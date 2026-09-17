#!/usr/bin/env bash
# OCR 按需运行：选空闲 64G 卡 → (若有服务占用则先停止) → 启动 OCR → 执行任务 → 自动退出 → 恢复原服务
# 用法: ocr_run.sh <图片或PDF路径> [输出文件]
#   选卡优先级:
#     1. 空闲的 64G 卡 (memory_used < 1GB)
#     2. LLM 占用之外的 64G 卡 (有进程但非 LLM 服务 → 先停止该服务进程,完成后恢复)
#     3. LLM 占用的 64G 卡 → 报错让用户决定(LLM 服务不建议自动停)
set -euo pipefail

INPUT="${1:?用法: ocr_run.sh <图片或PDF路径> [输出文件]}"
OUTPUT="${2:-}"
CONTAINER="unlimited-ocr"
PORT=10000
MODEL_SNAP="/root/.cache/huggingface/hub/models--baidu--Unlimited-OCR/snapshots/84757cb04b4d9b74adc65dc31cdf52fca7dc2a97"
HF_CACHE_HOST="$HOME/.cache/huggingface"
LOAD_WAIT_MAX=180     # 最多等 3 分钟装载

# ---- 1. 选卡 ----
pick_gpu() {
  local lines idx used
  lines=$(nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader,nounits \
    | awk -F', ' '$3+0 > 50000 {print $1, $2}' | sort -n)
  # 空闲的 64G 卡 (memory_used < 1GB)
  while read -r idx used; do
    if [ "$used" -lt 1024 ]; then
      echo "$idx free"
      return 0
    fi
  done <<< "$lines"
  # 无空闲 64G → 第一张被占用的 64G 卡（LLM 占用与否由下方判断）
  echo "$lines" | head -1
}

SEL=$(pick_gpu)
GPU_IDX="${SEL%% *}"; KIND="${SEL##* }"
echo "[选卡] GPU$GPU_IDX ($KIND)"

STOPPED_SVC=""
if [ "$KIND" = "occupied" ]; then
  # 识别占卡服务进程(非 LLM): 从 vllm-sentinel api/state 拿 service 归属
  SVC=$(curl -s --max-time 6 "http://127.0.0.1:8889/api/state" 2>/dev/null \
    | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d={}
for g in d.get('gpu',{}).get('items',[]):
    if g.get('index')==$GPU_IDX: print(g.get('service') or '')
" 2>/dev/null || true)
  echo "[占卡] GPU$GPU_IDX 服务: ${SVC:-未知}"
  if [ -z "$SVC" ]; then
    echo "❌ GPU$GPU_IDX 被未知进程占用且无法识别服务,放弃。请手动处理。"
    exit 1
  fi
  case "$SVC" in
    *GLM*|*DSV4*|*Qwen*|*vLLM*)
      echo "❌ GPU$GPU_IDX 被 LLM 服务($SVC)占用,不建议自动停止。请指定空闲卡或手动处理。"
      exit 1;;
    *)
      STOPPED_SVC="$SVC"
      echo "[停止] 停止 $SVC (OCR 完成后恢复) —— 请按记忆里的服务管理方式停止"
      ;;
  esac
fi

cleanup() {
  echo "[清理] 停止 OCR 容器(用完即退)"
  docker stop "$CONTAINER" >/dev/null 2>&1 || true
  if [ -n "$STOPPED_SVC" ]; then
    echo "[恢复] 恢复原服务 $STOPPED_SVC —— 请按记忆里的服务管理方式启动"
  fi
}
trap cleanup EXIT

# ---- 2. 启动 OCR ----
echo "[启动] OCR → GPU$GPU_IDX (本地权重,装载最多 ${LOAD_WAIT_MAX}s)"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" --gpus "\"device=$GPU_IDX\"" \
  -p $PORT:10000 \
  -v "$HF_CACHE_HOST:/root/.cache/huggingface" \
  -e HF_HUB_OFFLINE=1 \
  vllm/vllm-openai:unlimited-ocr \
  "$MODEL_SNAP" --served-model-name Unlimited-OCR --trust-remote-code \
  --dtype bfloat16 --max-model-len 32768 --port 10000 --gpu-memory-utilization 0.5 >/dev/null

ready=0
for i in $(seq 1 $((LOAD_WAIT_MAX / 15))); do
  sleep 15
  if curl -s --max-time 5 "http://localhost:$PORT/v1/models" 2>/dev/null | grep -q Unlimited; then
    ready=1; break
  fi
  echo "[装载] 等待中 ($((i*15))s)..."
done
[ "$ready" = "1" ] || { echo "❌ OCR 装载超时"; exit 1; }
echo "[就绪] OCR 服务就绪 ✓"

# ---- 3. 执行任务 ----
if [ -n "$OUTPUT" ]; then
  ~/.local/bin/ocr-tool image "$INPUT" > "$OUTPUT" 2>&1 && echo "[完成] 结果 → $OUTPUT"
else
  ~/.local/bin/ocr-tool image "$INPUT"
fi
