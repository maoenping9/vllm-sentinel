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
                "fan_percent": _num(value["fan.speed"]), "clock_sm_mhz": _num(value["clocks.current.sm"]), "clock_memory_mhz": _num(value["clocks.current.memory"]), "pstate": value["pstate"],
                "processes": processes.get(value["uuid"], []),
            })
        total_mem = sum(item["memory_total_mb"] for item in items)
        used_mem = sum(item["memory_used_mb"] for item in items)
        return {
            "count": len(items), "items": items,
            "utilization": round(sum(item["utilization"] for item in items) / len(items), 1) if items else 0,
            "memory_total_mb": total_mem, "memory_used_mb": used_mem, "memory_percent": round(used_mem/total_mem*100, 1) if total_mem else 0,
            "power_w": round(sum(item["power_w"] for item in items), 1), "max_temperature": max((item["temperature"] for item in items), default=0),
        }
