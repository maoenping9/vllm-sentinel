"""/api/summary —— 桌面小组件专用聚合端点（Windows Rainmeter / 未来安卓端用）。

设计目标（2026-09-30，与 Mac Übersicht 组件 v97.x 对齐）：
  1. **单请求**：state + energy + 流量周期合并成一个 JSON，弱隧道（EasyTier 中继
     430~670ms）下握手次数减半——v97.3 断联治理的核心结论。
  2. **展示语义全在服务端算好**：模型归一（canonModel）、短名、配色、排序、三态
     （在线/启动中/离线）、进度条分母与色调档位（tone 0/1/2）、显示字符串。
     客户端只做"取字段 → 画"，不再在每个端重写一份聚合逻辑（Mac 组件 v96.7
     模型重复行、Web 前端 CANON 缺 DSV4.1 都是"每端一份逻辑"漂移出来的 bug）。
  3. **体积极小**：全响应 ~1.2KB（gzip 后几百字节），对比 /api/state?light=1 的 20KB。

注意：不改动 /api/state（Mac 组件与 Web 控制台继续用旧契约），本模块是纯增量。
"""
from __future__ import annotations

import re
import time
from typing import Any

HOT_TEMP = 75.0            # 与 Mac 组件同口径：>= 此温度红色
OTHER_W = 200.0            # 整机功耗估算的"其他"补偿值，与组件一致
MONTH_BUDGET = 500.0       # 本月电费预算（元），组件 v61 定稿
YEAR_BUDGET = 6000.0       # 本年电费预算（元）
NET_TOTAL_TB = 1.5         # 流量周期总配额
NET_WARN_TB = 1.0          # 达到即红色告警
STALE_NET_MS = 40000       # 网络 EMA 沿用旧值时限（组件 STALE_GRACE_MS 同值）

MODEL_COLORS = ["#4e9cff", "#34d399", "#f59e0b", "#a78bfa", "#f472b6", "#22d3ee"]

# 与 Mac 组件 index.jsx v96.9 完全一致的固定配色表
MODEL_COLOR_MAP = {
    "DeepSeek-V4-Flash-Exp": "#4e9cff",
    "DeepSeek-V4.1-Flash": "#4e9cff",
    "GLM-5.3-Flash": "#34d399",
    "Qwen3.8-27B-W4A16": "#f59e0b",
    "WeMM-Embedding-9B": "#a78bfa",
    "Meeting-ASR": "#f472b6",
    "MiniMax-H3": "#22d3ee",
    "WeMM-Embedding-9B-CPU": "#facc15",
    "Qwen3-Embedding-0.6B": "#60a5fa",
    "CosyVoice-TTS": "#fb923c",
    "FishSpeech-TTS": "#4ade80",
    "GPT-SoVITS-TTS": "#c084fc",
    "Whisper-ASR": "#2dd4bf",
    "Unlimited-OCR": "#e879f9",
}

SHORT_NAMES = {
    "GLM-5.3-Flash": "GLM-5.3",
    "DeepSeek-V4-Flash-Exp": "DSV4-V",
    "DeepSeek-V4.1-Flash": "DSV4.1",
    "Qwen3.8-27B-W4A16": "Qwen3.8",
    "WeMM-Embedding-9B": "EB-9B",
    "MiniMax-H3": "MiniMax-H3",
    "Qwen3.8-27B-INT8": "Qwen3.8-INT8",
    "Qwen3.8-Flash-Next": "Qwen3.8-Next",
    "DSV4-Flash-0731": "DSV4-V",
    "DSV4-Flash-Exp": "DSV4-V",
    "DeepSeek-V4-Flash-0731": "DSV4-V",
    "qwen3.8-27b": "Qwen3.8",
    "Meeting-ASR": "Meet-ASR",
    "WeMM-Embedding-9B-CPU": "EB-CPU",
    "Qwen3-Embedding-0.6B": "Emb-0.6B",
    "CosyVoice-TTS": "CosyTTS",
    "FishSpeech-TTS": "FishTTS",
    "GPT-SoVITS-TTS": "SoVITS",
    "Whisper-ASR": "Whisper",
    "Unlimited-OCR": "OCR",
}

