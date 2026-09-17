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
from .settings import APP_NAME, AUTH_ENABLED, AUTH_PASSWORD, AUTH_USERNAME, GPU_MEMORY_WARNING, GPU_TEMP_CRITICAL, GPU_TEMP_WARNING, QUEUE_WARNING, SAMPLE_INTERVAL
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
async def current_state():
    return state


@app.get("/api/history")
async def history(range: str = Query("1h", pattern="^(15m|1h|6h|24h|7d)$")):
    seconds = {"15m": 900, "1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}[range]
    return {"range": range, "points": await asyncio.to_thread(history_store.read, seconds)}


# 浙江滨江 商业用电（单一制不满1千伏，2026年9月价，国网浙江代理购电公告）
_ENERGY_PRICE_FLAT = 0.736945    # 平段/非分时 元/度
_ENERGY_PRICE_PEAK = 1.133475    # 高峰 元/度
_ENERGY_PRICE_VALLEY = 0.457041  # 低谷 元/度


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
    """从全部历史样本积分：累计电量(kWh) + 按时段电价折算的累计电费(元)。
    v1.1.1: 额外计算本月/本年累计电费（预算进度条用，后台自动按自然月/年切分）。"""
    import json as _json
    import sqlite3 as _sqlite3
    from datetime import datetime as _dt
    try:
        conn = _sqlite3.connect(history_store.path, timeout=8)
        rows = conn.execute("SELECT ts, payload FROM samples ORDER BY ts").fetchall()
        conn.close()
    except Exception:
        return {"kwh": 0.0, "cost": 0.0, "days": 0, "cost_month": 0.0, "cost_year": 0.0}
    now = _dt.now()
    try:
        month_start = _dt(now.year, now.month, 1).timestamp()
        year_start = _dt(now.year, 1, 1).timestamp()
    except Exception:
        month_start = year_start = 0.0
    total_kwh = 0.0
    cost = 0.0
    cost_month = 0.0
    cost_year = 0.0
    prev = None
    for ts, payload in rows:
        try:
            power = _json.loads(payload).get("power") or 0.0
        except Exception:
            power = 0.0
        if prev is not None:
            dt_h = (ts - prev[0]) / 3600.0
            if 0 < dt_h < 1.0:  # 忽略采集空洞
                kwh = prev[1] / 1000.0 * dt_h
                money = kwh * _tou_price_utc(prev[0])
                total_kwh += kwh
                cost += money
                if prev[0] >= month_start:
                    cost_month += money
                if prev[0] >= year_start:
                    cost_year += money
        prev = (ts, power)
    days = 0
    if rows:
        days = max(1, round((rows[-1][0] - rows[0][0]) / 86400.0))
    return {"kwh": round(total_kwh, 1), "cost": round(cost, 2), "days": days,
            "cost_month": round(cost_month, 2), "cost_year": round(cost_year, 2)}


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
