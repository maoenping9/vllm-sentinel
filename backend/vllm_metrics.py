from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any

import httpx
from prometheus_client.parser import text_string_to_metric_families

from .settings import TARGETS, VllmTarget


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

    def _rate(self, target: str, metric: str, value: float, now: float) -> float:
        key = (target, metric)
        previous = self.previous.get(key)
        self.previous[key] = (now, value)
        if not previous or value < previous[1]:
            return 0.0
        return max(0.0, (value - previous[1]) / max(0.01, now - previous[0]))

    async def _one(self, client: httpx.AsyncClient, target: VllmTarget) -> dict[str, Any]:
        now = time.time()
        try:
            headers = {"Authorization": f"Bearer {target.api_key}"} if target.api_key else {}
            response = await client.get(f"{target.url}/metrics", headers=headers)
            response.raise_for_status()
            indexed: dict[str, list[tuple[dict[str, str], float]]] = defaultdict(list)
            models: set[str] = set()
            for family in text_string_to_metric_families(response.text):
                for sample in family.samples:
                    labels = {str(key): str(value) for key, value in sample.labels.items()}
                    indexed[sample.name].append((labels, float(sample.value)))
                    if labels.get("model_name"):
                        models.add(labels["model_name"])

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
            return {
                "name": target.name, "url": target.url, "online": True, "error": "", "models": sorted(models),
                "running": total("vllm:num_requests_running"), "waiting": total("vllm:num_requests_waiting"), "swapped": total("vllm:num_requests_swapped"),
                "kv_cache_percent": total("vllm:kv_cache_usage_perc") * 100,
                "prompt_tokens_total": prompt_total, "generation_tokens_total": generation_total, "requests_total": success_total,
                "prompt_tokens_per_second": self._rate(target.name, "prompt", prompt_total, now),
                "generation_tokens_per_second": self._rate(target.name, "generation", generation_total, now),
                "requests_per_second": self._rate(target.name, "requests", success_total, now),
                "prefix_cache_hit_percent": prefix_hits / prefix_queries * 100 if prefix_queries else 0,
                "spec_accept_percent": accepted / draft * 100 if draft else 0,
                "ttft_p50_ms": _quantile(ttft, .5) * 1000, "ttft_p95_ms": _quantile(ttft, .95) * 1000, "ttft_p99_ms": _quantile(ttft, .99) * 1000,
                "tpot_p50_ms": _quantile(tpot, .5) * 1000, "tpot_p95_ms": _quantile(tpot, .95) * 1000, "tpot_p99_ms": _quantile(tpot, .99) * 1000,
                "e2e_p95_ms": _quantile(e2e, .95) * 1000, "queue_p95_ms": _quantile(queue, .95) * 1000,
            }
        except (httpx.HTTPError, ValueError) as error:
            return {"name": target.name, "url": target.url, "online": False, "error": str(error), "models": [], "running": 0, "waiting": 0, "swapped": 0, "kv_cache_percent": 0, "prompt_tokens_total": 0, "generation_tokens_total": 0, "requests_total": 0, "prompt_tokens_per_second": 0, "generation_tokens_per_second": 0, "requests_per_second": 0, "prefix_cache_hit_percent": 0, "spec_accept_percent": 0, "ttft_p50_ms": 0, "ttft_p95_ms": 0, "ttft_p99_ms": 0, "tpot_p50_ms": 0, "tpot_p95_ms": 0, "tpot_p99_ms": 0, "e2e_p95_ms": 0, "queue_p95_ms": 0}

    async def collect(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as client:
            instances = [await self._one(client, target) for target in TARGETS]
        keys = ["running", "waiting", "swapped", "prompt_tokens_total", "generation_tokens_total", "requests_total", "prompt_tokens_per_second", "generation_tokens_per_second", "requests_per_second"]
        aggregate = {key: sum(float(item[key]) for item in instances) for key in keys}
        online = [item for item in instances if item["online"]]
        for key in ["kv_cache_percent", "prefix_cache_hit_percent", "spec_accept_percent", "ttft_p50_ms", "ttft_p95_ms", "ttft_p99_ms", "tpot_p50_ms", "tpot_p95_ms", "tpot_p99_ms", "e2e_p95_ms", "queue_p95_ms"]:
            aggregate[key] = sum(float(item[key]) for item in online) / len(online) if online else 0
        aggregate["models"] = sorted({model for item in instances for model in item["models"]})
        aggregate["online_instances"] = len(online)
        aggregate["total_instances"] = len(instances)
        return {"instances": instances, "aggregate": aggregate}