# canonModel 规则（组件 v96.8/v96.9 定稿：精确匹配排在通用前缀之前）
_CANON_RULES = [
    (re.compile(r"^qwen3\.8-27b-int8", re.I), "Qwen3.8-27B-INT8"),
    (re.compile(r"^qwen3\.8-flash[\s_-]?next", re.I), "Qwen3.8-Flash-Next"),
    (re.compile(r"^qwen3\.8", re.I), "Qwen3.8-27B-W4A16"),
    (re.compile(r"^deepseek[-_ ]?v4\.1", re.I), "DeepSeek-V4.1-Flash"),
    (re.compile(r"^dsv4", re.I), "DeepSeek-V4-Flash-Exp"),
    (re.compile(r"^deepseek[-_ ]?v4", re.I), "DeepSeek-V4-Flash-Exp"),
    (re.compile(r"^glm", re.I), "GLM-5.3-Flash"),
    (re.compile(r"^wemm", re.I), "WeMM-Embedding-9B"),
    (re.compile(r"^unlimited[-_ ]?ocr", re.I), "Unlimited-OCR"),
    (re.compile(r"^minimax", re.I), "MiniMax-H3"),
]


def canon_model(raw: str | None) -> str:
    r = raw or ""
    for pattern, canon in _CANON_RULES:
        if pattern.search(r):
            return canon
    return r


def model_color(name: str) -> str:
    if name in MODEL_COLOR_MAP:
        return MODEL_COLOR_MAP[name]
    h = 0
    for i, ch in enumerate(name or ""):
        h = (h + ord(ch) * (i + 7)) % 997
    return MODEL_COLORS[h % len(MODEL_COLORS)]


def color_index(name: str) -> int:
    """Rainmeter 只能整样式换色（StyleName 动态），所以给客户端返回 0..5 调色板序号。
    MAP 里不在 6 色调色板内的次级色，退到调色板内同色相近似或哈希位。"""
    hexc = model_color(name)
    if hexc in MODEL_COLORS:
        return MODEL_COLORS.index(hexc)
    h = 0
    for i, ch in enumerate(name or ""):
        h = (h + ord(ch) * (i + 7)) % 997
    return h % len(MODEL_COLORS)


def _num(v: Any, d: int = 0) -> str:
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return f"{0.0:.{d}f}"


