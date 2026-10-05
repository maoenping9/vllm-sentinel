#!/usr/bin/env bash
# vLLMSentinel Windows 皮肤一键发布
#
# 两条产物线互不污染（公开仓库脱敏要求）：
#   1) 仓库内 build/  → 地址一律写占位符
#   2) 交付包 zip     → 注入真实服务器地址（SENTINEL_SERVER），推到静态下载位
#
# 用法:
#   SENTINEL_SERVER=http://你的服务器:8889 SENTINEL_STATIC_DIR=/path/to/static ./publish.sh [版本号] [校验用地址]
#   版本号缺省按现有 v*.zip 递增；校验用地址缺省 http://127.0.0.1:8889
set -euo pipefail
cd "$(dirname "$0")"

VER="${1:-}"
VERIFY="${2:-${SENTINEL_VERIFY:-http://127.0.0.1:8889}}"
REAL_SERVER="${SENTINEL_SERVER:-http://your-server-ip:8889}"
STATIC_DIR="${SENTINEL_STATIC_DIR:-}"
PLACEHOLDER="http://your-server-ip:8889"

if [[ -z "$VER" ]]; then
  last=$(ls -1 vLLMSentinel-win-v*.zip 2>/dev/null | sed 's/.*-v\([0-9]*\)\.zip/\1/' | sort -n | tail -1)
  VER=$(( ${last:-0} + 1 ))
fi

echo "== 1/5 生成仓库用 ini（地址写占位符，保证公开仓库脱敏）"
SENTINEL_INI_SERVER="$PLACEHOLDER" python3 gen_skin2.py build/vLLMSentinel "$VERIFY"

echo "== 2/5 校验：选项名是否真实存在（官方文档白名单）"
python3 validate_ini.py build/vLLMSentinel/vLLMSentinel.ini
python3 validate_ini.py build/vLLMSentinelSelftest/vLLMSentinelSelftest.ini

echo "== 3/5 校验：正则实测 / 引用完整性 / 坐标"
python3 verify_skin.py build/vLLMSentinel/vLLMSentinel.ini "$VERIFY"

echo "== 4/5 生成交付包（注入真实地址 $REAL_SERVER）"
DELIVER=$(mktemp -d)
SENTINEL_INI_SERVER_OVERRIDE="$REAL_SERVER" python3 - "$DELIVER" <<'PY'
import os, subprocess, sys
deliver = sys.argv[1]
env = dict(os.environ)
env["SENTINEL_INI_SERVER"] = env.get("SENTINEL_INI_SERVER_OVERRIDE", "http://your-server-ip:8889")
subprocess.run(["python3", "gen_skin2.py", os.path.join(deliver, "vLLMSentinel"),
                env.get("SENTINEL_VERIFY", "http://127.0.0.1:8889")], check=True, env=env,
               stdout=subprocess.DEVNULL)
PY
python3 - "$DELIVER" "$REAL_SERVER" <<'PY'
import os, re, sys
deliver, real = sys.argv[1], sys.argv[2]
src = "build/vLLMSentinelSelftest/vLLMSentinelSelftest.ini"
dst = os.path.join(deliver, "vLLMSentinelSelftest.ini")
s = open(src, encoding="utf-8").read()
if real:
    s = s.replace("http://your-server-ip:8889", real)
open(dst, "w", encoding="utf-8").write(s)
PY

echo "== 5/5 打固定包 + 版本包并发布"
cp README.md build/README.md
python3 - "$VER" "$DELIVER" "$STATIC_DIR" <<'PY'
import hashlib, os, shutil, sys, zipfile

ver, deliver, static = sys.argv[1], sys.argv[2], sys.argv[3]
ver_zip = f"vLLMSentinel-win-v{ver}.zip"
stable_zip = "vLLMSentinel-win.zip"

def add_tree(z, base, prefix):
    for root, _dirs, files in os.walk(base):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.join(prefix, os.path.relpath(p, base)))

for out in (ver_zip, stable_zip):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        add_tree(z, os.path.join(deliver, "vLLMSentinel"), "vLLMSentinel")
        z.write(os.path.join(deliver, "vLLMSentinelSelftest.ini"), "vLLMSentinelSelftest/vLLMSentinelSelftest.ini")
        z.write("build/README.md", "README.md")

if static and os.path.isdir(static):
    for f in (ver_zip, stable_zip):
        shutil.copy(f, os.path.join(static, f))
        os.chmod(os.path.join(static, f), 0o644)
    page_dir = os.path.join(static, "vLLMSentinel")
    os.makedirs(page_dir, exist_ok=True)
    size = os.path.getsize(stable_zip)
    md5 = hashlib.md5(open(stable_zip, "rb").read()).hexdigest()
    open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8").write(f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>vLLM Sentinel Windows 组件</title><style>
body{{margin:0;background:#202020;color:#e8e8e8;font:15px/1.6 "Segoe UI Variable Text","Microsoft YaHei UI",sans-serif;display:flex;justify-content:center;padding:48px 20px}}
.box{{max-width:560px;width:100%}}h1{{font-size:20px;margin:0 0 4px}}
.meta{{color:#9a9a9a;font-size:13px;margin-bottom:22px}}
a.btn{{display:inline-block;background:#4cc2ff;color:#00253a;font-weight:600;text-decoration:none;padding:13px 26px;border-radius:8px;font-size:16px}}
a.btn:hover{{background:#6ccaff}}ol{{padding-left:22px;color:#c8c8c8}}code{{background:#2b2b2b;padding:1px 5px;border-radius:4px}}
.note{{margin-top:22px;color:#8a8a8a;font-size:13px}}
</style></head><body><div class="box">
<h1>vLLM Sentinel · Windows 桌面组件</h1>
<div class="meta">当前版本 v{ver} · {size} 字节 · md5 {md5}<br>下载后核对大小/md5，与上面不一致说明拿到的是浏览器缓存旧包</div>
<a class="btn" href="/static/{stable_zip}">下载 {stable_zip}</a>
<ol><li>装 Rainmeter（任意较新版）</li>
<li>解压 zip，把 <code>vLLMSentinel</code> 和 <code>vLLMSentinelSelftest</code> 放进 <code>%APPDATA%/Rainmeter/Skins/</code></li>
<li>Rainmeter 里加载 <code>vLLMSentinel.ini</code>（首次先加载 <code>vLLMSentinelSelftest</code> 自检更稳）</li>
<li>旧版请先删除 <code>Skins/vLLMSentinel</code> 再放新文件夹</li></ol>
<div class="note">数据源 /api/skin（每 6 秒刷新）· 需要内网/VPN 在线才能取到数据</div>
</div></body></html>""")
    print(f"  已发布到静态位: {os.path.join(static, stable_zip)}")
print(f"  版本包: {ver_zip}")
print(f"  固定包: {stable_zip}  ({os.path.getsize(stable_zip)} B, md5 {hashlib.md5(open(stable_zip,'rb').read()).hexdigest()[:8]})")
PY
rm -rf "$DELIVER" 2>/dev/null || true
echo
echo "完成。交付包已注入真实地址；仓库内 build/ 保持占位符。"
