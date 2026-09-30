#!/usr/bin/env python3
"""按 vLLMSentinel.ini 的几何常量，用线上 /api/summary 真实数据渲染 1:1 HTML 预览。
预览 ≠ 交付物本体（本体是 Rainmeter ini），仅用于 Windows 安装前确认版式。
用法：python3 preview.py [输出 html]"""
import json
import sys
import urllib.request

CARD_W = 420
M = 14
CONTENT = CARD_W - 2 * M
G_LBL, G_MEM, G_GAP = 118, 42, 6
G_META = 112
G_BAR = CONTENT - G_LBL - G_MEM - G_META - G_GAP * 3
DOT_W, NAME_W, STAT_W = 6, 132, 36
VAL_W = CONTENT - DOT_W - NAME_W - STAT_W - 12 - 6 - 6
QUOTA_LBL_W, QUOTA_BAR_W = 96, 200

PALETTE = ["#4e9cff", "#34d399", "#f59e0b", "#a78bfa", "#f472b6", "#22d3ee"]
TXT = ["#7eb1ff", "#6ee7b7", "#fabа4d".replace("а", "a"), "#bea6fd", "#f88fc5", "#54e0f1"]

src = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8889/api/summary"
d = json.load(urllib.request.urlopen(src, timeout=8))

rows = []
add = rows.append


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;")


add(f'<div class="hdr"><span class="brand">vLLM SENTINEL</span>'
    f'<span class="tiny">{esc(d["host"])} · 6s 刷新 <span class="dot on"></span>{esc("实时" if d["status"]=="ok" else d["status"])}</span></div>')
on = sum(1 for m in d["models"] if m["name"] and m["stIdx"] == 0)
tot = sum(1 for m in d["models"] if m["name"])
add(f'<div class="sec">模型服务 {on}/{tot} 在线</div>')
for m in d["models"]:
    if not m["name"]:
        continue
    c = PALETTE[m["cIdx"]] if m["cIdx"] < 6 else "#64748b"
    tc = TXT[m["cIdx"]] if m["cIdx"] < 6 else "#64748b"
    st = ["正常", "启动中", "离线"][m["stIdx"]]
    stc = ["#7ee2a8", "#f5b83a", "#ef4444"][m["stIdx"]]
    add(f'<div class="mrow"><span class="dot" style="background:{c}"></span>'
        f'<span class="mname" style="color:{tc}">{esc(m["name"])}</span>'
        f'<span style="color:{stc};font-size:8pt">{st}</span>'
        f'<span class="mval">{esc(m["value"])}</span></div>')

add(f'<div class="sec">GPU × 16 · 总 {esc(d["gpuW"])}W + 200W</div>')
bar_x = M + G_LBL + G_MEM + G_GAP * 2
for g in d["gpus"]:
    if g["idx"] < 0:
        continue
    bc = PALETTE[g["bar"]] if g["bar"] < 6 else ("rgba(100,116,139,.35)" if g["bar"] == 6 else "#ef4444")
    lc = TXT[g["bar"]] if g["bar"] < 6 else "#64748b"
    add(f'<div class="grow"><span style="width:{G_LBL}px;color:{lc}">{esc(g["label"])}</span>'
        f'<span class="mem" style="width:{G_MEM}px">{esc(g["memG"])}</span>'
        f'<span class="barwrap" style="width:{G_BAR}px"><i style="width:{int(g["util"])}%;background:{bc}"></i></span>'
        f'<span class="tiny" style="width:{G_META}px">{esc(g["meta"])}</span></div>')


def kv(label, value, color=None):
    st = f'style="color:{color}"' if color else ""
    add(f'<div class="kv"><span class="tiny">{label}</span><span {st}>{esc(value)}</span></div>')


def bar(frac, color="#6e8cff"):
    add(f'<div class="fbar" ><i style="width:{min(100, frac * 100):.0f}%;background:{color}"></i></div>')


