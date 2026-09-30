from __future__ import annotations

import math
import os
import time
from collections import defaultdict
from typing import Any

import httpx
from prometheus_client.parser import text_string_to_metric_families

from .settings import TARGETS, VllmTarget

# ===== 启动就绪门控（v1.1.5，2026-09-30 用户："不要启动了就显示正常，要正常启动再显示在线"）=====
# 实测：vLLM 在"进程已起 / HTTP 已能应答，但权重还在加载"时，/metrics 会返回 200 而正文几乎为空
#   未就绪（线上 Qwen3.8-Flash-Next 28028）：1 行、0 个 vllm: 家族、0 个 model_name
#   已就绪（线上 DeepSeek-V4.1-Flash 41016）：687 行、含 vllm: 家族、434 个 model_name
# 所以"探针通"不等于"在服务"：只有出现引擎家族指标才算真就绪，且要连续 _READY_PROBES 次
# （默认 3 次 ≈ 6s）才报"在线"，避免加载途中就显示"正常"。
_ENGINE_FAMILIES = (
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
    "vllm:kv_cache_usage_perc",
    "vllm:num_requests_swapped",
)
_READY_PROBES = max(1, int(os.getenv("VLLM_READY_PROBES", "3")))
# 进程还在但一直没就绪时，多久之后从"启动中"改判"离线"（默认 300s：大模型冷启动本来就要几分钟）
_STARTING_MAX_SECONDS = max(30.0, float(os.getenv("VLLM_STARTING_MAX_SECONDS", "300")))


def _quantile(samples: dict[float, float], percentile: float) -> float:
    finite = sorted((boundary, count) for boundary, count in samples.items() if math.isfinite(boundary))
    total = samples.get(math.inf, finite[-1][1] if finite else 0)
    if not finite or total <= 0:
        return 0.0
    rank = total * percentile
    previous_boundary = previous_count = 0.0
    for boundary, count in finite:
        if count >= rank:
            bucket_count = count - previous_count
            if bucket_count <= 0:
                return boundary
            return previous_boundary + (boundary - previous_boundary) * (rank - previous_count) / bucket_count
        previous_boundary, previous_count = boundary, count
    return finite[-1][0]


