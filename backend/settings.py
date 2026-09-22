from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VllmTarget:
    name: str
    url: str
    api_key: str = ""


def _targets() -> list[VllmTarget]:
    raw = os.getenv("VLLM_ENDPOINTS", "")
    if not raw:
        return [VllmTarget("Primary", "http://127.0.0.1:9003")]
    try:
        data = json.loads(raw)
        return [
            VllmTarget(
                str(item.get("name") or f"Instance {index + 1}"),
                str(item["url"]).rstrip("/"),
                str(item.get("api_key") or ""),
            )
            for index, item in enumerate(data)
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [
            VllmTarget(f"Instance {index + 1}", value.strip().rstrip("/"))
            for index, value in enumerate(raw.split(",")) if value.strip()
        ]


TARGETS = _targets()
SAMPLE_INTERVAL = max(1.0, float(os.getenv("SAMPLE_INTERVAL", "2")))
HISTORY_RETENTION_HOURS = max(1, int(os.getenv("HISTORY_RETENTION_HOURS", "744")))  # 31天，覆盖自然月电费统计
DATA_DIR = os.getenv("DATA_DIR", "/data")
BMC_STATE_FILE = os.getenv("BMC_STATE_FILE", os.path.join(DATA_DIR, "bmc-state.json"))
BMC_SAMPLE_INTERVAL = max(3.0, float(os.getenv("BMC_SAMPLE_INTERVAL", "5")))
HOST_ROOT = os.getenv("HOST_ROOT", "/host")
AUTH_USERNAME = os.getenv("DASHBOARD_USERNAME", "")
AUTH_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
AUTH_ENABLED = os.getenv("DASHBOARD_AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
APP_NAME = os.getenv("APP_NAME", "vLLM Sentinel")
GPU_TEMP_WARNING = float(os.getenv("GPU_TEMP_WARNING", "78"))
GPU_TEMP_CRITICAL = float(os.getenv("GPU_TEMP_CRITICAL", "86"))
GPU_MEMORY_WARNING = float(os.getenv("GPU_MEMORY_WARNING", "92"))
QUEUE_WARNING = float(os.getenv("QUEUE_WARNING", "16"))
