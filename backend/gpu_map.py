from __future__ import annotations

"""GPU ↔ LLM 关联解析。

约束：vllm-sentinel 容器以非 root(sentinel) 运行、read_only、cap_drop ALL，
只能读 /host/proc/<pid>/cmdline 与 status(PPid)，读不到 environ（无 CUDA_VISIBLE_DEVICES）。
因此"GPU 进程 → 所属 LLM"通过向上遍历父进程链，找到带 `--port <N>` 的 vLLM serve 主进程，
再按端口映射到 .env 里的 VLLM_ENDPOINTS 实例名（见 settings.VllmTarget）。

非 vLLM 的 GPU 常驻服务（如 GPU0 的 WeMM 多模态嵌入 :8008）通过 cmdline 关键字识别并单独呈现。
"""

import re
from pathlib import Path
from typing import Any

from .settings import HOST_ROOT

PROC = Path(HOST_ROOT) / "proc"

_MAX_PARENT_HOPS = 14


def _cmdline(pid: int) -> str:
    try:
        raw = (PROC / str(pid) / "cmdline").read_bytes()
        return raw.replace(b"\x00", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def _ppid(pid: int) -> int | None:
    try:
        for line in (PROC / str(pid) / "status").read_text(errors="replace").splitlines():
            if line.startswith("PPid:"):
                parts = line.split()
                return int(parts[1]) if len(parts) > 1 else None
    except OSError:
        pass
    return None


# 非 vLLM 的 GPU 常驻服务：cmdline 关键字 → (显示名, 端口)
_NON_VLLM_SERVICES: list[tuple[str, str, int]] = [
    ("embed-wemm-mm-gpu", "WeMM-Embedding-9B", 8008),
    ("embed-wemm-mm-cpu", "WeMM-Embedding-9B-CPU", 8008),
    ("embed-cpu-8008", "Qwen3-Embedding-0.6B", 8008),
]

# CPU 上跑的小模型服务（不在任何 GPU 上）：cmdline 关键字 → (显示名, 端口?)
# 只要运行的模型（无论大小、GPU 还是 CPU）都要在组件"模型服务"里呈现。
_CPU_SMALL_SERVICES: list[tuple[str, str, int | None]] = [
    ("embed-wemm-mm-cpu", "WeMM-Embedding-9B-CPU", 8008),
    ("embed-cpu-8008", "Qwen3-Embedding-0.6B", 8008),
    ("meeting-asr", "Meeting-ASR", 20001),
    ("cosyvoice", "CosyVoice-TTS", None),
    ("fish-speech", "FishSpeech-TTS", None),
    ("gpt-sovits", "GPT-SoVITS-TTS", None),
    ("whisper", "Whisper-ASR", None),
]


def _scan_small_services(
    gpu_map: list[dict[str, Any]],
    vllm_instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """扫描 /proc 找出 CPU 上跑的小模型服务（不在任何 GPU、也不是 vLLM 实例）。

    返回 [{"name": <显示名>, "port": <int>?}, ...]，按名称去重排序。
    """
    known_names: set[str] = {m.get("service", "") for m in gpu_map}
    for inst in vllm_instances:
        known_names.add(inst.get("name") or "")
        for model in inst.get("models") or []:
            known_names.add(model)
    known_ports = {m.get("port") for m in gpu_map if m.get("port") is not None}

    found: dict[str, dict[str, Any]] = {}
    for entry in PROC.iterdir():
        if not entry.name.isdigit():
            continue
        cmd = _cmdline(int(entry.name))
        if not cmd:
            continue
        for keyword, label, port in _CPU_SMALL_SERVICES:
            if keyword in cmd:
                # 已在 GPU 上呈现 / 已是 vLLM 实例 → 不重复上报
                if label in known_names or (port is not None and port in known_ports):
                    break
                found[label] = {"name": label, "port": port}
                break
    return sorted(found.values(), key=lambda m: m["name"])


def _service_from_cmdline(cmd: str) -> tuple[str, int] | None:
    if not cmd:
        return None
    for keyword, label, port in _NON_VLLM_SERVICES:
        if keyword in cmd:
            return label, port
    return None


def _instance_from_cmdline(cmd: str, port_to_name: dict[int, str]) -> tuple[str, int] | None:
    """从 vLLM serve 主进程 cmdline 提取实例名。找不到端口时用 served-model-name / model 兜底。"""
    if not cmd:
        return None
    m = re.search(r"--port\s+(\d+)", cmd)
    if m:
        port = int(m.group(1))
        if port in port_to_name:
            return port_to_name[port], port
        sm = re.search(r"--served-model-name\s+(\S+)", cmd)
        if sm:
            label = sm.group(1)
        else:
            mm = re.search(r"\bserve\s+(\S+)", cmd)
            label = mm.group(1) if mm else f"port:{port}"
        return label, port
    # v93 兜底：容器化 vLLM 主进程（uvicorn 默认 8000，cmdline 无 --port 旗标）——
    # 用 served-model-name / model 目录名识别，端口取 0（仅作占位，GPU 归属靠服务名聚合）
    sm = re.search(r"--served-model-name\s+(\S+)", cmd)
    if sm:
        return sm.group(1), 0
    mm = re.search(r"(?:\bvllm\s+serve\b|api_server)\s+(?:--model\s+)?(\S+)", cmd)
    if mm:
        return Path(mm.group(1)).name, 0
    return None


def _owner(pid: int, port_to_name: dict[int, str]) -> tuple[str, int] | None:
    """对某个 GPU 进程 PID 向上找所属 LLM 服务，返回 (服务名, 端口)。"""
    seen = 0
    while pid and pid > 1 and seen < _MAX_PARENT_HOPS:
        cmd = _cmdline(pid)
        svc = _service_from_cmdline(cmd)
        if svc:
            return svc
        inst = _instance_from_cmdline(cmd, port_to_name)
        if inst:
            return inst
        pid = _ppid(pid)
        seen += 1
    return None


def resolve(gpu_items: list[dict[str, Any]], vllm_instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """计算 GPU↔LLM 对照，回填 vllm.instances[*].gpus 与 gpu.items[*].service，并返回 gpu_map。

    gpu_map: [{"service": <显示名>, "gpus": [<索引>...], "port": <int>?}, ...]（按服务名聚合）
    """
    # 端口 → 实例名（来自 .env 的 VllmTarget）
    port_to_name: dict[int, str] = {}
    for inst in vllm_instances:
        url = (inst.get("url") or "").rstrip("/")
        try:
            port = int(url.rsplit(":", 1)[1])
            port_to_name[port] = inst["name"]
        except (ValueError, IndexError):
            continue
    name_to_port = {name: port for port, name in port_to_name.items()}

    # GPU 索引 → (服务名, 端口)
    gpu_owner: dict[int, tuple[str, int]] = {}
    for g in gpu_items:
        for proc in g.get("processes", []):
            owner = _owner(int(proc["pid"]), port_to_name)
            if owner:
                gpu_owner[g["index"]] = owner
                break

    # 按服务名聚合 GPU 索引
    svc_to_meta: dict[str, dict[str, Any]] = {}
    for idx, (svc, port) in gpu_owner.items():
        meta = svc_to_meta.setdefault(svc, {"service": svc, "gpus": [], "port": port})
        meta["gpus"].append(idx)
    for meta in svc_to_meta.values():
        meta["gpus"] = sorted(meta["gpus"])

    # 回填 vllm.instances[*].gpus：按实例自身端口匹配（同名多实例也不会互相污染）；
    # v93：占位端口 0 的服务（容器化 vLLM，cmdline 无 --port）按服务名匹配——
    # 实例名与 gpu_owner 服务名一致（同源于 served-model-name）且唯一时回填
    port_gpus: dict[int, list[int]] = {}
    for idx, (svc, port) in gpu_owner.items():
        port_gpus.setdefault(port, []).append(idx)
    for plist in port_gpus.values():
        plist.sort()
    name_gpus: dict[str, list[int]] = {}
    for svc, meta in svc_to_meta.items():
        if meta.get("port") == 0:
            name_gpus[svc] = meta["gpus"]
    for inst in vllm_instances:
        url = (inst.get("url") or "").rstrip("/")
        try:
            port = int(url.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            port = None
        if port in port_gpus:
            inst["gpus"] = list(port_gpus[port])
        elif inst.get("name") in name_gpus:
            inst["gpus"] = list(name_gpus[inst["name"]])
        else:
            inst["gpus"] = []

    # 回填 gpu.items[*].service
    for g in gpu_items:
        owner = gpu_owner.get(g["index"])
        g["service"] = owner[0] if owner else ""

    # 稳定排序：有端口的按端口，无端口的（非 vLLM）排末尾
    return sorted(svc_to_meta.values(), key=lambda m: (m.get("port", 1 << 30), m["service"]))
