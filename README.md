# vLLM Sentinel

> **v2.2** — 面向多 GPU vLLM 推理机的实时监控控制台 + macOS 桌面 3D 机箱小组件（Übersicht）。

一个 Docker 命令拉起 Web 控制台，同时看模型吞吐/延迟、GPU 阵列、主机资源和 BMC 功耗；桌面小组件以等轴 3D 机箱实时呈现全部 GPU（卡数自适应）、猫扇/涡轮扇转速、GPU 三段状态条、涡轮显卡风扇与前→后气流动画。

v2.2 亮点（在 v2.1 基础上）：
- **累计口径改为持久日汇总**：新增 `daily` 汇总表（电量 / 电费 / 流量，**永不被历史裁剪删除**），自然月、自然年、流量周期都由它求和 —— 年度额度不再等于最近 31 天，跨月持续累加；日/月/年边界一律按本地时区（原先容器 UTC 会把月初/年初算错 8 小时）。`/api/energy` 由每次全表扫样本变为毫秒级增量。
- **网络流量真实累加**：桌面组件原先用「瞬时速率 × 周期已过时长」反推累计，数值随速率跳动；现读后端持久累加值，单调递增、2 秒实时刷新。
- **流量口径修正为 WAN 出口**：原先把 `/proc/net/dev` 除 `lo` 外**所有**网卡相加（含 10G 内网互传、VPN、docker 网桥），内网互传会把数值放大数倍；现只统计默认路由口，可用 `NET_IFACE` 指定。
- **GPU 转速读数修复**：多台 BOSS Storm3 串口盒按「官方驱动节点当前指向」动态选口（串口枚举顺序会变，硬编码会静默读错盒）；`get_LEVELS` 帧按 `0x4C 包头 + 8 通道字节` 解析（原先差一位，包头被当成第 1 通道，导致机箱扇转速恒定不变）；串口读失败不再写入 30s 缓存。
- **GPU↔模型归属修复**：容器需要 `pid: host` 才能枚举宿主 GPU 进程 —— 缺了它 `nvidia-smi --query-compute-apps` 恒返回 0 行，所有在用卡会被显示成「空闲」。
- **内存温度**：CPU 区新增内存使用率条 + 内存条温度 0/1（`DIMMG0/1_TEMP`）+ 内存供电温度 0/1（`VR_DIMMG0/1_TEMP`），各自按传感器自带阈值上色。
- **模型命名对齐**：DeepSeek V4.1 裸名归一 + Qwen3.8 家族按体量区分（INT8 / Flash-Next / W4A16），桌面组件与 Web 控制台同名同色。

v2.1 亮点（在 v2.0 基础上）：
- **显卡数自适应**：卡条/风扇/卡号跟随本机实际 GPU 数量（不再 hardcode），加卡自动跟上。
- **三段状态条**：显卡条 = 显存段（模型色，左半）+ 功率段（≥200W 黄色）+ 温度段（≥75°C 红色），从两端向内生长、满载占满整条。
- **网络流量周期**：每月 20 号 → 下月 20 号跨月周期，总配额 1.5TB，达 1TB 红色提示。
- **自然月电费**：TOU 分时电价积分 + 本月/本年/本月预估（线性外推）。
- **风扇转速全量实时**：GPU 专属扇（Corsair PWM 反算 + BOSS Storm3 串口档位换算）+ Storm3 机箱扇（G2 后排双扇/G1 前排）+ 主板 IPMI 机箱扇。
- **MB/s EMA 平滑**：网络速率显示指数移动平均，抹平逐秒毛刺。

v2.0 亮点：
- **3D 机箱小组件（v90）**：双塔写实造型，等轴旋转摆动画（-26°↔-50°），13×9733 GPU 涡轮风扇、顶/前/后 Noctua 猫扇与 G2 排风，显卡条负载/功率分段条，GPU↔模型实时对照；前端进风 → GPU 卡仓 → 后排排风的气流动画。
- **Web 控制台**：模型吞吐/延迟、GPU 阵列、主机性能、BMC 功耗（一键 `docker compose up -d`）。

截图来自 `8 × NVIDIA CMP 170HX` 上的 `GLM-5.3-Flash` 生产实例。

## 目录结构

- `backend/` — FastAPI 数据服务（`/api/state` GPU↔模型映射、`/api/energy` BMC 功耗）
- `frontend/` — React/Vite Web 控制台
- `desktop/` — macOS Übersicht 3D 机箱小组件（Intel Mac）
- `docs/screenshots/` — 效果图

## 效果图

### 运行态势

总览生成/预填充吞吐、TTFT/TPOT、排队、KV Cache，以及 GPU/CPU/整机功耗。

![运行态势](docs/screenshots/dashboard-overview.png)

### 模型监控

实例在线状态、P50/P95/P99 延迟、端到端延迟、Prefix Cache 和 Spec Decode 接受率。

