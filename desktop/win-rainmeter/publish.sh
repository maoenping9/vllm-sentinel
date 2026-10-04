#!/usr/bin/env bash
# vLLMSentinel Windows 皮肤一键发布
#
# 流程：生成 ini → 两道校验（文档白名单 + 正则实测）→ 打版本包 + 固定包 → 发布到控制台静态位
# 固定下载地址（永不变，永远指向最新版）：
#     http://your-server-ip:8889/static/vLLMSentinel-win.zip
# 版本包同时保留一份，便于回退：
#     http://your-server-ip:8889/static/vLLMSentinel-win-v<N>.zip
#
# 用法: ./publish.sh [版本号，默认递增] [数据源地址]
set -euo pipefail
cd "$(dirname "$0")"

SERVER="${2:-http://127.0.0.1:8889}"
STATIC_DIR="/path/to/deploy/static"
VER="${1:-}"

if [[ -z "$VER" ]]; then
  last=$(ls -1 vLLMSentinel-win-v*.zip 2>/dev/null | sed 's/.*-v\([0-9]*\)\.zip/\1/' | sort -n | tail -1)
  VER=$(( ${last:-0} + 1 ))
fi

echo "== 1/4 生成 ini（数据源 $SERVER）"
python3 gen_skin2.py build/vLLMSentinel "$SERVER"

echo "== 2/4 校验：选项名是否真实存在（官方文档白名单）"
python3 validate_ini.py build/vLLMSentinel/vLLMSentinel.ini
python3 validate_ini.py build/vLLMSentinelSelftest/vLLMSentinelSelftest.ini

echo "== 3/4 校验：正则实测 / 引用完整性 / 坐标"
python3 verify_skin.py build/vLLMSentinel/vLLMSentinel.ini "$SERVER"

echo "== 4/4 打包并发布"
cp README.md build/README.md
python3 - "$VER" <<'PY'
import os, shutil, sys, zipfile, hashlib
ver = sys.argv[1]
ver_zip = f"vLLMSentinel-win-v{ver}.zip"
stable_zip = "vLLMSentinel-win.zip"
for out in (ver_zip, stable_zip):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk("build"):
            for f in files:
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, "build"))
static = "/path/to/deploy/static"
os.makedirs(static, exist_ok=True)
for f in (ver_zip, stable_zip):
    shutil.copy(f, os.path.join(static, f))
    os.chmod(os.path.join(static, f), 0o644)
md5 = hashlib.md5(open(stable_zip, "rb").read()).hexdigest()[:8]
print(f"  版本包: {ver_zip}")
print(f"  固定包: {stable_zip}  ({os.path.getsize(stable_zip)} B, md5 {md5})")
PY

echo
echo "固定下载地址（永不变）：http://your-server-ip:8889/static/vLLMSentinel-win.zip"
echo "局域网备用：          http://your-server-ip:8889/static/vLLMSentinel-win.zip"
