# vLLM Sentinel — macOS 桌面小组件（Übersicht）

把 vLLM Sentinel 控制台的关键指标**直接渲染在 Mac 桌面上**（壁纸之上、窗口之下），2 秒实时刷新。适配 Intel Mac。

桌面显示内容：
- 模型服务：各 vLLM 实例在线状态、生成 tok/s、KV Cache 命中
- GPU ↔ LLM 对照：实时显示“哪个 LLM 跑在哪些 GPU 上”（来自后端 `/api/state` 的 `gpu_map`，自动识别 vLLM 主进程的 `--port` 并关联 `CUDA_VISIBLE_DEVICES` / 父进程链）
- GPU 阵列：Top N 张卡（按 负载×0.7 + 温度×0.3 降序，与控制台同口径）、温度、风扇转速（海盗船 Commander 实测 PWM×3450 换算）
- 整机功耗：GPU 总功耗 + 其他 ~200W、电源额定 2600W + 2200W
- 主机内存、最后更新时间

数据源：本机 vLLM Sentinel 控制台 `GET /api/state`（`curl` 在 Mac 本地执行，无 CORS 问题）。

## 安装（Intel Mac）

1. 安装 Übersicht（免费桌面 widget 框架）：

```bash
brew install --cask ubersicht
# 或从官网下载: http://tracesof.net/uebersicht/
```

2. 把整个 `vllm-sentinel.widget` 文件夹拷贝到 Übersicht 的 widgets 目录：

```bash
mkdir -p ~/Library/Application\ Support/Übersicht/widgets
cp -R vllm-sentinel.widget ~/Library/Application\ Support/Übersicht/widgets/
```

3. 如果服务器 IP 不是 `your-server-ip`，编辑 widget 里的 `index.jsx` 顶部常量：

```jsx
const SERVER = 'http://你的服务器IP:8889'
```

4. 完成。Übersicht 会自动加载，widget 出现在屏幕右上角桌面层；可拖动位置由 Übersicht 设置调整（或在 className 里改 `top/right`）。

## 可调参数（widget 顶部常量）

| 常量 | 默认 | 说明 |
|---|---|---|
| `SERVER` | `http://your-server-ip:8889` | vLLM Sentinel 控制台地址 |
| `REFRESH_MS` | `2000` | 刷新间隔（毫秒） |
| `GPU_TOP_N` | `4` | 桌面显示几张 GPU 卡 |
| `OTHER_W` | `200` | 整机功耗估算的"其他"补偿值 |
| `PSU` | `2600 + 2200 W` | 电源额定文案 |

## 「GPU ↔ LLM」区块说明

这一区块把"某个 LLM 当前占用了哪些 GPU"清晰地列出来，数据来自后端 `GET /api/state` 的 `gpu_map` 字段。

**显示格式**：`模型名  →  G1 G3 G5 · 端口`，例如 `DeepSeek-V4-Flash-Exp  →  G3 G5 G6 G7 G8 · :40017`。

- `G` 后的数字 = **GPU 索引**（`nvidia-smi` 里的卡号）。
- 端口 = 该服务的 **API 端口**（`--port`）。
- 每行 = 一个当前真正在 GPU 上占有显存的服务；模型未加载或 GPU 空闲时不会出现在列表里，显示"暂无绑定"。

**映射是怎么得出的（后端 `backend/gpu_map.py`）**：
1. 从 `nvidia-smi` 拿到"GPU → 进程 PID"。
2. 沿每个进程的**父进程链**向上找，命中带 `--port <N>` 的 vLLM 主进程，即按端口关联到 `.env` 里的实例名。
3. 非 vLLM 的常驻 GPU 服务（如 GPU0 的 WeMM-Embedding-9B `:8008`）按 cmdline 关键字识别并单独列出。
4. 因为容器以非 root 运行、读不到 `environ`（无 `CUDA_VISIBLE_DEVICES`），才走父进程链方案。

**为何会变**：本机 LLM 服务会重启/上线下线（Qwen 三实例、DSV4 都会来回抖动），所以 `gpu_map` 是**实时**的——谁在跑就显示谁，谁重启中就不在列表。这是"看到真实情况"而不是写死。

**当前机型映射基准**（your-host，14 GPU）：
| GPU | LLM / 服务 | 端口 |
|---|---|---|
| 0 | WeMM-Embedding-9B | 8008 |
| 3,5,6,7,8 | DeepSeek-V4-Flash-Exp | 40017 |
| 9 / 10 / 13 | Qwen3.8-27B-W4A16 各实例 | 38024/38025/38027 |

> 端点在 `.env` 的 `VLLM_ENDPOINTS` 里维护；`GLM-5.3-Flash(:40053)` 已长期下线且无监督脚本，故从列表剔除。

## 说明

- widget 只读 `/api/state`，不会改任何模型服务。
- 断网/服务器不可达时显示"离线"，并按刷新间隔自动重试。
- 需要更多指标（BMC 温度/风扇阵列、模型延迟分位）可在 `render` 里按 `/api/state` 字段扩展。