class VllmCollector:
    def __init__(self) -> None:
        self.previous: dict[tuple[str, str], tuple[float, float]] = {}
        self._disc_cache: list[dict[str, object]] = []
        self._disc_at: float = 0.0
        self._ready_streak: dict[str, int] = {}     # 连续就绪探针次数（启动门控）
        self._unready_since: dict[str, float] = {}  # 首次探到"未就绪"的时刻（判启动中还是离线）

    def _targets(self) -> list[VllmTarget]:
        """纯自动发现：直接取当前运行中的 vLLM 进程合集（关了就从列表消失、开了就出现）。
        仅当发现为空（全部 vLLM 未运行）时兜底到 .env 配置，避免列表意外清空。"""
        now = time.time()
        if not self._disc_cache or now - self._disc_at > 5.0:
            try:
                from .discovery import discover_vllm_targets
                self._disc_cache = discover_vllm_targets()
            except Exception:
                self._disc_cache = []
            self._disc_at = now
        if self._disc_cache:
            return [VllmTarget(str(t["name"]), str(t["url"])) for t in self._disc_cache]
        return list(TARGETS)

    def _rate(self, target: str, metric: str, value: float, now: float) -> float:
        key = (target, metric)
        previous = self.previous.get(key)
        self.previous[key] = (now, value)
        if not previous or value < previous[1]:
            return 0.0
        return max(0.0, (value - previous[1]) / max(0.01, now - previous[0]))

    def _unready_state(self, url: str, now: float, alive_hint: bool) -> str:
        """未就绪时到底是"启动中"还是"离线"：
        - 进程还在（discovery 能看见该实例）且未就绪时长 < _STARTING_MAX_SECONDS → starting
        - 否则（进程没了 / 卡住太久）→ offline
        """
        since = self._unready_since.setdefault(url, now)
        if not alive_hint or (now - since) > _STARTING_MAX_SECONDS:
            return "offline"
        return "starting"

    def _offline(self, target: VllmTarget, error: Exception, alive_hint: bool = False) -> dict[str, Any]:
        """某个 vLLM 实例取不到指标时返回的零值结构（避免在异常路径写一长串字面量）。"""
        state = self._unready_state(target.url, time.time(), alive_hint)
        self._ready_streak.pop(target.url, None)     # 连不上要清零就绪计数，下次得重新攒够
        item: dict[str, Any] = {
            "name": target.name, "url": target.url, "online": False, "state": state,
            "ready_streak": 0, "error": str(error) or type(error).__name__, "models": [],
        }
        for key in (
            "running", "waiting", "swapped", "kv_cache_percent",
            "prompt_tokens_total", "generation_tokens_total", "requests_total",
            "prompt_tokens_per_second", "generation_tokens_per_second", "requests_per_second",
            "prefix_cache_hit_percent", "spec_accept_percent",
            "ttft_p50_ms", "ttft_p95_ms", "ttft_p99_ms",
            "tpot_p50_ms", "tpot_p95_ms", "tpot_p99_ms",
            "e2e_p95_ms", "queue_p95_ms",
        ):
            item[key] = 0.0
        return item

    async def _one(self, client: httpx.AsyncClient, target: VllmTarget, alive_hint: bool = False) -> dict[str, Any]:
        now = time.time()
        try:
            headers = {"Authorization": f"Bearer {target.api_key}"} if target.api_key else {}
            response = await client.get(f"{target.url}/metrics", headers=headers)
            response.raise_for_status()
        except Exception as error:
            return self._offline(target, error, alive_hint)   # 连不上/HTTP 错误 → 启动中或离线
        indexed: dict[str, list[tuple[dict[str, str], float]]] = defaultdict(list)
        models: set[str] = set()
        try:
            for family in text_string_to_metric_families(response.text):
                for sample in family.samples:
                    labels = {str(key): str(value) for key, value in sample.labels.items()}
                    indexed[sample.name].append((labels, float(sample.value)))
                    if labels.get("model_name"):
                        models.add(labels["model_name"])
        except Exception:
            # 能连上但正文还不可用（半截/空白）→ 当作"还没就绪"，别报离线也别报在线
            indexed, models = defaultdict(list), set()

        def total(*names: str) -> float:
            for name in names:
                if name in indexed:
                    return sum(value for _, value in indexed[name])
            return 0.0

        def histogram(*names: str) -> dict[float, float]:
            buckets: dict[float, float] = defaultdict(float)
            for name in names:
                bucket_name = name if name.endswith("_bucket") else f"{name}_bucket"
                if bucket_name in indexed:
                    for labels, value in indexed[bucket_name]:
                        raw = labels.get("le", "inf")
                        boundary = math.inf if raw in ("+Inf", "Inf", "inf") else float(raw)
                        buckets[boundary] += value
                    break
            return buckets

        prompt_total = total("vllm:prompt_tokens_total", "vllm:prompt_tokens")
        generation_total = total("vllm:generation_tokens_total", "vllm:generation_tokens")
        success_total = total("vllm:request_success_total", "vllm:request_success")
        prefix_queries = total("vllm:prefix_cache_queries_total", "vllm:prefix_cache_queries")
        prefix_hits = total("vllm:prefix_cache_hits_total", "vllm:prefix_cache_hits")
        draft = total("vllm:spec_decode_num_draft_tokens_total", "vllm:spec_decode_num_draft_tokens")
        accepted = total("vllm:spec_decode_num_accepted_tokens_total", "vllm:spec_decode_num_accepted_tokens")
        ttft = histogram("vllm:time_to_first_token_seconds")
        tpot = histogram("vllm:inter_token_latency_seconds")
        e2e = histogram("vllm:e2e_request_latency_seconds")
        queue = histogram("vllm:request_queue_time_seconds")

        # 启动就绪判定：引擎家族指标出现才算真就绪（见文件头注释的实测对比）
        engine_ready = any(name in indexed for name in _ENGINE_FAMILIES)
        streak = (self._ready_streak.get(target.url, 0) + 1) if engine_ready else 0
        self._ready_streak[target.url] = streak
        online = engine_ready and streak >= _READY_PROBES
        if online:
            self._unready_since.pop(target.url, None)
            state = "online"
        else:
            state = self._unready_state(target.url, now, alive_hint)
        # 只把"真就绪"实例的吞吐/延迟计入速率：加载中不该产生假的 tok/s
        if not online:
            self.previous.pop((target.url, "prompt"), None)
            self.previous.pop((target.url, "generation"), None)
            self.previous.pop((target.url, "requests"), None)
        return {
            "name": target.name, "url": target.url, "online": online,
            "state": state, "ready_streak": streak,
            "error": "", "models": sorted(models),
            "running": total("vllm:num_requests_running"), "waiting": total("vllm:num_requests_waiting"), "swapped": total("vllm:num_requests_swapped"),
            "kv_cache_percent": total("vllm:kv_cache_usage_perc") * 100,
            "prompt_tokens_total": prompt_total, "generation_tokens_total": generation_total, "requests_total": success_total,
            "prompt_tokens_per_second": self._rate(target.url, "prompt", prompt_total, now) if online else 0.0,
            "generation_tokens_per_second": self._rate(target.url, "generation", generation_total, now) if online else 0.0,
            "requests_per_second": self._rate(target.url, "requests", success_total, now) if online else 0.0,
            "prefix_cache_hit_percent": prefix_hits / prefix_queries * 100 if prefix_queries else 0,
            "spec_accept_percent": accepted / draft * 100 if draft else 0,
            "ttft_p50_ms": _quantile(ttft, .5) * 1000, "ttft_p95_ms": _quantile(ttft, .95) * 1000, "ttft_p99_ms": _quantile(ttft, .99) * 1000,
            "tpot_p50_ms": _quantile(tpot, .5) * 1000, "tpot_p95_ms": _quantile(tpot, .95) * 1000, "tpot_p99_ms": _quantile(tpot, .99) * 1000,
            "e2e_p95_ms": _quantile(e2e, .95) * 1000, "queue_p95_ms": _quantile(queue, .95) * 1000,
        }

    async def collect(self) -> dict[str, Any]:
        targets = self._targets()
        # alive_hint：该目标来自"进程发现"（进程确实在跑）→ 未就绪时算"启动中"而不是"离线"
        discovered = {str(t.get("url")) for t in self._disc_cache} if self._disc_cache else set()
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as client:
            instances = [await self._one(client, target, str(target.url) in discovered) for target in targets]
        keys = ["running", "waiting", "swapped", "prompt_tokens_total", "generation_tokens_total", "requests_total", "prompt_tokens_per_second", "generation_tokens_per_second", "requests_per_second"]
        aggregate = {key: sum(float(item[key]) for item in instances) for key in keys}
        online = [item for item in instances if item["online"]]
        for key in ["kv_cache_percent", "prefix_cache_hit_percent", "spec_accept_percent", "ttft_p50_ms", "ttft_p95_ms", "ttft_p99_ms", "tpot_p50_ms", "tpot_p95_ms", "tpot_p99_ms", "e2e_p95_ms", "queue_p95_ms"]:
            aggregate[key] = sum(float(item[key]) for item in online) / len(online) if online else 0
        aggregate["models"] = sorted({model for item in instances for model in item["models"]})
        aggregate["online_instances"] = len(online)
        aggregate["total_instances"] = len(instances)
        return {"instances": instances, "aggregate": aggregate}
