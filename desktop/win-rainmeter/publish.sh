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

# 生成固定入口页（可收藏，点按钮即下载；显示版本/大小/md5 便于核对是否下到新版）
python3 - "$VER" <<'PY'
import hashlib, os, sys
ver = sys.argv[1]
f = "vLLMSentinel-win.zip"
size = os.path.getsize(f)
md5 = hashlib.md5(open(f, "rb").read()).hexdigest()
dest = "/path/to/deploy/static/vLLMSentinel/index.html"
os.makedirs(os.pathname(dest) if False else os.path.dirname(dest), exist_ok=True)
open(dest, "w", encoding="utf-8").write(f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>vLLM Sentinel Windows 组件</title><style>
body{{margin:0;background:#202020;color:#e8e8e8;font:15px/1.6 "Microsoft YaHei UI","Segoe UI",sans-serif;display:flex;justify-content:center;padding:48px 20px}}
.box{{max-width:560px;width:100%}}h1{{font-size:20px;margin:0 0 4px}}
.meta{{color:#9a9a9a;font-size:13px;margin-bottom:22px}}
a.btn{{display:inline-block;background:#4cc2ff;color:#00253a;font-weight:600;text-decoration:none;padding:13px 26px;border-radius:8px;font-size:16px}}
a.btn:hover{{background:#6ccaff}}ol{{padding-left:22px;color:#c8c8c8}}code{{background:#2b2b2b;padding:1px 5px;border-radius:4px}}
.note{{margin-top:22px;color:#8a8a8a;font-size:13px}}
</style></head><body><div class="box">
<h1>vLLM Sentinel · Windows 桌面组件</h1>
<div class="meta">当前版本 v{ver} · {size} 字节 · md5 {md5}<br>下载后核对大小/md5，与上面不一致说明拿到的是浏览器缓存旧包</div>
<a class="btn" href="/static/{f}">下载 vLLMSentinel-win.zip</a>
<ol><li>装 Rainmeter（任意较新版）</li>
<li>解压 zip，把 <code>vLLMSentinel</code> 和 <code>vLLMSentinelSelftest</code> 两个文件夹放进 <code>%APPDATA%\\Rainmeter\\Skins\\</code></li>
<li>Rainmeter 里加载 <code>vLLMSentinel.ini</code>（首次先加载 <code>vLLMSentinelSelftest</code> 自检更稳）</li>
<li>旧版请先删除 <code>Skins\\vLLMSentinel</code> 再放新文件夹</li></ol>
<div class="note">数据源 /api/skin（每 6 秒刷新）· 需要 EasyTier 在线才能取到数据</div>
</div></body></html>""")
print("  入口页: /static/vLLMSentinel/index.html")
PY

echo
echo "入口页（可收藏，点按钮下载）：http://your-server-ip:8889/static/vLLMSentinel/"
echo "固定下载地址（永不变）：http://your-server-ip:8889/static/vLLMSentinel-win.zip"
echo "局域网备用：          http://your-server-ip:8889/static/vLLMSentinel-win.zip"
