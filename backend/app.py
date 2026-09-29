from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .bmc_metrics import BmcCollector
from .database import HistoryStore
from .gpu_map import resolve as resolve_gpu_map
from .gpu_map import _scan_small_services
from .host_metrics import GpuCollector, HostCollector
from .settings import APP_NAME, AUTH_ENABLED, AUTH_PASSWORD, AUTH_USERNAME, GPU_MEMORY_WARNING, GPU_TEMP_CRITICAL, GPU_TEMP_WARNING, NET_CYCLE_BASE_GB, NET_CYCLE_START_DAY, QUEUE_WARNING, SAMPLE_INTERVAL, TZ_OFFSET_HOURS
from .vllm_metrics import VllmCollector


host_collector = HostCollector()
gpu_collector = GpuCollector()
bmc_collector = BmcCollector()
vllm_collector = VllmCollector()
history_store = HistoryStore()
realtime: deque[dict[str, Any]] = deque(maxlen=900)
state: dict[str, Any] = {"status": "starting", "timestamp": time.time()}
subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
last_persist = 0.0


def _alerts(host: dict[str, Any], gpu: dict[str, Any], vllm: dict[str, Any], bmc: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for item in gpu["items"]:
        if item["temperature"] >= GPU_TEMP_CRITICAL:
            alerts.append({"severity": "critical", "title": f"GPU {item['index']} 温度过高", "detail": f"当前 {item['temperature']:.0f}°C，超过临界阈值"})
        elif item["temperature"] >= GPU_TEMP_WARNING:
            alerts.append({"severity": "warning", "title": f"GPU {item['index']} 温度偏高", "detail": f"当前 {item['temperature']:.0f}°C"})
        if item["memory_percent"] >= GPU_MEMORY_WARNING:
            alerts.append({"severity": "warning", "title": f"GPU {item['index']} 显存接近满载", "detail": f"已使用 {item['memory_percent']:.1f}%"})
    aggregate = vllm["aggregate"]
    if aggregate["waiting"] >= QUEUE_WARNING:
        alerts.append({"severity": "warning", "title": "请求队列拥塞", "detail": f"当前有 {aggregate['waiting']:.0f} 个排队请求"})
    for instance in vllm["instances"]:
        if not instance["online"]:
            alerts.append({"severity": "critical", "title": f"{instance['name']} 无法连接", "detail": instance["error"][:160]})
    if host["memory"]["percent"] >= 92:
        alerts.append({"severity": "warning", "title": "主机内存压力较高", "detail": f"已使用 {host['memory']['percent']:.1f}%"})
    if not bmc.get("online"):
        alerts.append({"severity": "warning", "title": "BMC 传感器不可用", "detail": str(bmc.get("error", "无法读取 IPMI"))[:160]})
    for sensor in [*bmc.get("temperatures", []), *bmc.get("fans", [])]:
        if sensor.get("status") not in {"ok", "na"}:
            alerts.append({"severity": "critical", "title": f"BMC 传感器异常：{sensor.get('name')}", "detail": f"读数 {sensor.get('value')} {sensor.get('units')}，状态 {sensor.get('status')}"})
    for psu in bmc.get("psus", []):
        if psu.get("status") != "ok":
            alerts.append({"severity": "critical", "title": f"电源模块异常：{psu.get('name')}", "detail": str(psu.get("detail", ""))})
    return alerts


def _point(snapshot: dict[str, Any]) -> dict[str, Any]:
    agg = snapshot["vllm"]["aggregate"]
    return {
        "ts": snapshot["timestamp"], "prompt_tps": round(agg["prompt_tokens_per_second"], 2), "generation_tps": round(agg["generation_tokens_per_second"], 2),
        "ttft_p95": round(agg["ttft_p95_ms"], 2), "tpot_p95": round(agg["tpot_p95_ms"], 2), "running": agg["running"], "waiting": agg["waiting"],
        "kv_cache": round(agg["kv_cache_percent"], 2), "gpu": snapshot["gpu"]["utilization"], "gpu_memory": snapshot["gpu"]["memory_percent"],
        "cpu": snapshot["host"]["cpu"]["usage"], "memory": snapshot["host"]["memory"]["percent"], "power": snapshot["gpu"]["power_w"],
        "disk": round(snapshot["host"]["disk"]["percent"], 2), "net": round((snapshot["host"]["network"]["rx_bps"] + snapshot["host"]["network"]["tx_bps"]) / 1_000_000, 2),
        "bmc_power": float(snapshot.get("bmc", {}).get("power", {}).get("instant_w", 0)),
    }


async def collect_loop() -> None:
    global state, last_persist
    while True:
        started = time.time()
        try:
            host_task = asyncio.to_thread(host_collector.collect)
            gpu_task = asyncio.to_thread(gpu_collector.collect)
            bmc_task = asyncio.to_thread(bmc_collector.collect)
            host, gpu, bmc, vllm = await asyncio.gather(host_task, gpu_task, bmc_task, vllm_collector.collect())
            snapshot = {"status": "ok", "timestamp": time.time(), "sample_interval": SAMPLE_INTERVAL, "host": host, "gpu": gpu, "bmc": bmc, "vllm": vllm}
            snapshot["gpu_map"] = resolve_gpu_map(gpu["items"], vllm["instances"])
            snapshot["small_models"] = _scan_small_services(snapshot["gpu_map"], vllm["instances"])
            snapshot["alerts"] = _alerts(host, gpu, vllm, bmc)
            point = _point(snapshot)
            realtime.append(point)
            snapshot["realtime"] = list(realtime)[-180:]
            state = snapshot
            if snapshot["timestamp"] - last_persist >= 5:
                await asyncio.to_thread(history_store.write, point)
                last_persist = snapshot["timestamp"]
            for queue in list(subscribers):
                try:
                    queue.put_nowait(snapshot)
                except asyncio.QueueFull:
                    pass
        except Exception as error:  # collector stays alive; surfaced in health endpoint
            state = {**state, "status": "degraded", "error": str(error), "timestamp": time.time()}
        await asyncio.sleep(max(0.05, SAMPLE_INTERVAL - (time.time() - started)))


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(collect_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title=APP_NAME, version="1.1.0", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=900)


@app.middleware("http")
async def security(request: Request, call_next):
    if AUTH_ENABLED and AUTH_USERNAME and AUTH_PASSWORD and request.url.path != "/api/health":
        auth = request.headers.get("Authorization", "")
        valid = False
        if auth.startswith("Basic "):
            try:
                user, password = base64.b64decode(auth[6:]).decode().split(":", 1)
                valid = secrets.compare_digest(user, AUTH_USERNAME) and secrets.compare_digest(password, AUTH_PASSWORD)
            except (ValueError, UnicodeDecodeError):
                pass
        if not valid:
            return JSONResponse({"detail": "Authentication required"}, 401, {"WWW-Authenticate": 'Basic realm="vLLM Sentinel"'})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:"
    return response


@app.get("/api/health")
async def health():
    return {"status": state.get("status", "starting"), "timestamp": state.get("timestamp"), "version": "1.1.0"}


@app.get("/api/state")
async def current_state(light: bool = Query(False)):
    # light=1：给 Mac 组件等只需要最新一帧的客户端用，剔除 realtime 历史窗口（占响应 ~79%）
    if light and isinstance(state, dict) and "realtime" in state:
        slim = {k: v for k, v in state.items() if k != "realtime"}
        return slim
    return state


@app.get("/api/history")
async def history(range: str = Query("1h", pattern="^(15m|1h|6h|24h|7d)$")):
    seconds = {"15m": 900, "1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}[range]
    return {"range": range, "points": await asyncio.to_thread(history_store.read, seconds)}


# 浙江滨江 商业用电（单一制不满1千伏，2026年9月价，国网浙江代理购电公告）
_ENERGY_PRICE_FLAT = 0.736945    # 平段/非分时 元/度
_ENERGY_PRICE_PEAK = 1.133475    # 高峰 元/度
_ENERGY_PRICE_VALLEY = 0.457041  # 低谷 元/度


def _calendar_month_end_day(now) -> int:
    """自然月最后一天（10月31天→31、2月平年28/闰年29）。"""
    import calendar as _cal
    return _cal.monthrange(now.year, now.month)[1]


# ===== v1.1.4：本地（北京）时间边界工具 =====
# 容器 TZ=UTC，旧代码用 datetime.now() 当本地时间 → 月初/年初边界差 8 小时。
_TZ = TZ_OFFSET_HOURS * 3600


def _local_parts(ts: float) -> tuple[int, int, int]:
    lt = time.gmtime(ts + _TZ)
    return lt.tm_year, lt.tm_mon, lt.tm_mday


def _local_date(ts: float) -> str:
    """UTC 时间戳 → 本地日期字符串 YYYY-MM-DD（日粒度汇总的键）。"""
    lt = time.gmtime(ts + _TZ)
    return f"{lt.tm_year:04d}-{lt.tm_mon:02d}-{lt.tm_mday:02d}"


def _ts_of_day(day: str) -> float:
    """本地日期 YYYY-MM-DD 的 00:00 → UTC 时间戳。"""
    import calendar as _cal
    try:
        tm = time.strptime(day, "%Y-%m-%d")
    except ValueError:
        return 0.0
    return _cal.timegm(tm) - _TZ


def _next_month_first(year: int, month: int) -> str:
    return f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"


def _cycle_start_date(year: int, month: int, day: int) -> str:
    """流量周期起点（本地）：当日 >= NET_CYCLE_START_DAY → 本月该日；否则上月该日。"""
    if day >= NET_CYCLE_START_DAY:
        return f"{year:04d}-{month:02d}-{NET_CYCLE_START_DAY:02d}"
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    return f"{prev_year:04d}-{prev_month:02d}-{NET_CYCLE_START_DAY:02d}"


_NET_SEED_KEY = "net_cycle_seed"


def _net_cycle_seed() -> dict[str, Any]:
    """本周期流量手工基准（GB）：只在首次运行时写一次 meta，之后长期有效；
    周期滚动（下个 20 日）后因 cycle_start 不匹配而自动失效，不参与累计。"""
    raw = history_store.meta_get(_NET_SEED_KEY)
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (TypeError, ValueError):
            pass
    seed = {"cycle_start": "", "bytes": 0.0}
    if NET_CYCLE_BASE_GB > 0:
        seed = {
            "cycle_start": _cycle_start_date(*_local_parts(time.time())),
            "bytes": NET_CYCLE_BASE_GB * 1_000_000_000.0,
            "seeded_at": time.time(),
        }
        try:
            history_store.meta_set(_NET_SEED_KEY, json.dumps(seed))
        except Exception:
            pass
    return seed


def _integrate_day(prev_ts: float, prev: dict[str, Any], ts: float, cur: dict[str, Any], acc: dict[str, dict[str, float]]) -> None:
    """把相邻两个采样点之间的一段，累加到「前一点所在本地日」的汇总里。

    - 电量/电费：power(瓦) × dt，电价按 prev_ts 的分时档（与 _tou_price_utc 同口径）
    - 流量：采样点 net 是 rx+tx 的 MB/s（见 _point），换算成字节累加
    - dt > 60s 视为关机/采集空洞，整段不计（关机不耗电，也不该按满功率补）
    """
    dt = ts - prev_ts
    if not (0.0 < dt < 60.0):
        return
    day = _local_date(prev_ts)
    slot = acc.setdefault(day, {"kwh": 0.0, "cost": 0.0, "net_bytes": 0.0})
    kwh = float(prev.get("power") or 0.0) / 1000.0 * (dt / 3600.0)
    slot["kwh"] += kwh
    slot["cost"] += kwh * _tou_price_utc(prev_ts)
    slot["net_bytes"] += float(prev.get("net") or 0.0) * 1_000_000.0 * dt


def _tou_price_utc(ts: float) -> float:
    """按北京时间时段取电价（samples.ts 为 UTC）。"""
    lt = time.gmtime(ts + 8 * 3600)
    hm = lt.tm_hour * 60 + lt.tm_min
    month = lt.tm_mon
    summer = month in (1, 7, 8, 12)
    if hm < 420 or (660 <= hm < 840):
        return _ENERGY_PRICE_VALLEY
    if summer and 1080 <= hm < 1320:  # 夏冬季尖峰 18:00-22:00
        return _ENERGY_PRICE_PEAK
    if (420 <= hm < 660) or (840 <= hm < 960) or hm >= 1380:
        return _ENERGY_PRICE_FLAT
    return _ENERGY_PRICE_PEAK


def _cumulative_energy() -> dict[str, Any]:
    """累计电量/电费 + 流量累计。**全部基于 daily 汇总表（永不被 retention 裁剪）**。

    2026-09-29 重写（用户："查看本月额度是否按自然月加总上去了，本年额度也要实时加总，
    不要只有7天加上"）：旧实现每次请求全表扫 samples 并只统计 retention（31 天）内的样本，
    于是「本年额度」实际只等于最近一个月；且边界用 UTC（容器 TZ=UTC），月初/年初会错 8 小时。
    现在：增量把新样本汇入 daily（本地日粒度、与分时电价同口径），月/年/流量周期都从 daily 求和，
    历史天不再因裁剪丢失；日/月/年边界一律按北京时间。
    """
    try:
        history_store.rollup_into(_integrate_day)
    except Exception:
        pass
    rows = history_store.daily_all()
    now = time.time()
    year, month, day = _local_parts(now)
    month_prefix = f"{year:04d}-{month:02d}-"
    year_prefix = f"{year:04d}-"
    cycle_start = _cycle_start_date(year, month, day)
    today = _local_date(now)

    total_kwh = 0.0
    cost = 0.0
    cost_month = 0.0
    cost_year = 0.0
    kwh_month = 0.0
    kwh_year = 0.0
    net_month = 0.0
    net_year = 0.0
    net_cycle = 0.0
    month_days: list[str] = []
    for row in rows:
        d = row["day"]
        total_kwh += row["kwh"]
        cost += row["cost"]
        in_year = d.startswith(year_prefix)
        in_month = d.startswith(month_prefix)
        if in_year:
            cost_year += row["cost"]
            kwh_year += row["kwh"]
            net_year += row["net_bytes"]
        if in_month:
            cost_month += row["cost"]
            kwh_month += row["kwh"]
            net_month += row["net_bytes"]
            month_days.append(d)
        if cycle_start <= d <= today:
            net_cycle += row["net_bytes"]
    seed = _net_cycle_seed()
    if seed.get("cycle_start") == cycle_start:
        net_cycle += float(seed.get("bytes") or 0.0)   # 本周期手工基准（跨周期自动失效）
    # days：本月已过天数（自然月口径，显示/预估用）
    days = day
    # 本月预估：用本月日均速率外推到月底（覆盖不足 6h 不出预估，防月初外推爆炸）
    cost_month_est = cost_month
    if month_days and cost_month > 0:
        covered_from = max(_ts_of_day(month_days[0]), _ts_of_day(f"{year:04d}-{month:02d}-01"))
        covered_hours = (now - covered_from) / 3600.0
        remaining_hours = max(0.0, (_ts_of_day(_next_month_first(year, month)) - now) / 3600.0)
        if covered_hours >= 6.0:
            cost_month_est = cost_month + (cost_month / covered_hours) * remaining_hours
    return {
        "kwh": round(total_kwh, 1), "cost": round(cost, 2), "days": days,
        "cost_month": round(cost_month, 2), "cost_year": round(cost_year, 2),
        "cost_month_est": round(cost_month_est, 2),
        "kwh_month": round(kwh_month, 1), "kwh_year": round(kwh_year, 1),
        # 流量累计（字节）：周期(20日起)/本月/本年，来自 daily + 本周期基准
        "net_cycle_bytes": round(net_cycle, 0), "net_month_bytes": round(net_month, 0),
        "net_year_bytes": round(net_year, 0), "net_cycle_start": cycle_start,
        "net_cycle_base_bytes": round(float(seed.get("bytes") or 0.0), 0) if seed.get("cycle_start") == cycle_start else 0.0,
        "days_with_data": len(rows),
    }


@app.get("/api/energy")
async def energy():
    return await asyncio.to_thread(_cumulative_energy)


@app.get("/api/stream")
async def stream(request: Request):
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2)
    subscribers.add(queue)

    async def events():
        try:
            if state.get("host"):
                yield f"data: {json.dumps(state, separators=(',', ':'))}\n\n"
            while not await request.is_disconnected():
                try:
                    snapshot = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {json.dumps(snapshot, separators=(',', ':'))}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            subscribers.discard(queue)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


STATIC_DIR = Path(os.getenv("STATIC_DIR", "/app/static"))
if STATIC_DIR.exists():
    assets = STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}")
    async def spa(path: str):
        candidate = STATIC_DIR / path
        if candidate.is_file() and STATIC_DIR in candidate.resolve().parents:
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(404)
