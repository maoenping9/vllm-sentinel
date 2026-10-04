#!/usr/bin/env python3
"""vLLMSentinel Rainmeter 皮肤生成器 v2 —— 严格只使用官方文档中确实存在的选项。

数据源：GET {SERVER}/api/skin?part=top（81 值）/ ?part=gpu（81 值），固定顺序值数组。
为什么这样取数：Rainmeter 的 WebParser 单亲度量最多 99 个 StringIndex，且按 key 写正则
会绑定 JSON 键序。值数组 + 序号取值，服务器改字段只影响两端对齐表。

本文件的字段顺序必须与 backend/summary.py 的 build_skin_payload 一致；生成时会实时
拉取接口断言字段数与首尾内容，避免两端漂移。

已废弃的写法（这些选项在官方 manual 中不存在，v1 皮肤就是因此糊成一条）：
  Meter=Rectangle   → 用 Meter=Shape 或 Meter=Bar / Meter=Image
  StyleName=        → 不存在，动态配色改用 FontColor/[&度量] + DynamicVariables=1
  StringFormula=    → 不存在，派生数值改用 Measure=Calc 的 Formula=
  FallbackString=   → 不存在（WebParser 有 ErrorString）
  SectionParser= / SectionIndex= → 不存在，子度量用 StringIndex=
  FontFamily=       → 字符串 meter 用 FontFace=
"""
import json
import os
import sys
import urllib.request

# ---------------- 几何常量（改版式只改这里）----------------
CARD_W = 420
M = 14
CONTENT = CARD_W - 2 * M          # 392
RIGHT = CARD_W - M                # 406，右对齐锚点
PAD_TOP = 10
ROW_MODEL = 21
ROW_GPU = 20
ROW_KV = 19
ROW_QUOTA = 21
FONT = "Segoe UI Variable Text"   # Win11 原生 UI 字体；缺失时系统自动回退
REFRESH_SEC = 6
SERVER_DEFAULT = "http://your-server-ip:8889"
BG_1 = "32,32,32,255"          # 卡片渐变上端（Win11 深色中性面 #202020）
BG_2 = "41,41,41,255"          # 卡片渐变下端
BORDER = "62,62,62,255"        # 圆角描边 #3E3E3E
BAR_TROUGH = "58,58,58,255"    # 进度条底槽
ACCENT_FALLBACK = "76,194,255,255"   # 系统强调色读取失败时使用（Win11 默认蓝）
# 卡片两套配色（Shape 的 Fill/Stroke 用；由 IfCondition 切换）
CARD_TOP_DARK_RAW = "32,32,32,255"
CARD_BOTTOM_DARK_RAW = "41,41,41,255"
CARD_BORDER_DARK_RAW = "70,70,70,255"
CARD_TOP_LIGHT_RAW = "250,250,250,255"
CARD_BOTTOM_LIGHT_RAW = "240,240,240,255"
CARD_BORDER_LIGHT_RAW = "214,214,214,255"

# ---------------- 字段顺序表（与 build_skin_payload 一一对应）----------------
# TOP 81 值：0 标题 | 1 状态文字 | 2 状态色 | 3 模型表头
#   4..35  模型 8 行 × (名称, 明细, 名称色, 状态点色)
#   36..67 CPU 8 行 × (标签, 数值, 数值色, 条百分比)
#   68..79 额度 3 行 × (标签, 数值, 数值色, 条百分比)
#   80 页脚（保留在载荷中，皮肤不渲染）
# GPU 81 值：0 表头 | 1..80 GPU 16 行 × (标签, 显存, 元信息, 负载%, 条色)
T_TITLE, T_STAT, T_STATC, T_MHDR = 1, 2, 3, 4
T_MODEL = 5        # 模型块起始 StringIndex
MODEL_N = 8
T_KV = T_MODEL + MODEL_N * 4           # 37
KV_N = 8
T_QUOTA = T_KV + KV_N * 4              # 69
QUOTA_N = 3
T_FOOTER = T_QUOTA + QUOTA_N * 4       # 81（页脚值保留在载荷里，皮肤不再渲染它）
G_HDR = 1
G_GPU = 2
GPU_N = 16
TOP_LEN = T_FOOTER                     # 81
GPU_LEN = G_GPU - 1 + GPU_N * 5        # 81


