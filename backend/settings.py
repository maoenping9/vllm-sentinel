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
# ===== v1.1.4：累计口径 =====
# 自然月/自然年/流量周期都按**北京时间**切边界（容器默认 UTC，差 8h 会把月初/年初那 8 小时
# 算到上一个月/年，见 2026-09-29 修正）；与 _tou_price_utc 的分时电价口径保持一致。
TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "8"))
# 流量周期起点：每月该日 00:00（本地）→ 次月同日，与桌面组件「网络流量（20日起）」一致
NET_CYCLE_START_DAY = min(28, max(1, int(os.getenv("NET_CYCLE_START_DAY", "20"))))
# 流量累加基线（GB，十进制）：机器上只有本机网卡的采样，看不到路由器/ISP 的全网流量，
# 所以可以填一个手工实测值做「本周期起点」的基准，之后按本机采样增量实时累加（单调递增）。
# 默认 0（不加基准，纯本机累计）；只在首次运行时写入一次 meta，之后跨周期自动失效。
NET_CYCLE_BASE_GB = float(os.getenv("NET_CYCLE_BASE_GB", "0"))