![模型监控](docs/screenshots/model-metrics.png)

### GPU 阵列

逐卡利用率、显存、温度、功耗、频率和 GPU 进程。

![GPU 阵列](docs/screenshots/gpu-array.png)

### 主机性能

CPU 逐逻辑处理器、内存、GPU 显存、磁盘 IO 和网卡吞吐。

![主机性能](docs/screenshots/host-performance.png)

### BMC 管理

整机 DCMI 功耗、CPU/PCH/系统温度、风扇、电源模块和 IPMI 信息。

![BMC 管理](docs/screenshots/bmc-management.png)

## 功能

- Dashboard：生成/预填充吞吐、Token 总量、TTFT、TPOT、并发、排队、KV Cache
- 模型监控：多 vLLM 实例、延迟分位、缓存命中、Spec Decode
- GPU 阵列：每张卡独立展示，不依赖 DCGM Exporter
- 主机性能：CPU / 内存 / 磁盘 / 网络
- BMC 管理：独立无网络采集容器，只读 `/dev/ipmi0`
- 2 秒 SSE 实时推送，SQLite 保存 15 分钟到 7 天历史
- 深海蓝 / 石墨黑 / 月光白主题

## 快速开始

需要 Linux、Docker Compose、NVIDIA Container Toolkit，以及本机可达的 vLLM `/metrics`。

```bash
cp .env.example .env
# 修改 VLLM_ENDPOINTS 指向你的 vLLM
docker compose up -d --build
```

打开 `http://服务器地址:8733`。

```dotenv
VLLM_ENDPOINTS=[{"name":"GLM-5.3-Flash","url":"http://127.0.0.1:9004"}]
```

可同时监控多个实例；`api_key` 可选。控制台只读 `/metrics`，不会代理聊天，也不会改模型服务。

鉴权由 `DASHBOARD_AUTH_ENABLED` 控制。内网可关，对公网请打开并设置强密码。

## 部署要点（v2.2 新增）

**1. 想看 GPU 上跑的是哪个模型，容器必须 `pid: host`。**
容器的 `nvidia-smi` 只能枚举本 PID 命名空间可见的进程；缺了 `pid: host` 时
`--query-compute-apps` 恒返回 0 行 → `gpu_map` 为空 → 所有在用卡都会被显示成「空闲」。
`compose.yaml` 已带上该项，若自行改写 compose 请保留。

**2. 风扇转速来源（有 BOSS Storm3 风机盒时）。**
串口盒由 `gpu-fan-control` 一类温控服务驱动，通道档位（0-127）经串口 `get_LEVELS` 读出后按
`档位 / 127 × 3450` 换算成 RPM（满速 3450）。注意两点：

- 一台机器可能挂**多只**同型号 CH340 串口盒（如 GPU 专属 9733 盒 + 机箱/CPU 风冷盒），
  且 `/dev/ttyUSB*` 的枚举顺序会变。后端按官方驱动节点（`/dev/ttyCH341USB0`）的当前指向
  自动选口，也可以用 `STORM_PORT` 显式指定（支持逗号分隔的候选列表）。
- 帧格式为 `0x4C('L') 包头 + 8 个通道字节`（每字节 = 档位×2，共 9 字节）。

无 Storm3 时该段逻辑自动跳过，风扇转速仍可由 Corsair Commander 的 `pwmN`（`PWM/255×3450`）得到。

**3. 累计口径（电量 / 电费 / 流量）。**
`/api/energy` 的月、年、流量周期累计都来自 `daily` 汇总表，它**不参与历史裁剪**
（样本按 `HISTORY_RETENTION_HOURS` 裁剪，汇总表永久保留），所以年度值会跨月持续累加；
日/月/年边界按 `TZ_OFFSET_HOURS`（默认 +8，北京时间）切分。

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `NET_IFACE` | 自动（默认路由口） | 统计流量的网卡；留空则取默认路由接口（= WAN），避免把内网互传/容器网桥算进去 |
| `NET_CYCLE_START_DAY` | `20` | 流量周期起始日（每月该日 00:00 起算，桌面组件同值） |
| `NET_CYCLE_BASE_GB` | `0` | 流量周期手工基准（GB）。只有本机网卡采样可看，若想对齐路由器/ISP 账单口径，填一个实测值做起点，之后按本机增量实时累加；只在首次运行写入一次，跨周期自动失效 |
| `TZ_OFFSET_HOURS` | `8` | 累计边界与分时电价的本地时区偏移 |
| `HISTORY_RETENTION_HOURS` | `744` | 样本保留时长（不影响月/年累计） |

## 接口

- `GET /api/health`
- `GET /api/state`
- `GET /api/stream`
- `GET /api/history?range=1h`
- `GET /api/energy`（累计电量/电费 + 月/年/流量周期累计）

## License

MIT