def fetch(part, base):
    url = f"{base}/api/skin?part={part}"
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.load(r)["v"]


def verify(base):
    top, gpu = fetch("top", base), fetch("gpu", base)
    problems = []
    if len(top) != TOP_LEN:
        problems.append(f"top 字段数 {len(top)} != {TOP_LEN}")
    if len(gpu) != GPU_LEN:
        problems.append(f"gpu 字段数 {len(gpu)} != {GPU_LEN}")
    if top and top[0] != "vLLM SENTINEL":
        problems.append(f"top[0] 期望标题，实得 {top[0]!r}")
    if top and not top[T_FOOTER - 1].startswith("点击打开控制台"):
        problems.append(f"top[{T_FOOTER - 1}] 期望页脚，实得 {top[T_FOOTER - 1]!r}")
    if gpu and "GPU ×" not in gpu[0]:
        problems.append(f"gpu[0] 期望表头，实得 {gpu[0]!r}")
    for i, s in enumerate(top + gpu):
        if '"' in s or "\\" in s or "\n" in s:
            problems.append(f"第 {i} 个值含引号/反斜杠/换行，会破坏正则: {s[:30]!r}")
    return problems, top, gpu


def emit(outdir, base):
    problems, top, gpu = verify(base)
    if problems:
        print("❌ 接口与生成器不对齐：")
        for p in problems:
            print("   -", p)
        return None, problems

    L = []
    add = L.append

    # ---------------- 头部 ----------------
    add("; ============================================================")
    add(";  vLLM Sentinel — Windows 桌面组件（Rainmeter 皮肤）")
    add(";  数据源：/api/skin?part=top|gpu（固定顺序值数组，服务器算好展示语义）")
    add(";  本文件由 desktop/win-rainmeter/gen_skin2.py 生成，请勿手改；改版式改生成器常量")
    add(";  选项均经官方 manual 校验（validate_ini.py 用文档白名单机械核对）")
    add("; ============================================================")
    add("")
    add("[Rainmeter]")
    add("Update=1000")
    add("AccurateText=1")
    add("DynamicWindowSize=1")
    add("DragEnabled=1")
    add("RestoreAfterRestart=1")
    add("")
    add("[Variables]")
    add(f"; 唯一需要改的配置：服务器地址（EasyTier 内网 your-server-ip + 控制台端口 8889）")
    add(f"SERVER={SERVER_DEFAULT}")
    add(f"REFRESH_SEC={REFRESH_SEC}")
    add("; 卡片自身配色：皮肤按系统主题本地取用（不走网络，避免刷新时卡片瞬暗）")
    add("CARD_TOP_DARK=32,32,32,255")
    add("CARD_BOTTOM_DARK=41,41,41,255")
    add("CARD_BORDER_DARK=70,70,70,255")
    add("CARD_TROUGH_DARK=58,58,58,255")
    add("CARD_DIVIDER_DARK=255,255,255,22")
    add("CARD_TOP_LIGHT=250,250,250,255")
    add("CARD_BOTTOM_LIGHT=240,240,240,255")
    add("CARD_BORDER_LIGHT=214,214,214,255")
    add("CARD_TROUGH_LIGHT=226,226,226,255")
    add("CARD_DIVIDER_LIGHT=0,0,0,20")
    add("TEXT_DARK=255,255,255,255")
    add("DIM_DARK=190,190,190,255")
    add("SEC_DARK=150,150,150,255")
    add("TEXT_LIGHT=26,26,26,255")
    add("DIM_LIGHT=92,92,92,255")
    add("SEC_LIGHT=118,118,118,255")
    add("; 告警色/模型配色由服务端按 theme 参数给全；上面这些是默认文字色，由皮肤本地按主题算")
    add("; 系统强调色自动读取（注册表 HKCU/Software/Microsoft/Windows/DWM/AccentColor）；读不到就用下面这个兜底色")
    add(f"ACCENT_FALLBACK={ACCENT_FALLBACK}")
    add("; 字体：想换字体只改这一行（如 Segoe UI Variable Text / 微软雅黑 / HarmonyOS Sans）")
    add(f"FONT_FACE={FONT}")
    add("")

    # ---------------- 样式（只放字体/颜色，绝不放 X/Y：避免坐标被样式影响）----------------
    add("; 样式节：仅字体类属性。Rainmeter 规则是 Meter 自身选项优先于样式，但仍不在此放坐标")
    add("; 样式只放字体属性，绝不放颜色：颜色按主题显式给（浅色主题下白字会整片看不见）")
    add("[StyleBase]")
    add("FontFace=#FONT_FACE#")
    add("FontSize=9")
    add("AntiAlias=1")
    add("[StyleTiny]")
    add("FontSize=8.5")
    add("[StyleSec]")
    add("FontSize=8.5")
    add("FontWeight=600")
    add("[StyleTitle]")
    add("FontSize=11")
    add("FontWeight=600")
    add("[StyleRight]")
    add("StringAlign=Right")
    add("")

    # ---------------- WebParser：两个亲度量（每部分 ≤99 个捕获组）----------------
    def parent(name, part, n):
        add(f"[{name}]")
        add("Measure=WebParser")
        add(f"URL=#SERVER#/api/skin?part={part}&theme=[&msThemeNum]")
        add("DynamicVariables=1")
        add("UpdateDivider=6")
        add("UpdateRate=1")
        add(f"RegExp=(?si)\"v\":\\[" + ",".join(['"(.*?)"'] * n) + "\\]")
        add("")

    def child(name, parent_name, idx, minmax=False):
        add(f"[{name}]")
        add("Measure=WebParser")
        add(f"URL=[{parent_name}]")
        add(f"StringIndex={idx}")
        add("UpdateDivider=6")
        if minmax:
            add("MinValue=0")
            add("MaxValue=100")
        add("")

    # 系统强调色：AccentColor 是 DWORD（0xAABBGGRR），用位运算拆出 R/G/B
    add("; ---------------- 系统强调色（自动跟随 Windows 个性化颜色）----------------")
    add("[AccentV]")
    add("Measure=Registry")
    add("RegHKey=HKEY_CURRENT_USER")
    add("RegKey=Software\\Microsoft\\Windows\\DWM")
    add("RegValue=AccentColor")
    add("")
    add("[AccentR]")
    add("Measure=Calc")
    add("Formula=(Trunc([&AccentV]/65536) & 255)")
    add("DynamicVariables=1")
    add("")
    add("[AccentG]")
    add("Measure=Calc")
    add("Formula=(Trunc([&AccentV]/256) & 255)")
    add("DynamicVariables=1")
    add("")
    add("[AccentB]")
    add("Measure=Calc")
    add("Formula=([&AccentV] & 255)")
    add("DynamicVariables=1")
    add("")
    add("[AccentC]")
    add("Measure=String")
    add("String=[&AccentR],[&AccentG],[&AccentB],255")
    add('Substitute="0,0,0,255":"#ACCENT_FALLBACK#"')
    add("DynamicVariables=1")
    add("")

    add("; ---------------- 系统主题（浅色/深色）：本地判色 + 作为 theme 参数上报服务端 ----------------")
    add("[msThemeRaw]")
    add("Measure=Registry")
    add("RegHKey=HKEY_CURRENT_USER")
    add("RegKey=Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize")
    add("RegValue=AppsUseLightTheme")
    add("")
    add("[msThemeNum]")
    add("Measure=Calc")
    add("Formula=[&msThemeRaw]")
    add("DynamicVariables=1")
    add("")
    text_roles = (("Text", "TEXT"), ("Dim", "DIM"), ("Sec", "SEC"))
    for role, var in (("CardTop", "CARD_TOP"), ("CardBottom", "CARD_BOTTOM"), ("CardBorder", "CARD_BORDER"),
                      ("CardTrough", "CARD_TROUGH"), ("CardDivider", "CARD_DIVIDER")) + text_roles:
        add(f"[ms{role}]")
        add("Measure=String")
        add("String=[&msThemeNum]")
        add(f'Substitute="0":"#{var}_DARK#","1":"#{var}_LIGHT#",'
            f'"0.0":"#{var}_DARK#","1.0":"#{var}_LIGHT#"')
        add("DynamicVariables=1")
        add("")

    parent("WebTop", "top", TOP_LEN)
    parent("WebGpu", "gpu", GPU_LEN)

    # 子度量：值数组每个值一个（StringIndex 从 1 开始）
    # 需要 0..100 取值的子度量：CPU 块与额度块第 4 个值、GPU 行第 4 个值（Bar 的源）
    kv_bar_idx = {T_KV + i * 4 + 3 for i in (0, 1, 4, 7)}
    quota_bar_idx = {T_QUOTA + i * 4 + 3 for i in range(QUOTA_N)}
    gpu_bar_idx = {G_GPU + i * 5 + 3 for i in range(GPU_N)}
    bar_idx = kv_bar_idx | quota_bar_idx
    for i in range(1, TOP_LEN + 1):
        child(f"t{i:02d}", "WebTop", i, minmax=(i in bar_idx))
    for i in range(1, GPU_LEN + 1):
        child(f"g{i:02d}", "WebGpu", i, minmax=(i in gpu_bar_idx))

    # ---------------- 版式游标：meter 依次排布，绝对坐标（普通数字即绝对）----------------
    meters = []
    y = PAD_TOP

    def m_line(name, meter, x, yy, **kw):
        meters.append((name, meter, x, yy, kw))

    # 背景
    card_h = 0  # 先占位，最后回填

    # 表头
    m_line("Title", "String", M, y, text=f"[&t{T_TITLE:02d}]", style="StyleBase,StyleTitle",
           color="[&msText]")
    m_line("StatText", "String", RIGHT, y + 2, text=f"[&t{T_STAT:02d}]", style="StyleBase,StyleTiny,StyleRight",
           color=f"[&t{T_STATC:02d}]")
    m_line("StatDot", "String", RIGHT - 52, y + 2, text="●", style="StyleBase", size="7",
           color=f"[&t{T_STATC:02d}]")
    y += 24
    m_line("TickModels", "Image", M, y + 2, w=3, h=9, solid="[&AccentC]")
    m_line("ModelsHeader", "String", M + 9, y, color="[&msSec]", text=f"[&t{T_MHDR:02d}]", style="StyleBase,StyleSec")
    y += 20
    m_line("DivModels", "Image", M, y - 6, w=CONTENT, h=1, solid="[&msCardDivider]")

    # 模型行
    name_x, name_w = M + 13, 148
    for i in range(MODEL_N):
        base_i = T_MODEL + i * 4
        yy = y + i * ROW_MODEL
        m_line(f"MDot{i+1}", "String", M, yy + 3, text="●", style="StyleBase",
               size="7", color=f"[&t{base_i+3:02d}]")
        m_line(f"MName{i+1}", "String", name_x, yy, text=f"[&t{base_i:02d}]",
               style="StyleBase", w=name_w, clip="1", color=f"[&t{base_i+2:02d}]")
        m_line(f"MValue{i+1}", "String", RIGHT, yy, text=f"[&t{base_i+1:02d}]",
               style="StyleBase,StyleTiny,StyleRight", color="[&msDim]")
    y += MODEL_N * ROW_MODEL + 6

    # GPU 表头 + 阵列
    m_line("TickGpu", "Image", M, y + 2, w=3, h=9, solid="[&AccentC]")
    m_line("GpuHeader", "String", M + 9, y, color="[&msSec]", text=f"[&g{G_HDR:02d}]", style="StyleBase,StyleSec")
    y += 20
    m_line("DivGpu", "Image", M, y - 6, w=CONTENT, h=1, solid="[&msCardDivider]")
    g_lbl_x, g_lbl_w = M, 112
    g_mem_x, g_mem_w = M + 114, 42
    g_bar_x, g_bar_w = M + 162, 96
    g_meta_x, g_meta_w = M + 262, CONTENT - 262
    for i in range(GPU_N):
        base_i = G_GPU + i * 5
        yy = y + i * ROW_GPU
        # 标签色与负载条同色（= 该模型在"模型服务"里的颜色），空行/高温由服务端给灰/红
        m_line(f"GLabel{i+1}", "String", g_lbl_x, yy, text=f"[&g{base_i:02d}]",
               style="StyleBase", size="8.5", w=g_lbl_w, clip="1", color=f"[&g{base_i+4:02d}]")
        m_line(f"GMem{i+1}", "String", g_mem_x + g_mem_w, yy, text=f"[&g{base_i+1:02d}]",
               style="StyleBase,StyleTiny", size="8", align="right", color="[&msDim]")
        m_line(f"GBar{i+1}", "Bar", g_bar_x, yy + 6, measure=f"g{base_i+3:02d}",
               barcolor=f"[&g{base_i+4:02d}]", w=g_bar_w, h=6)
        m_line(f"GMeta{i+1}", "String", g_meta_x, yy, text=f"[&g{base_i+2:02d}]",
               style="StyleBase,StyleTiny", size="8", w=g_meta_w, clip="1", color="[&msDim]")
    y += GPU_N * ROW_GPU + 6

    # CPU 块（带条的行走 Bar）
    m_line("TickCpu", "Image", M, y + 2, w=3, h=9, solid="[&AccentC]")
    m_line("CpuHeader", "String", M + 9, y, color="[&msSec]", text="CPU 综合", style="StyleBase,StyleSec")
    y += 20
    m_line("DivCpu", "Image", M, y - 6, w=CONTENT, h=1, solid="[&msCardDivider]")
    kv_bar_rows = {1, 2, 5, 8}          # 与服务器字段顺序对应：总使用率/内存/最高单核/整机功耗
    k_lbl_x, k_lbl_w = M, 108
    k_bar_x, k_bar_w = M + 116, 150
    for i in range(KV_N):
        base_i = T_KV + i * 4
        yy = y + i * ROW_KV
        m_line(f"KLabel{i+1}", "String", k_lbl_x, yy, text=f"[&t{base_i:02d}]",
               style="StyleBase,StyleSec", size="8.5", w=k_lbl_w, color="[&msSec]")
        if (i + 1) in kv_bar_rows:
            m_line(f"KBar{i+1}", "Bar", k_bar_x, yy + 5, measure=f"t{base_i+3:02d}",
                   barcolor="[&AccentC]", w=k_bar_w, h=7)
        m_line(f"KValue{i+1}", "String", RIGHT, yy, text=f"[&t{base_i+1:02d}]",
               style="StyleBase,StyleRight", size="9.5", color=f"[&t{base_i+2:02d}]")
    y += KV_N * ROW_KV + 6

    # 电费 / 流量额度
    m_line("TickQuota", "Image", M, y + 2, w=3, h=9, solid="[&AccentC]")
    m_line("QuotaHeader", "String", M + 9, y, color="[&msSec]", text="电费 / 流量额度", style="StyleBase,StyleSec")
    y += 20
    m_line("DivQuota", "Image", M, y - 6, w=CONTENT, h=1, solid="[&msCardDivider]")
    for i in range(QUOTA_N):
        base_i = T_QUOTA + i * 4
        yy = y + i * ROW_QUOTA
        m_line(f"QLabel{i+1}", "String", M, yy, text=f"[&t{base_i:02d}]",
               style="StyleBase,StyleSec", size="8.5", w=k_lbl_w, color="[&msSec]")
        m_line(f"QBar{i+1}", "Bar", k_bar_x, yy + 6, measure=f"t{base_i+3:02d}",
               barcolor="[&AccentC]", w=k_bar_w, h=7)
        m_line(f"QValue{i+1}", "String", RIGHT, yy, text=f"[&t{base_i+1:02d}]",
               style="StyleBase,StyleRight", size="9.5", color=f"[&t{base_i+2:02d}]")
    y += QUOTA_N * ROW_QUOTA + 6

    card_h = y

    # ---------------- 输出 meter ----------------
    add("; ---------------- 背景与点击区 ----------------")
    add("; 卡片：圆角 + 竖向渐变。颜色不能用 [&度量] 直接写在 Shape 串里（动态变量在 Shape 里不保证生效），")
    add("; 改由 [msThemeNum] 的 IfCondition 用 !SetOption 按主题设置，这也是 Rainmeter 官方推荐的动态改样式做法。")
    add("[Card]")
    add("Meter=Shape")
    add("X=0")
    add("Y=0")
    add(f"Shape=Rectangle 0,0,{CARD_W},{card_h},7 | Fill LinearGradient 90 | {CARD_TOP_DARK_RAW};0.0 | {CARD_BOTTOM_DARK_RAW};1.0 | StrokeWidth 1 | Stroke Color {CARD_BORDER_DARK_RAW}")
    add("")

    def card_shape(top, bottom, border):
        # 高度代入真实数字：!SetOption 的值不会再做模板替换，写占位符会让形状失效
        return (f"Rectangle 0,0,{CARD_W},{card_h},7 | Fill LinearGradient 90 | {top};0.0 | "
                f"{bottom};1.0 | StrokeWidth 1 | Stroke Color {border}")

    add("; 按系统主题切换卡片配色（IfCondition + !SetOption：官方推荐的动态改样式方式）")
    add("[msThemeApply]")
    add("Measure=Calc")
    add("Formula=[&msThemeNum]")
    add("DynamicVariables=1")
    add("IfCondition=([msThemeApply] = 1)")
    add(f'IfTrueAction=[!SetOption "Card" "Shape" "{card_shape(CARD_TOP_LIGHT_RAW, CARD_BOTTOM_LIGHT_RAW, CARD_BORDER_LIGHT_RAW)}"][!UpdateMeter "Card"][!Redraw]')
    add(f'IfFalseAction=[!SetOption "Card" "Shape" "{card_shape(CARD_TOP_DARK_RAW, CARD_BOTTOM_DARK_RAW, CARD_BORDER_DARK_RAW)}"][!UpdateMeter "Card"][!Redraw]')
    add("")
    add("[AccentSpine]")
    add("Meter=Image")
    add("X=0")
    add("Y=7")
    add("W=3")
    add(f"H={card_h - 14}")
    add("SolidColor=[&AccentC]")
    add("DynamicVariables=1")
    add("")

    add("[ClickZone]")
    add("Meter=Image")
    add("X=0")
    add("Y=0")
    add(f"W={CARD_W}")
    add(f"H={card_h}")
    add("SolidColor=0,0,0,1")
    add('LeftMouseUpAction=["#SERVER#"]')
    add("")
    add("; ---------------- 内容 ----------------")
    for name, meter, x, yy, kw in meters:
        add(f"[{name}]")
        add(f"Meter={meter}")
        add(f"X={x}")
        add(f"Y={yy}")
        style = kw.pop("style", None)
        if style:
            # 注意：Rainmeter 多样式分隔符是竖线，逗号会被当成一个不存在的样式名
            add("MeterStyle=" + " | ".join(x.strip() for x in style.split(",")))
        if meter == "Bar":
            add(f"MeasureName={kw.pop('measure')}")
            add("BarOrientation=Horizontal")
            add(f"BarColor={kw.pop('barcolor')}")
            add("SolidColor=[&msCardTrough]")
        if "w" in kw:
            add(f"W={kw.pop('w')}")
        if "h" in kw:
            add(f"H={kw.pop('h')}")
        if "size" in kw:
            add(f"FontSize={kw.pop('size')}")
        if "align" in kw:
            add(f"StringAlign={kw.pop('align').capitalize()}")
        if "clip" in kw:
            add(f"ClipString={kw.pop('clip')}")
        if "color" in kw:
            add(f"FontColor={kw.pop('color')}")
        if "solid" in kw:
            add(f"SolidColor={kw.pop('solid')}")
        if "text" in kw:
            add(f"Text={kw.pop('text')}")
        if kw:
            raise SystemExit(f"{name} 有未处理选项 {kw}")
        # 只要有动态色值引用（[&tXX] / [&AccentC]）就必须开 DynamicVariables
        if meter in ("String", "Bar", "Image", "Shape"):
            add("DynamicVariables=1")
        add("")

    path = os.path.join(outdir, "vLLMSentinel.ini")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path, []


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "build/vLLMSentinel"
    base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8889"
    os.makedirs(outdir, exist_ok=True)
    path, problems = emit(outdir, base)
    if problems:
        print(f"生成失败：{len(problems)} 处接口/生成器不一致")
        return 1
    lines = open(path, encoding="utf-8").read().count("\n")
    print(f"written: {path}  ({lines} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