add('<div class="sec">CPU 综合</div>')
kv("总使用率", d["cpuUse"] + " %")
bar(float(d["cpuUse"]) / 100)
kv("内存使用率", d["memUse"] + " %")
bar(float(d["memUse"]) / 100)
kv("内存温度", d["dimm"], ["#e2e8f0", "#fbbf24", "#ef4444"][d["dimmTone"]])
kv("内存供电温度", d["vr"], ["#e2e8f0", "#fbbf24", "#ef4444"][d["vrTone"]])
kv("最高单核", d["maxCore"] + " %")
kv("CPU 温度", d["cpuTemp"], ["#e2e8f0", "#fbbf24", "#ef4444"][d["cpuTone"]])
kv("线程数 / 频率", f'{d["threads"]} 线程 · {esc(d["freqM"])}MHz')
kv("整机功耗（GPU+200W）", d["totalW"] + " W")
add('<div class="sec">电费 / 流量额度</div>')
warn = "linear-gradient(90deg,#f59e0b,#ef4444)"
add(f'<div class="qrow"><span class="tiny">本月额度</span><span class="fbar" style="width:{QUOTA_BAR_W}px"><i style="width:{min(100, float(d["costM"]) / float(d.get("costMBudget", 500)) * 100):.0f}%;background:{warn if d["costMTone"] else "#6e8cff"}"></i></span><span> {esc(d["costM"])} / 500 元</span></div>')
add(f'<div class="qrow"><span class="tiny">本年额度</span><span class="fbar" style="width:{QUOTA_BAR_W}px"><i style="width:{min(100, float(d["costY"]) / float(d.get("costYBudget", 6000)) * 100):.0f}%;background:{warn if d["costYTone"] else "#6e8cff"}"></i></span><span> {esc(d["costY"])} / 6000 元</span></div>')
kv("网络流量（20日起）", f'{esc(d["netTB"])} / 1.5 TB', "#ef4444" if d["netWarn"] else "#e2e8f0")
bar(float(d["netTB"]) / 1.5, warn if d["netWarn"] else "#6e8cff")
kv("磁盘 IO / 网络", f'{esc(d["diskMB"])}/{esc(d["netMB"])} MB/s')
add(f'<div class="foot tiny">点击打开控制台 · iface {esc(d["iface"])} · ts {d["ts"]}</div>')

html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:"Microsoft YaHei UI","Segoe UI",sans-serif}}
body{{background:#334;padding:24px;display:flex;justify-content:center}}
.card{{width:{CARD_W}px;background:linear-gradient(180deg,#0d1321,#121a2c);color:#e2e8f0;padding:{M}px;border:1px solid #2a3650;border-radius:6px;font-size:9pt;line-height:1.35}}
.hdr{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}}
.brand{{font-size:11pt;font-weight:700}}
.sec{{color:#94a3b8;font-size:8pt;margin:6px 0 3px}}
.dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:#64748b;margin-right:5px;vertical-align:1px}}
.dot.on{{background:#7ee2a8}}
.mrow{{display:flex;align-items:center;gap:6px;height:17px;overflow:hidden}}
.mname{{width:{NAME_W}px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.mval{{margin-left:auto;color:#94a3b8;font-size:8pt;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:{VAL_W}px}}
.grow{{display:flex;align-items:center;gap:{G_GAP}px;height:16px;font-size:8pt;white-space:nowrap;overflow:hidden}}
.mem{{text-align:right;color:#94a3b8}}
.barwrap{{height:5px;background:#1e293b;display:inline-block;position:relative}}
.barwrap i{{display:block;height:5px}}
.kv{{display:flex;justify-content:space-between;height:15px;font-size:8.5pt}}
.kv span:last-child{{font-size:8.5pt}}
.fbar{{display:block;height:6px;background:#1e293b;margin-bottom:3px}}
.fbar i{{display:block;height:6px}}
.qrow{{display:flex;align-items:center;gap:8px;height:18px;font-size:8pt}}
.qrow .fbar{{margin:0}}
.tiny{{font-size:7.5pt;color:#64748b}}
.foot{{margin-top:6px}}
</style></head><body><div class="card">{"".join(rows)}</div></body></html>"""

out = sys.argv[1] if len(sys.argv) > 1 else "preview.html"
open(out, "w", encoding="utf-8").write(html)
print("written:", out)
