from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

try:  # 可选的 Storm3 串口读取所需（仅 Linux）
    import fcntl
    import termios
except Exception:  # pragma: no cover
    fcntl = termios = None

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
    # v1.1.4：WAN 口径（只统计出口网卡）。NET_IFACE 可强制指定，留空则按默认路由自动识别。
    _NET_IFACE_ENV = os.environ.get("NET_IFACE", "").strip()
    _NET_IFACE_TTL = 60.0

    def __init__(self) -> None:
        self.previous_cpu: list[tuple[int, int]] | None = None
        self.previous_io: tuple[float, float, float] | None = None
        self.previous_net: tuple[float, float, float] | None = None
        self._net_iface: str | None = None
        self._net_iface_ts: float = 0.0
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

    def _wan_iface(self) -> str:
        """WAN 出口网卡名：默认路由所在接口（可用 env NET_IFACE 强制指定）。60s 缓存。"""
        if self._NET_IFACE_ENV:
            return self._NET_IFACE_ENV
        if self._net_iface is not None and time.monotonic() - self._net_iface_ts < self._NET_IFACE_TTL:
            return self._net_iface
        name = ""
        try:
            for line in (PROC / "net" / "route").read_text(errors="replace").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 8 and parts[1] == "00000000":      # Destination=0.0.0.0 → 默认路由
                    name = parts[0]
                    break
        except OSError:
            name = ""
        self._net_iface = name
        self._net_iface_ts = time.monotonic()
        return name

    def _network(self, now: float) -> tuple[float, float]:
        """只统计 **WAN 出口网卡** 的流量（ISP 配额口径）。

        2026-09-29：原实现把 /proc/net/dev 里除 lo 外的所有接口相加——本机 10G 内网互传、
        VPN(tun0) 与 docker 网桥全被算进"网络流量"，9/28 单日虚增 ~2.9TB（其实是机间互传，
        不进 ISP 配额；用户实测周期值 0.41TB 只有 WAN 口对得上）。
        取不到默认路由时退回「除 lo 与虚拟接口外全部相加」，避免直接变成 0。
        """
        wan = self._wan_iface()
        rx = tx = 0.0
        matched = False
        for line in _text(PROC / "net/dev").splitlines()[2:]:
            name, _, values = line.partition(":")
            name = name.strip()
            if name == "lo":
                continue
            parts = values.split()
            if len(parts) < 9:
                continue
            if wan:
                if name != wan:
                    continue
            elif name.startswith(("veth", "br-", "docker", "virbr", "tap", "tun")):
                continue        # 兜底：排除虚拟接口
            rx += _num(parts[0])
            tx += _num(parts[8])
            matched = True
        if wan and not matched:
            # 网卡名对不上（改过名/路由变化）→ 本轮沿用上一次读数，不把 0 当真值写进累计
            if self.previous_net:
                return 0.0, 0.0
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
            # v1.1.4：附上实际统计的网卡名（WAN 口径，便于核对 ISP 配额；不再是所有网卡相加）
            "network": {"rx_bps": rx_bps, "tx_bps": tx_bps, "iface": self._wan_iface() or "(全部非虚拟网卡)"},
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
        # v96.6: Storm3 机箱扇实时档位（ch1/ch2=G2 后排双扇、ch3=G1 前排，gpu-fan-control 温控驱动）
        # ——这三个通道的转速此前漏显示（widget 后 G2 用主板 IPMI SYS_FAN6/7、前 G1 硬编码 3450）
        storm_fans = self._storm_chassis_rpm()
        total_mem = sum(item["memory_total_mb"] for item in items)
        used_mem = sum(item["memory_used_mb"] for item in items)
        return {
            "count": len(items), "items": items,
            "storm_fans": storm_fans,
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

    # ---- BOSS Storm3（CH340 串口）风机盒（v97）：mapping 里的 "STORM:ch"（ch=1-8）----
    # 风暴盒不像 Corsair 有系统 hwmon，走串口指令读各通道档位(0-127)，无 tach 转速——
    # 满速按与 Corsair 一致的 3450 RPM 线性换算（用户确认：满速同 3450）：
    #   RPM = level/127 × FAN_MAX_RPM。串口与 gpu-fan-control(--storm) 共用，只读不写，
    #   并加 30s 缓存（SAMPLE_INTERVAL=2Hz 下最多 1/30s 打一次串口），失败静默保持 0。
    # 2026-09-29 修两处导致"GPU 详情转速不对 / 出现 0 转速"的缺陷：
    #  ① 读错盒子：机器上有两只 CH340 风暴盒——(a) GPU 9733 盒：gpu-fan-control 用
    #     /dev/ttyCH341USB0（沁园官方 ch341 驱动节点）驱动它，映射表里的 STORM:5/6/7/8
    #     全在它上面；(b) 昆仑4 CPU/GPU 风机盒：gpu-fan-control 的 STORM2_PORT=/dev/ttyUSB0。
    #     两个 ttyUSB 的枚举顺序会变：原来 /dev/ttyUSB0 正好是 GPU 盒，现在成了昆仑4 盒，
    #     于是 GPU3(bus26→STORM:5) 读成 0、GPU4/5/10 读到别人家的通道。
    #     改为按「与 gpu-fan-control 同款节点」动态解析（宿主机 /dev 已挂到 /host/dev）。
    #  ② 帧解析差一位：get_LEVELS 返回 0x4C('L') 包头 + 8 个通道字节（共 9 字节，每字节 = 档位×2）。
    #     原实现用 data[ch-1] 把包头当成了 ch1 → ch1 恒为 0x4C/2=38（这正是过去 storm g2
    #     一直显示 1032 RPM 不变的原因），且 ch8 被丢掉。gpu-fan-control 自己的写入回读用的是
    #     L[ch]（跳过包头），以后者为准。
    _STORM_PORT_ENV = os.environ.get("STORM_PORT", "")
    _STORM_LEVELS_TTL = 30.0
    _STORM_PORT_TTL = 60.0
    _storm_levels: dict[int, int] | None = None
    _storm_levels_ts: float = 0.0
    _storm_port: str | None = None
    _storm_port_ts: float = 0.0

    def _storm_port_candidates(self) -> list[str]:
        """候选串口（按优先级）：显式 STORM_PORT（可逗号分隔）→ 跟随官方 ch341 节点当前指向。
        若两个来源都拿不到（驱动没加载/链接缺失），才退回裸 ttyUSB 节点。
        —— 关键：只要能确定「官方节点指向谁」，就**不再**退回裸节点，
        否则一旦枚举顺序翻转，会静默读到另一只盒子（昆仑4 盒）的通道，显示看似正常却完全错的转速。"""
        cands: list[str] = []
        if self._STORM_PORT_ENV:
            cands += [p.strip() for p in self._STORM_PORT_ENV.split(",") if p.strip()]
        host_dev = Path(HOST_ROOT) / "dev"
        for link in (host_dev / "ttyCH341USB0", host_dev / "serial" / "by-id" / "usb-1a86_USB_Serial-if00-port0"):
            try:
                name = os.path.basename(os.path.realpath(link))
            except OSError:
                continue
            if name.startswith("ttyUSB"):
                cands.append("/dev/" + name)
        if not cands:
            cands = ["/dev/ttyUSB1", "/dev/ttyUSB0"]
        seen: set[str] = set()
        return [c for c in cands if not (c in seen or seen.add(c))]

    @staticmethod
    def _storm_parse_levels(data: bytes) -> dict[int, int]:
        """帧 → {ch: level}。帧格式：0x4C('L') 包头 + 8 个通道字节（每字节 = 档位×2），共 9 字节；
        兼容无包头的 8 字节老帧。不足/不合法返回 {}（调用方会换候选口或本轮不出数）。"""
        if len(data) >= 9 and data[0] == 0x4C:
            body, base = data, 1
        elif len(data) >= 8:
            body, base = data, 0
        else:
            return {}
        result: dict[int, int] = {}
        for ch in range(1, 9):
            if len(body) > base + ch - 1:
                lvl = body[base + ch - 1] // 2
                if 0 <= lvl <= 127:
                    result[ch] = lvl
        return result

    def _storm_read_port(self, port: str) -> dict[int, int]:
        """读单个候选串口，返回 {ch: level(0-127)}；打不开/帧不完整/无响应返回 {}。"""
        try:
            fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except OSError:
            return {}
        try:
            # 配置 2000000 baud 8N1 raw（无 cfsetispeed 时直接置 cflag 速率位）
            attrs = termios.tcgetattr(fd)
            baud = getattr(termios, "B2000000", 0x10000000)  # B2000000 cflag 宏（Linux）
            attrs[1] &= ~(termios.OPOST)          # raw output
            attrs[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN)  # raw input
            cflag = baud | termios.CS8 | termios.CREAD | termios.CLOCAL
            # 清除旧速率/字节位后写入
            attrs[0] = (attrs[0] & ~(termios.CBAUD | termios.CSIZE | termios.CSTOPB | termios.PARENB)) | cflag
            if hasattr(termios, "cfsetispeed"):
                termios.cfsetispeed(attrs, baud)
                termios.cfsetospeed(attrs, baud)
            attrs[6][termios.VMIN] = 0            # read 不阻塞
            attrs[6][termios.VTIME] = 2           # 0.2s 超时
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            fcntl.fcntl(fd, fcntl.F_SETFL, 0)     # 清非阻塞
            os.write(fd, b"get_LEVELS")
            time.sleep(0.3)
            data = b""
            try:
                while True:
                    chunk = os.read(fd, 64)
                    if not chunk:
                        break
                    data += chunk
                    if len(data) >= 9:
                        break
            except OSError:
                pass
        except OSError:
            return {}
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
        # 帧解析见 _storm_parse_levels（包头 + 8 通道，按 gpu-fan-control 的 L[ch] 口径）
        return self._storm_parse_levels(data)

    def _storm_levels_read(self) -> dict[int, int]:
        """读风暴盒 get_LEVELS，返回 {ch: level(0-127)}；串口不可用/失败返回 {}。"""
        if self._storm_levels is not None and time.monotonic() - self._storm_levels_ts < self._STORM_LEVELS_TTL:
            return self._storm_levels
        if fcntl is None or termios is None:
            return {}
        ports: list[str] = []
        if self._storm_port and time.monotonic() - self._storm_port_ts < self._STORM_PORT_TTL:
            ports.append(self._storm_port)          # 先在已知可用口上试
        ports += [p for p in self._storm_port_candidates() if p not in ports]
        for port in ports:
            result = self._storm_read_port(port)
            if result:
                if port != self._storm_port:
                    self._storm_port = port
                self._storm_port_ts = time.monotonic()
                self._storm_levels = result
                self._storm_levels_ts = time.monotonic()
                return result
        # 全部候选都失败：**不吃 30s 缓存**（否则一次串口抖动会让所有转速显示 0 达 30 秒）
        self._storm_levels = None
        return {}

    def _storm_chassis_rpm(self) -> dict[str, float]:
        """Storm3 机箱扇档位 → RPM（ch1/ch2=G2 后排双扇、ch3=G1 前排）。
        串口不可用时返回 {}（widget 回退主板 IPMI/硬编码）。"""
        levels = self._storm_levels_read()
        if not levels:
            return {}
        out: dict[str, float] = {}
        for key, ch in (("g2", 1), ("g2b", 2), ("g1", 3)):
            lv = levels.get(ch)
            if lv is None:
                continue
            out[key] = round(lv / 127 * self.FAN_MAX_RPM, 0)
        return out

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
            storm_level: int | None = None
            for dev, pin in entry:
                # v97：风暴盒 STORM:<ch>（BOSS Storm3 串口，ch=1-8，档位 0-127）——
                # 无 hwmon 无 tach，走串口读档位后换算 RPM（满速 3450 与 Corsair 一致）
                if dev == "STORM":
                    level = self._storm_levels_read().get(pin)
                    if level is None:
                        continue
                    storm_level = max(storm_level or 0, level)
                    continue
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
            if storm_level is not None:
                # STORM 档位(0-127) → RPM：满速 127 = FAN_MAX_RPM(3450)，与 Corsair 同口径
                it["fan_pwm"] = round(storm_level)
                it["fan_percent"] = round(storm_level / 127 * 100, 1)
                it["fan_rpm"] = round(storm_level / 127 * self.FAN_MAX_RPM, 0)
            elif pwm_best > 0:
                it["fan_pwm"] = round(pwm_best)
                it["fan_percent"] = round(pwm_best / 255 * 100, 1)
                it["fan_rpm"] = round(pwm_best / 255 * self.FAN_MAX_RPM, 0)

