#!/usr/bin/env bash
# 重新构建镜像并滚动更新（日志追加到 /tmp/vllmsent-rebuild.log）
set -euo pipefail
cd "$(dirname "$0")"                     # 与仓库所在路径无关：始终在仓库根执行
echo "[rebuild] start $(date)" >> /tmp/vllmsent-rebuild.log
docker compose build 2>&1 | tail -15 >> /tmp/vllmsent-rebuild.log
echo "[rebuild] up -d" >> /tmp/vllmsent-rebuild.log
docker compose up -d 2>&1 | tail -10 >> /tmp/vllmsent-rebuild.log
echo "[rebuild] done $(date)" >> /tmp/vllmsent-rebuild.log
