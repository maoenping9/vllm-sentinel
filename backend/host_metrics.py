from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from .settings import HOST_ROOT


PROC = Path(HOST_ROOT) / "proc"
SYS = Path(HOST_ROOT) / "sys"


def _text(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return fallback


def _num(value: str | None, fallback: float = 0.0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return fallback


class HostCollector:
    def __init__(self) -> None:
        self.previous_cpu: list[tuple[int, int]] | None = None
        self.previous_io: tuple[float, float, float] | None = None
        self.previous_net: tuple[float, float, float] | None = None
        self.cpu_model, self.cores, self.threads = self._cpu_identity()

    def _cpu_identity(self) -> tuple[str, int, int]:
        info = _text(PROC / "cpuinfo")
        processors = [line for line in info.splitlines() if line.startswith("processor")]
        model = next((line.split(":", 1)[1].strip() for line in info.splitlines() if line.startswith("model name")), platform.processor() or "CPU")
        physical: set[tuple[str, str]] = set()
        package = core = "0"
        for line in info.splitlines() + [""]:
            if line.startswith("physical id"):
                package = line.split(":", 1)[1].strip()
            elif line.startswith("core id"):
                core = line.split(":", 1)[1].strip()
            elif not line.strip():
                physical.add((package, core))
        threads = len(processors) or (os.cpu_count() or 1)
        cores = len(physical) if len(physical) > 1 else max(1, threads // 2)
        return model, cores, threads

    def _cpu(self) -> tuple[float, list[float]]:
        rows: list[tuple[int, int]] = []
        for line in _text(PROC / "stat").splitlines():
            parts = line.split()
            if not parts or not parts[0].startswith("cpu"):
                break
            values = [int(value) for value in parts[1:]]
            idle = sum(values[3:5])
            rows.append((sum(values), idle))
        if not rows:
            return 0.0, []
        if not self.previous_cpu or len(self.previous_cpu) != len(rows):
            self.previous_cpu = rows
            return 0.0, [0.0] * max(0, len(rows) - 1)
        usage: list[float] = []
        for current, previous in zip(rows, self.previous_cpu):
            total_delta = current[0] - previous[0]
            idle_delta = current[1] - previous[1]
            usage.append(round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1) if total_delta else 0.0)
        self.previous_cpu = rows
        return usage[0], usage[1:]

    def _memory(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for line in _text(PROC / "meminfo").splitlines():
            key, _, raw = line.partition(":")
            values[key] = _num(raw.strip().split()[0]) * 1024
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", values.get("MemFree", 0))
        used = max(0, total - available)
        swap_total = values.get("SwapTotal", 0)
        swap_free = values.get("SwapFree", 0)
        return {
            "total": total, "used": used, "available": available,
            "percent": round(used / total * 100, 1) if total else 0,
            "swap_total": swap_total, "swap_used": max(0, swap_total - swap_free),
        }

    def _disk_io(self, now: float) -> tuple[float, float]:
        read_sectors = write_sectors = 0
        try:
            block_devices = {path.name for path in (SYS / "block").iterdir()}
        except OSError:
            block_devices = set()
        for line in _text(PROC / "diskstats").splitlines():
            parts = line.split()
            if len(parts) < 14:
                continue
            name = parts[2]
            if block_devices and name not in block_devices:
                continue
            if name.startswith(("loop", "ram", "dm-")):
                continue
            read_sectors += int(parts[5])
            write_sectors += int(parts[9])
        current = (now, read_sectors * 512.0, write_sectors * 512.0)
        if not self.previous_io:
            self.previous_io = current
            return 0.0, 0.0
        elapsed = max(0.01, now - self.previous_io[0])
        rates = (max(0, current[1] - self.previous_io[1]) / elapsed, max(0, current[2] - self.previous_io[2]) / elapsed)
        self.previous_io = current
        return rates

    def _network(self, now: float) -> tuple[float, float]:
        rx = tx = 0.0
        for line in _text(PROC / "net/dev").splitlines()[2:]:
            name, _, values = line.partition(":")
            if name.strip() == "lo":
                continue
            parts = values.split()
            if len(parts) >= 9:
                rx += _num(parts[0]); tx += _num(parts[8])
        current = (now, rx, tx)
        if not self.previous_net:
            self.previous_net = current
            return 0.0, 0.0
        elapsed = max(0.01, now - self.previous_net[0])
        rates = (max(0, rx - self.previous_net[1]) / elapsed, max(0, tx - self.previous_net[2]) / elapsed)
        self.previous_net = current
        return rates

    def _frequency(self) -> float:
        value = _num(_text(SYS / "devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").strip()) / 1000
        if value:
            return round(value)
        info = _text(PROC / "cpuinfo")
        mhz = [_num(line.split(":", 1)[1]) for line in info.splitlines() if line.startswith("cpu MHz")]
        return round(sum(mhz) / len(mhz)) if mhz else 0

    def collect(self) -> dict[str, Any]:
        now = time.time()
        cpu_usage, per_core = self._cpu()
        memory = self._memory()
        read_bps, write_bps = self._disk_io(now)
        rx_bps, tx_bps = self._network(now)
        try:
            stat = os.statvfs(HOST_ROOT)
            disk_total = stat.f_blocks * stat.f_frsize
            disk_free = stat.f_bavail * stat.f_frsize
        except OSError:
            disk_total = disk_free = 0
        load = [_num(value) for value in _text(PROC / "loadavg", "0 0 0").split()[:3]]
        uptime = _num(_text(PROC / "uptime").split()[0] if _text(PROC / "uptime") else "0")
        return {
            "hostname": socket.gethostname(), "os": _text(Path(HOST_ROOT) / "etc/os-release").split('PRETTY_NAME="')[-1].split('"')[0] or "Linux",
            "uptime": uptime,
            "cpu": {"model": self.cpu_model, "cores": self.cores, "threads": self.threads, "usage": cpu_usage, "per_core": per_core, "frequency_mhz": self._frequency(), "load": load},
            "memory": memory,
            "disk": {"total": disk_total, "used": max(0, disk_total - disk_free), "percent": round((disk_total-disk_free)/disk_total*100, 1) if disk_total else 0, "read_bps": read_bps, "write_bps": write_bps},
            "network": {"rx_bps": rx_bps, "tx_bps": tx_bps},
        }


class GpuCollector:
    FIELDS = ["index", "uuid", "name", "utilization.gpu", "utilization.memory", "memory.total", "memory.used", "memory.free", "temperature.gpu", "power.draw", "power.limit", "fan.speed", "clocks.current.sm", "clocks.current.memory", "pstate"]

    def _query(self, query: str) -> list[list[str]]:
        try:
            result = subprocess.run(
                ["nvidia-smi", f"--query-{query}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            return [[item.strip() for item in line.split(",")] for line in result.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError):
            return []

    def collect(self) -> dict[str, Any]:
        processes: dict[str, list[dict[str, Any]]] = {}
        for row in self._query("compute-apps=gpu_uuid,pid,process_name,used_memory"):
            if len(row) >= 4:
                processes.setdefault(row[0], []).append({"pid": int(_num(row[1])), "name": row[2].split("/")[-1], "memory_mb": _num(row[3])})
        items = []
        for row in self._query("gpu=" + ",".join(self.FIELDS)):
            if len(row) < len(self.FIELDS):
                continue
            value = dict(zip(self.FIELDS, row))
            total = _num(value["memory.total"]); used = _num(value["memory.used"])
            items.append({
                "index": int(_num(value["index"])), "uuid": value["uuid"], "name": value["name"],
                "utilization": _num(value["utilization.gpu"]), "memory_utilization": _num(value["utilization.memory"]),
                "memory_total_mb": total, "memory_used_mb": used, "memory_free_mb": _num(value["memory.free"]),
                "memory_percent": round(used / total * 100, 1) if total else 0,
                "temperature": _num(value["temperature.gpu"]), "power_w": _num(value["power.draw"]), "power_limit_w": _num(value["power.limit"]),
                "fan_percent": _num(value["fan.speed"]), "fan_pwm": 0, "fan_rpm": 0, "clock_sm_mhz": _num(value["clocks.current.sm"]), "clock_memory_mhz": _num(value["clocks.current.memory"]), "pstate": value["pstate"],
                "processes": processes.get(value["uuid"], []),
            })
        self._apply_corsair_fans(items)
        total_mem = sum(item["memory_total_mb"] for item in items)
        used_mem = sum(item["memory_used_mb"] for item in items)
        return {
            "count": len(items), "items": items,
            "utilization": round(sum(item["utilization"] for item in items) / len(items), 1) if items else 0,
            "memory_total_mb": total_mem, "memory_used_mb": used_mem, "memory_percent": round(used_mem/total_mem*100, 1) if total_mem else 0,
            "power_w": round(sum(item["power_w"] for item in items), 1), "max_temperature": max((item["temperature"] for item in items), default=0),
        }

    # ----- 海盗船 Commander Pro (corsair_cpro hwmon) GPU 风扇实时 PWM → 转速 -----
    # 矿卡 fan.speed(NVML) 恒 0 / 无 tach, 按 PWM 占空比线性反算：RPM = PWM/255 × 3450（满速 3450）。
    # 映射来自宿主机 /etc/gpu-mapping.conf，支持两种键格式（2026-09-12 现场版）：
    #   1. GPU<idx>=<dev>:<pin>[,...]           （GPU 索引版，dev=A/B/C/D 按序列号解析）
    #   2. <pci.bus_id>=<label>-<hub>-<port>:<pin> （总线版，如 00000000:21:00.0=1000D-3-4.3:4；
    #      dev 尾段 <port>（"4.3"）与该 Commander 的 HID_PHYS usb 端口段匹配定位 hwmon 目录）
    # GPU13(RTX3090Ti) 板载风扇自行控制，不在映射内，保持系统读数。
    FAN_MAX_RPM = 3450
    # v28：SERIAL 表补 E=0D05...2128（当前在线的第 3 台 Commander，USB 口 2.3）。
    # v27 只认 A/B/C/D 四台旧设备，标签 1000D-3-2.3 的二级查找错位到 D(=4.3 设备)、
    # 三级端口段兜底又错位到 2.3(=另一台) —— GPU4/7/8/11 的 PWM 全部读错设备。
    # 补 E 后二级查找按序列号精确定位（与温控软件 gpu-fan-control 同路径），13/13 与实测定 位一致。
    _CORS_SERIAL = {"A": "0A0500CC94300712", "B": "150500B6931C0E0D", "C": "0505037A2429241F", "D": "0E05037A24291610", "E": "0D05037A24292128"}
    # v27：dev 标签 → 序列号（与温控软件 gpu-fan-control 的 SERIAL 表一致）。
    # conf 的 dev=1000D-3-4.2 这类标签按此表解析到序列号再定位 hwmon（温控软件写 pwm 的同一设备），
    # 解决 4.2 口 USB 端口段未枚举（HID_PHYS 只有 2.2/2.3/4.3）导致后端读不到 pwm 的问题。
    _CORS_LABEL_SERIAL = {
        "1000D-3-2.3": "0D05037A24292128",
        "1000D-3-4.2": "0505037A2429241F",
        "1000D-3-4.3": "0E05037A24291610",
    }
    _cors_map: dict[int, list[tuple[str, int]]] | None = None
    _cors_hwmon: dict[str, Path] | None = None
    _cors_ports: dict[str, Path] | None = None
    # v95：GPU 拓扑变动 / gpu-mapping.conf 热更新后，运行中服务的进程级缓存
    # 永不刷新，导致新映射的 GPU3/GPU6 风扇恒显示 0（2026-09-20 事故）。
    # 缓存加 TTL，过期自动重建，配置与拓扑变更 60s 内自愈，无需重启服务。
    _CACHE_TTL = 60.0
    _cache_ts: dict[str, float] = {}

    def _cache_fresh(self, key: str) -> bool:
        return (time.monotonic() - self._cache_ts.get(key, 0.0)) < self._CACHE_TTL

    def _cache_mark(self, key: str) -> None:
        self._cache_ts[key] = time.monotonic()

    def _cors_port_dirs(self) -> dict[str, Path]:
        """Commander hubport（如 "4.3"）→ hwmon 目录，按 HID_PHYS usb 端口段解析。"""
        if self._cors_ports is not None and self._cache_fresh("ports"):
            return self._cors_ports
        result: dict[str, Path] = {}
        try:
            candidates = list((SYS / "class" / "hwmon").glob("hwmon*"))
        except OSError:
            candidates = []
        for d in candidates:
            if _text(d / "name").strip() != "corsaircpro":
                continue
            uevent = _text(d / "device" / "uevent")
            for line in uevent.splitlines():
                if line.startswith("HID_PHYS="):
                    seg = line.split("=", 1)[1].strip()
                    # usb-0000:68:00.3-2.3/input0 → "2.3"
                    port_seg = seg.rsplit("/", 1)[0].rsplit("-", 1)[-1]
                    if port_seg:
                        result[port_seg] = d
                    break
        self._cors_ports = result
        self._cache_mark("ports")
        return result

    def _cors_hwmon_dirs(self) -> dict[str, Path]:
        if self._cors_hwmon is not None and self._cache_fresh("hwmon"):
            return self._cors_hwmon
        result: dict[str, Path] = {}
        try:
            candidates = list((SYS / "class" / "hwmon").glob("hwmon*"))
        except OSError:
            candidates = []
        for code, serial in self._CORS_SERIAL.items():
            for d in candidates:
                if _text(d / "name").strip() != "corsaircpro":
                    continue
                if "HID_UNIQ=" + serial in _text(d / "device" / "uevent"):
                    result[code] = d
                    break
        self._cors_hwmon = result
        self._cache_mark("hwmon")
        return result

    def _cors_mapping(self) -> dict[int, list[tuple[str, int]]]:
        if self._cors_map is not None and self._cache_fresh("cors_map"):
            return self._cors_map
        mapping: dict[int, list[tuple[str, int]]] = {}
        p = Path(HOST_ROOT) / "etc" / "gpu-mapping.conf"
        for line in _text(p).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            idx: int | None = None
            if key.startswith("GPU"):
                # GPU 索引版: GPU13=C:1,C:2
                try:
                    idx = int(key[3:])
                except ValueError:
                    continue
            elif key.count(":") == 2:
                # 总线版: 00000000:21:00.0=1000D-3-4.3:4 → 按 NVML pci.bus_id 对应 GPU 索引
                idx = self._gpu_index_by_bus(key)
                if idx is None:
                    continue
            else:
                continue
            pairs: list[tuple[str, int]] = []
            for part in value.split(","):
                part = part.strip()
                if not part or ":" not in part:
                    continue
                dev, _, pin = part.partition(":")
                pin = pin.split()[0].strip()  # 去掉行内注释残留
                try:
                    pin_i = int(pin)
                except ValueError:
                    continue
                if dev and pin_i > 0:
                    pairs.append((dev, pin_i))
            if idx is not None and pairs:
                mapping[idx] = pairs
        self._cors_map = mapping
        self._cache_mark("cors_map")
        return mapping

    _gpu_bus_map: dict[str, int] | None = None

    def _gpu_index_by_bus(self, bus_id: str) -> int | None:
        """NVML pci.bus_id（00000000:21:00.0）→ GPU 索引；查不到返回 None。"""
        if self._gpu_bus_map is None or not self._cache_fresh("bus_map"):
            bus_map: dict[str, int] = {}
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=index,pci.bus_id", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5,
                )
                for row in result.stdout.splitlines():
                    parts = [item.strip() for item in row.split(",")]
                    if len(parts) >= 2:
                        try:
                            bus_map[parts[1].lower()] = int(parts[0])
                        except ValueError:
                            continue
            except (OSError, subprocess.SubprocessError):
                return None
            self._gpu_bus_map = bus_map
            self._cache_mark("bus_map")
        return self._gpu_bus_map.get(bus_id.strip().lower())

    def _apply_corsair_fans(self, items: list[dict[str, Any]]) -> None:
        hw = self._cors_hwmon_dirs()
        ports = self._cors_port_dirs()
        for it in items:
            entry = self._cors_mapping().get(it["index"])
            if not entry:
                continue
            pwm_best = 0
            for dev, pin in entry:
                # v27 查找顺序：①序列号字母（A/B/C/D）→ ②dev 标签（1000D-3-X.Y）按
                #   _CORS_LABEL_SERIAL 解析序列号再定位 hwmon（温控软件写 pwm 的同一设备）
                #   → ③HID_PHYS usb 端口段（兜底）
                hwdir = hw.get(dev)
                if not hwdir:
                    serial = self._CORS_LABEL_SERIAL.get(dev)
                    if serial:
                        for code, s in self._CORS_SERIAL.items():
                            if s == serial:
                                hwdir = hw.get(code)
                                break
                if not hwdir:
                    # 总线版 dev：尾段 <port>（如 "4.3"）按 HID_PHYS 端口段定位
                    port_seg = dev.rsplit("-", 1)[-1]
                    hwdir = ports.get(port_seg)
                if not hwdir:
                    continue
                pwm = _num(_text(hwdir / f"pwm{pin}"))
                if pwm > pwm_best:
                    pwm_best = pwm
            if pwm_best > 0:
                it["fan_pwm"] = round(pwm_best)
                it["fan_percent"] = round(pwm_best / 255 * 100, 1)
                it["fan_rpm"] = round(pwm_best / 255 * self.FAN_MAX_RPM, 0)

