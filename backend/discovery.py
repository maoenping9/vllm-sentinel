from __future__ import annotations

"""运行中 vLLM 实例的自动发现。

约束：vllm-sentinel 容器非 root 运行、read_only、cap_drop ALL，
只能读 /host/proc/<pid>/cmdline（读不到 environ）。
因此扫描所有进程的 cmdline，命中 `vllm` + `--port <N>` 的主服务进程即视为一个 vLLM 实例，
并从中提取 `--served-model-name`（无则取 `serve <model>` 的模型目录名）。
配合 settings.VllmTarget，把未在 .env 里配置、但实际在跑的模型（如 GLM-5.3-Flash）也纳入采集。

v93 兜底（docker 化 vLLM）：新模型跑在 docker 容器里（容器内 uvicorn 默认 8000、
cmdline 无 --port 旗标），宿主机 docker-proxy 把 <host-port> 转到 <container-ip>:8000——
--port 正则匹配不到 → 实例被跳过（用户：新模型上线没显示）。修复：
  ① 读 vLLM 进程 netns 的 /proc/net/tcp(+tcp6)，取 LISTEN 的非临时端口 + 本地 IP
    （procfs 在 read_only+cap_drop 下仍可读）；
  ② 扫 docker-proxy 进程 cmdline，建 "container_ip:container_port" → 宿主端口 映射；
  ③ vLLM netns 监听地址命中映射 → URL 用宿主侧可达的 host-port；
    无映射（本机直连场景）→ 退回容器内端口。
"""

import re
from pathlib import Path

from .settings import HOST_ROOT

PROC = Path(HOST_ROOT) / "proc"
EPHEMERAL_MIN = 32768  # Linux 临时端口范围下限（netns tcp 里大量 ephemeral LISTEN 需排除）


