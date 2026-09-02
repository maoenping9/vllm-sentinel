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
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .bmc_metrics import BmcCollector
from .database import HistoryStore
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
