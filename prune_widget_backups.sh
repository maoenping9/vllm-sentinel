#!/usr/bin/env bash
# vLLM Sentinel 小组件备份清理规则：
#   - index.jsx.bak-v9-*        永久保存
#   - 其它 index.jsx.bak-*      只保留最近 3 个（按修改时间），其余删除
# 用法: ./prune_widget_backups.sh [保留数量，默认 3]
set -euo pipefail

KEEP_V9_GLOB="index.jsx.bak-v9-*"
MOD_GLOB="index.jsx.bak-*"
KEEP_N="${1:-3}"
HOST="${DEPLOY_HOST:-10.10.1.13}"

ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$HOST" bash -s -- "$KEEP_N" <<'REMOTE'
KEEP_N="$1"
W="$HOME/Library/Application Support/Übersicht/widgets/vllm-sentinel.widget"
[ -d "$W" ] || { echo "组件目录不存在: $W"; exit 1; }

# 永久保存的 v9（不动）
v9_count=$(find "$W" -maxdepth 1 -name 'index.jsx.bak-v9-*' | wc -l | tr -d ' ')
echo "永久保存 v9: $v9_count 个"

# 修改备份：按修改时间新→旧，保留前 KEEP_N 个，其余删除
# （可移植写法，不用 mapfile——Mac 自带 bash 较老）
total=$(find "$W" -maxdepth 1 -name 'index.jsx.bak-*' ! -name 'index.jsx.bak-v9-*' | wc -l | tr -d ' ')
echo "修改备份: $total 个"

if [ "$total" -gt 0 ]; then
  n=0
  ls -t "$W"/index.jsx.bak-* 2>/dev/null | grep -v 'index.jsx.bak-v9-' | while IFS= read -r f; do
    n=$((n + 1))
    if [ "$n" -le "$KEEP_N" ]; then
      echo "保留: $(basename "$f")"
    else
      rm -f "$f"
      echo "删除: $(basename "$f")"
    fi
  done
fi
REMOTE

echo "清理完成。"