def _tone(value: Any, warn: Any, crit: Any) -> int:
    """传感器色调档位：0 正常 / 1 警告(黄) / 2 危险(红)，门槛优先传感器自带。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0
    if crit is None or crit == "":
        crit = (warn or 0) + 10
    if v >= float(crit):
        return 2
    if warn is not None and warn != "" and v >= float(warn):
        return 1
    return 0


def _sensor_tone(sensor: dict[str, Any] | None) -> int:
    if not sensor or sensor.get("value") is None:
        return 0
    warn = sensor.get("upper_warning")
    crit = sensor.get("upper_critical")
    return _tone(sensor.get("value"), warn if warn is not None else HOT_TEMP, crit)


def _pick_sensor(temps: list[dict[str, Any]], name: str, prefix: str) -> dict[str, Any] | None:
    for t in temps:
        if t.get("name") == name:
            return t
    for t in temps:
        if str(t.get("name", "")).startswith(prefix):
            return t
    return None


_net_ema: tuple[float, float] | None = None   # (ema MB/s, ts)：与组件 v96.2 同口径的毛刺平滑
_net_ema_at: float = 0.0

# Rainmeter 用固定 Meter 池渲染（无循环语法），服务端把数组补齐到固定槽位，
# 空行全字段置空/0，客户端按同一起点排版即可——比让每个客户端自定行数简单可靠。
MODEL_SLOTS = 8
GPU_SLOTS = 16


def _net_mb_smooth(rx_tx_bps: float) -> float:
    global _net_ema, _net_ema_at
    now = time.time()
    mb = rx_tx_bps / 1048576.0
    if _net_ema is None or now - _net_ema_at > STALE_NET_MS / 1000.0:
        _net_ema = mb
    else:
        _net_ema = _net_ema * 0.7 + mb * 0.3
    _net_ema_at = now
    return _net_ema


def build_model_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    """模型服务行：与组件 v96.7/v97.4 语义完全一致（byCanon 按规范名去重合并，
    在线口径——vLLM 行只认 vLLM 就绪态；纯小模型以"进程在跑"为证据）。"""
    by: dict[str, dict[str, Any]] = {}

    def get_row(canon: str) -> dict[str, Any]:
        return by.setdefault(canon, {
            "name": canon, "count": 0, "online": 0, "starting": 0, "tok": 0.0,
            "kv": 0.0, "kvN": 0, "gpus": [], "from_vllm": False, "from_gpu": False,
            "from_cpu": False, "gpu_present": False, "cpu_present": False,
        })

    def merge_gpus(row: dict[str, Any], gpus: list[int] | None) -> None:
        for gi in gpus or []:
            if gi not in row["gpus"]:
                row["gpus"].append(gi)

    for inst in (state.get("vllm") or {}).get("instances") or []:
        raw = (inst.get("models") or [None])[0] or inst.get("name")
        row = get_row(canon_model(raw))
        row["count"] += 1
        row["from_vllm"] = True
        st = inst.get("state") or ("online" if inst.get("online") else "offline")
        if st == "online":
            row["online"] += 1
            try:
                row["tok"] += float(inst.get("generation_tokens_per_second") or 0)
            except (TypeError, ValueError):
                pass
            try:
                row["kv"] += float(inst.get("kv_cache_percent") or 0)
                row["kvN"] += 1
            except (TypeError, ValueError):
                pass
        elif st == "starting":
            row["starting"] += 1
        merge_gpus(row, inst.get("gpus"))

    for gm in state.get("gpu_map") or []:
        row = get_row(canon_model(gm.get("service")))
        row["count"] += 1
        row["from_gpu"] = True
        row["gpu_present"] = True
        merge_gpus(row, gm.get("gpus"))

    for sm in state.get("small_models") or []:
        row = get_row(canon_model(sm.get("name")))
        row["count"] += 1
        row["from_cpu"] = True
        row["cpu_present"] = True

    items = {g.get("index"): g for g in (state.get("gpu") or {}).get("items") or []}
    rows = []
    for canon, r in by.items():
        r["gpus"].sort()
        online = r["online"] > 0 if r["from_vllm"] else (r["online"] > 0 or r["gpu_present"] or r["cpu_present"])
        starting = (not online) and r["starting"] > 0
        gpu_str = ",".join(str(g) for g in r["gpus"]) or "-"
        if r["from_cpu"]:
            value = "CPU · 进程在跑"
        elif (not r["from_vllm"]) and r["from_gpu"]:
            used = sum(float((items.get(g) or {}).get("memory_used_mb") or 0) for g in r["gpus"])
            value = f"GPU {gpu_str} · {used / 1024:.1f}G 显存"
        elif online:
            kv = (r["kv"] / r["kvN"]) if r["kvN"] else 0.0
            value = f"GPU {gpu_str} · {r['tok']:.1f}t/s · K{kv:.0f}%"
        elif starting:
            value = "引擎启动中 · 等待就绪…"
        else:
            value = "--"
        # stIdx：0 在线(绿) / 1 启动中(黄) / 2 离线(红)——Rainmeter 只能整样式切换，直接给档位
        rows.append({
            "name": canon,
            "short": SHORT_NAMES.get(canon, canon[:7]),
            "online": online,
            "starting": starting,
            "value": value,
            "cIdx": color_index(canon),
            "stIdx": 0 if online else (1 if starting else 2),
        })
    rows.sort(key=lambda x: (-int(x["online"]), -int(x["starting"]), x["name"]))
    rows = rows[:MODEL_SLOTS]
    while len(rows) < MODEL_SLOTS:
        rows.append({"name": "", "short": "", "online": False, "starting": False, "value": "", "cIdx": 6, "stIdx": 3})
    return rows


def build_gpu_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    """GPU 阵列行：负载×0.7 + 温度×0.3 降序（组件同款排序）；缺失槽位补"驱动失联"。"""
    items = list((state.get("gpu") or {}).get("items") or [])
    count = max(len(items), 14)
    seen = {g.get("index") for g in items}
    rows_src = list(items)
    for i in range(count):
        if i not in seen:
            rows_src.append({"index": i, "_missing": True, "utilization": 0, "temperature": 0})

    insts = (state.get("vllm") or {}).get("instances") or []

    def model_of(g: dict[str, Any]) -> dict[str, Any] | None:
        svc = g.get("service") or ""
        if not svc:
            return None
        canon = canon_model(svc)
        online, starting = True, False
        inst = next((i for i in insts if i.get("name") == svc or svc in (i.get("models") or []) or canon in (i.get("models") or [])), None)
        if inst:
            st = inst.get("state") or ("online" if inst.get("online") else "offline")
            online = st == "online"
            starting = st == "starting"
        else:
            online = float(g.get("memory_used_mb") or 0) > 1024
        return {"model": canon, "online": online, "starting": starting}

    def gpu_score(g: dict[str, Any]) -> float:
        if g.get("_missing"):
            return 0.0
        return float(g.get("utilization") or 0) * 0.7 + float(g.get("temperature") or 0) * 0.3

    rows_src.sort(key=gpu_score, reverse=True)   # 与组件同口径：负载×0.7+温度×0.3 降序，失联卡沉底
    out = []
    for g in rows_src:
        missing = bool(g.get("_missing"))
        m = model_of(g)
        model = m["model"] if m else ""
        idle = (not missing) and not m
        util = float(g.get("utilization") or 0)
        temp = float(g.get("temperature") or 0)
        if missing:
            label = f"GPU {g['index']}"
            meta = "驱动失联"
        else:
            short = SHORT_NAMES.get(model, model[:7]) if model else ""
            label = f"GPU {g['index']}·{short}" if model else f"GPU {g['index']}·空闲"
            meta = f"{temp:.0f}°C · {_num(g.get('fan_rpm'), 0)} RPM"
        # 条色样式：0-5 模型调色板 / 6 空闲灰 / 7 高温红（高温优先，与组件 gpuBarHot 一致）
        if temp >= HOT_TEMP:
            bar_tone = 7
        elif idle or missing:
            bar_tone = 6
        else:
            bar_tone = color_index(model)
        out.append({
            "idx": g["index"], "label": label, "meta": meta,
            "memG": _num(float(g.get("memory_used_mb") or 0) / 1024.0, 1) + "G",
            "util": _num(util, 0), "temp": _num(temp, 0),
            "tone": 2 if (missing or temp >= HOT_TEMP) else 0,
            "bar": bar_tone,
            # mIdx：0 正常灰 / 1 红（失联或高温）/ 2 空行隐藏
            "mIdx": 1 if (missing or temp >= HOT_TEMP) else 0,
        })
    rows_out = out[:GPU_SLOTS]
    while len(rows_out) < GPU_SLOTS:
        rows_out.append({"idx": -1, "label": "", "meta": "", "memG": "", "util": "0", "temp": "0", "tone": 0, "bar": 8, "mIdx": 2})
    return rows_out


def build_summary(state: dict[str, Any], energy: dict[str, Any]) -> dict[str, Any]:
    host = state.get("host") or {}
    gpu = state.get("gpu") or {}
    bmc = state.get("bmc") or {}
    temps = bmc.get("temperatures") or []
    cpu = host.get("cpu") or {}
    mem = host.get("memory") or {}
    net = host.get("network") or {}
    disk = host.get("disk") or {}

    cpu_sensor = _pick_sensor(temps, "CPU0_TEMP", "CPU")
    dimm0 = _pick_sensor(temps, "DIMMG0_TEMP", "DIMM")
    dimm1 = None
    for t in temps:
        if t.get("name") == "DIMMG1_TEMP" or (str(t.get("name", "")).startswith("DIMM") and t is not dimm0):
            dimm1 = t
            break
    vr0 = _pick_sensor(temps, "VR_DIMMG0_TEMP", "VR_DIMM")
    vr1 = None
    for t in temps:
        if t.get("name") == "VR_DIMMG1_TEMP" or (str(t.get("name", "")).startswith("VR_DIMM") and t is not vr0):
            vr1 = t
            break

    per_core = cpu.get("per_core") or []
    gpu_w = float(gpu.get("power_w") or 0)
    total_w = gpu_w + OTHER_W

    cost_month = float(energy.get("cost_month") or 0)
    cost_year = float(energy.get("cost_year") or 0)
    net_tb = float(energy.get("net_cycle_bytes") or 0) / 1e12
    base_gb = float(energy.get("net_cycle_base_bytes") or 0) / 1e9

    def bar_tone(value: float, budget: float) -> int:
        return 1 if value > budget * 0.9 else 0

    def fmt(v: Any, d: int) -> str:
        try:
            return f"{float(v):.{d}f}"
        except (TypeError, ValueError):
            return "--"

    net_mb = _net_mb_smooth(float(net.get("rx_bps") or 0) + float(net.get("tx_bps") or 0))
    dimm_pair = "0 " + (f"{dimm0['value']:.0f}°C" if dimm0 and dimm0.get("value") is not None else "--") + \
        " · 1 " + (f"{dimm1['value']:.0f}°C" if dimm1 and dimm1.get("value") is not None else "--")
    vr_pair = "0 " + (f"{vr0['value']:.0f}°C" if vr0 and vr0.get("value") is not None else "--") + \
        " · 1 " + (f"{vr1['value']:.0f}°C" if vr1 and vr1.get("value") is not None else "--")

    return {
        "status": "ok" if state.get("status") == "ok" else str(state.get("status") or "degraded"),
        "ts": int(state.get("timestamp") or time.time()),
        "host": host.get("hostname") or "your-host",
        "models": build_model_rows(state),
        "gpus": build_gpu_rows(state),
        "gpuW": _num(gpu_w, 0),
        "totalW": _num(total_w, 1),
        "cpuUse": _num(cpu.get("usage"), 1),
        "memUse": _num(mem.get("percent"), 1),
        "cpuTemp": f"{cpu_sensor['value']:.0f}°C" if cpu_sensor and cpu_sensor.get("value") is not None else "--",
        "cpuTone": _sensor_tone(cpu_sensor),
        "dimm": dimm_pair,
        "dimmTone": max(_sensor_tone(dimm0), _sensor_tone(dimm1)),
        "vr": vr_pair,
        "vrTone": max(_sensor_tone(vr0), _sensor_tone(vr1)),
        "maxCore": _num(max(per_core) if per_core else 0, 1),
        "threads": len(per_core),
        "freqM": _num(cpu.get("frequency_mhz"), 0),
        "costM": _num(cost_month, 2), "costY": _num(cost_year, 2),
        "costEst": _num(energy.get("cost_month_est"), 2),
        "costMTone": bar_tone(cost_month, MONTH_BUDGET),
        "costYTone": bar_tone(cost_year, YEAR_BUDGET),
        "costMBudget": MONTH_BUDGET, "costYBudget": YEAR_BUDGET,
        "netTB": _num(net_tb, 2), "netWarn": 1 if net_tb >= NET_WARN_TB else 0,
        "netBaseGb": _num(base_gb, 0), "netTotalTB": NET_TOTAL_TB,
        "netMB": _num(net_mb, 1),
        "diskMB": _num(float(disk.get("write_bps") or 0) / 1048576.0, 1),
        "iface": net.get("iface") or "?",
        "refreshS": 6,
    }
