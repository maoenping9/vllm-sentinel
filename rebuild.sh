#!/usr/bin/env bash
cd /path/to/vllm-sentinel
echo "[rebuild] start $(date)" >> /tmp/vllmsent-rebuild.log
docker compose build 2>&1 | tail -15 >> /tmp/vllmsent-rebuild.log
echo "[rebuild] up -d" >> /tmp/vllmsent-rebuild.log
docker compose up -d 2>&1 | tail -10 >> /tmp/vllmsent-rebuild.log
echo "[rebuild] done $(date)" >> /tmp/vllmsent-rebuild.log
