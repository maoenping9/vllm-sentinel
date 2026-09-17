from __future__ import annotations

"""运行中 vLLM 实例的自动发现。

约束：vllm-sentinel 容器非 root 运行、read_only、cap_drop ALL，
只能读 /host/proc/<pid>/cmdline（读不到 environ）。
因此扫描所有进程的 cmdline，命中 `vllm` + `--port <N>` 的主服务进程即视为一个 vLLM 实例，
并从中提取 `--served-model-name`（无则取 `serve <model>` 的模型目录名）。
配合 settings.VllmTarget，把未在 .env 里配置、但实际在跑的模型（如 GLM-5.3-Flash）也纳入采集。
"""

import re
from pathlib import Path

from .settings import HOST_ROOT

PROC = Path(HOST_ROOT) / "proc"


def _cmdline(pid: str) -> str:
    try:
        raw = (PROC / pid / "cmdline").read_bytes()
        return raw.replace(b"\x00", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def discover_vllm_targets() -> list[dict[str, object]]:
    """返回当前运行中的 vLLM 实例：[{name, port, url}, ...]（按端口去重、升序）。"""
    out: list[dict[str, object]] = []
    try:
        for entry in PROC.glob("[0-9]*"):
            pid = entry.name
            if not pid.isdigit():
                continue
            cmd = _cmdline(pid)
            if not cmd or "vllm" not in cmd.lower():
                continue
            m = re.search(r"--port\s+(\d+)", cmd)
            if not m:
                continue
            port = int(m.group(1))
            if port <= 0:
                continue
            sm = re.search(r"--served-model-name\s+(\S+)", cmd)
            if sm:
                name = sm.group(1)
            else:
                mm = re.search(r"\bserve\s+(\S+)", cmd)
                name = Path(mm.group(1)).name if mm else f"vllm-{port}"
            out.append({"name": name, "port": port, "url": f"http://127.0.0.1:{port}"})
    except Exception:
        return []
    seen: dict[int, dict[str, object]] = {}
    for item in out:
        seen.setdefault(item["port"], item)
    return sorted(seen.values(), key=lambda item: int(item["port"]))