def _cmdline(pid: str) -> str:
    try:
        raw = (PROC / pid / "cmdline").read_bytes()
        return raw.replace(b"\x00", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def _netns_listen(proc_entry: Path) -> list[tuple[str, int]]:
    """v93：读进程 netns 的 /proc/net/tcp(+tcp6)，返回 LISTEN 的 (本地IP, 端口) 列表。

    容器化 vLLM 的 uvicorn 在容器 netns 里监听（默认 8000），cmdline 无 --port 旗标；
    /proc/<pid>/net/tcp 在 read_only+cap_drop 下仍可读（procfs 允许），据此拿到
    容器内真实监听地址。只保留非临时端口（< EPHEMERAL_MIN）。
    """
    out: list[tuple[str, int]] = []
    for fname in ("net/tcp", "net/tcp6"):
        try:
            rows = (proc_entry / fname).read_text().splitlines()[1:]
        except OSError:
            continue
        for r in rows:
            f = r.split()
            if len(f) < 4 or f[3] != "0A":  # 0A = TCP_LISTEN
                continue
            la = f[1]
            addr_hex, port_hex = la.split(":")
            port = int(port_hex, 16)
            if port <= 0 or port >= EPHEMERAL_MIN:
                continue
            # 十六进制小端 IPv4 → 点分十进制
            if len(addr_hex) == 8:
                b = bytes.fromhex(addr_hex)
                addr = ".".join(str(x) for x in reversed(b))
            else:
                addr = ":".join(  # tcp6 简化展示
                    addr_hex[i:i + 4] for i in range(0, len(addr_hex), 4)
                )
            out.append((addr, port))
    return out


def _docker_proxy_map() -> dict[str, int]:
    """v93：扫 docker-proxy 进程 cmdline，建 "container_ip:container_port" → 宿主端口 映射。

    容器内 8000 从宿主机 127.0.0.1:8000 不可达——宿主侧 URL 必须用 docker-proxy
    的 -host-port 映射端口，靠 -container-ip/-container-port 与 vLLM netns 监听地址关联。
    """
    mapping: dict[str, int] = {}
    try:
        for entry in PROC.glob("[0-9]*"):
            if not entry.name.isdigit():
                continue
            cmd = _cmdline(entry.name)
            if "docker-proxy" not in cmd:
                continue
            hp = re.search(r"-host-port\s+(\d+)", cmd)
            cip = re.search(r"-container-ip\s+(\S+)", cmd)
            cp = re.search(r"-container-port\s+(\d+)", cmd)
            if not (hp and cip and cp):
                continue
            mapping[f"{cip.group(1)}:{cp.group(1)}"] = int(hp.group(1))
    except Exception:
        return {}
    return mapping


def discover_vllm_targets() -> list[dict[str, object]]:
    """返回当前运行中的 vLLM 实例：[{name, port, url}, ...]（按端口去重、升序）。"""
    out: list[dict[str, object]] = []
    proxy_map: dict[str, int] = {}
    try:
        proxy_map = _docker_proxy_map()
        for entry in PROC.glob("[0-9]*"):
            pid = entry.name
            if not pid.isdigit():
                continue
            cmd = _cmdline(pid)
            if not cmd or "vllm" not in cmd.lower():
                continue
            # v93 修正：VLLM::Worker_PP / VLLM::EngineCore 是内部 RPC 进程（cmdline
            # 就是进程名，无 serve/--model 旗标），不是主服务——跳过，否则按 netns
            # 兜底会生成 vllm-28028 这类假实例（worker 内部口 28028）
            if cmd.startswith("VLLM::") or cmd.startswith("vllm::"):
                continue
            # v93 修正：路径含 conda 环境名 vllm-g 的非推理服务（embed-wemm-mm-gpu.py、
            # open-mem-proxy.py）也会命中 "vllm"——只认 vLLM 推理主服务的特征旗标
            # （vllm.entrypoints api_server / cli.main serve / vllm serve）
            if not re.search(r"vllm\.entrypoints|\bvllm\s+serve\b|-m\s+vllm\b", cmd):
                continue
            m = re.search(r"--port\s+(\d+)", cmd)
            if m:
                port = int(m.group(1))
                if port <= 0:
                    continue
                url = f"http://127.0.0.1:{port}"
            else:
                # v93 兜底：容器化 vLLM（cmdline 含 vllm 但无 --port）——
                # 读该进程 netns 的 LISTEN 端口 + 本地 IP，与 docker-proxy 映射表
                # 关联出宿主侧可达 URL；无映射时退回容器内端口（本机直连场景）
                listens = _netns_listen(entry)
                if not listens:
                    continue
                picked: tuple[str, int] | None = None
                for addr, lp in listens:
                    # 精确匹配（netns 监听具体容器 IP）或通配匹配（uvicorn 绑 0.0.0.0
                    # 时按端口找任一 container-ip 的该端口映射）
                    if f"{addr}:{lp}" in proxy_map or (
                        addr in {"0.0.0.0", "::"}
                        and any(k.endswith(f":{lp}") for k in proxy_map)
                    ):
                        picked = (addr, lp)
                        break
                if picked is None:
                    picked = listens[0]
                addr, port = picked
                if addr in {"0.0.0.0", "::"}:
                    # 通配监听：从映射表按端口反查宿主端口
                    host_port = next(
                        (v for k, v in proxy_map.items() if k.endswith(f":{port}")),
                        port,
                    )
                else:
                    host_port = proxy_map.get(f"{addr}:{port}", port)
                url = f"http://127.0.0.1:{host_port}"
            sm = re.search(r"--served-model-name\s+(\S+)", cmd)
            if sm:
                name = sm.group(1)
            else:
                mm = re.search(r"\bserve\s+(\S+)", cmd)
                name = Path(mm.group(1)).name if mm else f"vllm-{port}"
            out.append({"name": name, "port": port, "url": url})
    except Exception:
        return []
    seen: dict[int, dict[str, object]] = {}
    for item in out:
        seen.setdefault(item["port"], item)
    return sorted(seen.values(), key=lambda item: int(item["port"]))
