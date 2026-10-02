#!/usr/bin/env python3
"""生成 vLLM Sentinel 的 Rainmeter 皮肤 vLLMSentinel.ini（Windows 桌面组件）。

版式对齐 Mac Übersicht 组件 v97.x（去掉 3D 机箱图，平面化）：
  头部 → 模型服务 → GPU 阵列 → CPU 综合 → 电费/流量额度 → 页脚
数据源：单请求 GET {SERVER}/api/summary（展示语义服务端算好，见 backend/summary.py）。
用法：python3 gen_skin.py [输出目录]
"""
import sys
import os

CARD_W = 420
M = 14
CONTENT = CARD_W - M * 2

# 行内几何
G_LBL, G_MEM, G_GAP = 118, 42, 6
G_META = 112
G_BAR = CONTENT - G_LBL - G_MEM - G_META - G_GAP * 3

MODEL_LBL_X = M
DOT_X, DOT_W = M, 6
NAME_W, STAT_W = 132, 36
VAL_W = CONTENT - DOT_W - NAME_W - STAT_W - 12 - 6 - 6

KV_LBL_W = 170
BAR_FULL_W = CONTENT
QUOTA_LBL_W, QUOTA_BAR_W, QUOTA_VAL_W = 96, 200, CONTENT - 96 - 200 - 8 - 8

MODEL_SLOTS, GPU_SLOTS = 8, 16

L = []


def emit(*lines):
    L.extend(lines)


def style_defs():
    emit(
        "[GBar0]\nSolidColor=78,156,255,255",
        "[GBar1]\nSolidColor=52,211,153,255",
        "[GBar2]\nSolidColor=245,158,11,255",
        "[GBar3]\nSolidColor=167,139,250,255",
        "[GBar4]\nSolidColor=244,114,182,255",
        "[GBar5]\nSolidColor=34,211,238,255",
        "[GBarIdle]\nSolidColor=100,116,139,90",
        "[GBarHot]\nSolidColor=239,68,68,255",
        "[GBarHidden]\nSolidColor=0,0,0,0",
        "[GBarBlue]\nSolidColor=110,140,255,255",
        "[GBarWarn]\nSolidColor=239,116,68,255",
        "[TxtC0]\nFontColor=126,177,255,255",
        "[TxtC1]\nFontColor=110,231,183,255",
        "[TxtC2]\nFontColor=250,186,77,255",
        "[TxtC3]\nFontColor=190,166,253,255",
        "[TxtC4]\nFontColor=248,143,197,255",
        "[TxtC5]\nFontColor=84,224,241,255",
        "[TxtIdle]\nFontColor=100,116,139,255",
        "[TxtRed]\nFontColor=239,68,68,255",
        "[TxtNormal]\nFontColor=226,232,240,255",
        "[TxtWarn]\nFontColor=251,191,36,255",
        "[TxtSt0]\nFontColor=126,226,168,255",
        "[TxtSt1]\nFontColor=245,184,58,255",
        "[TxtSt2]\nFontColor=239,68,68,255",
        "[TxtSt3]\nFontColor=100,116,139,0",
        "[DotC0]\nSolidColor=78,156,255,255",
        "[DotC1]\nSolidColor=52,211,153,255",
        "[DotC2]\nSolidColor=245,158,11,255",
        "[DotC3]\nSolidColor=167,139,250,255",
        "[DotC4]\nSolidColor=244,114,182,255",
        "[DotC5]\nSolidColor=34,211,238,255",
        "[DotHidden]\nSolidColor=0,0,0,0",
        "[DotFresh]\nSolidColor=126,226,168,255",
        "[DotStale]\nSolidColor=245,184,58,255",
        "[DotOff]\nSolidColor=239,68,68,255",
    )


def main(outdir="."):
    os.makedirs(outdir, exist_ok=True)
    emit(
        "; ============================================================",
        ";  vLLM Sentinel - Windows 桌面组件 (Rainmeter 皮肤)",
        ";  版式对齐 Mac 组件 v97.x（平面版）；数据源 /api/summary 单请求",
        ";  要求 Rainmeter >= 4.5（动态 StyleName）",
        ";  部署：整个文件夹放入 %APPDATA%\\Rainmeter\\Skins\\ ，加载本 ini",
        "; ============================================================",
        "",
        "[Rainmeter]",
        "Update=1000",
        "AccurateText=1",
                "DragEnabled=1",
        "RestoreAfterRestart=1",
        "",
        "[Variables]",
        "; ==== 唯一需要改的配置：服务器地址（EasyTier 内网 IP + 控制台端口 8889）====",
        "SERVER=http://your-server-ip:8889",
        "REFRESH_MS=6000",
        "; 温度红色阈值与预算进度条阈值已在服务端算好（summary.py），这里不用配",
        "",
        "; ---------------- 基础样式 ----------------",
        "[Base]",
        "FontFamily=Microsoft YaHei UI",
        "FontSize=9",
        "FontColor=226,232,240,255",
        "AntiAlias=1",
        "",
        "[SecTitle]",
        "FontColor=148,163,184,255",
        "FontSize=8",
        "",
        "[Small]",
        "FontSize=8",
        "",
        "[Tiny]",
        "FontSize=7.5",
        "FontColor=100,116,139,255",
        "",
        "[Right]",
        "StringAlign=Right",
        "",
    )
    style_defs()

    # ---------- 数据层 ----------
    emit(
        "",
        "; ---------------- 数据层：单请求聚合端点 ----------------",
        "[WebSummary]",
        "Measure=Plugin",
        "Plugin=WebParser",
        "URL=[#SERVER]/api/summary",
        "UpdateDivider=[#REFRESH_MS]",
        "DynamicVariables=1",
        "HTTPTimeout=5000",
        "RetryCount=0",
        "",
        "; ---- 顶层标量（字段名唯一，直接子正则） ----",
    )

    def web(key, fallback="", quoted=True):
        fb0 = fallback or "0"
        pat = f'"{key}":"([^"]*)"' if quoted else f'"{key}":([-\\d.eE+]+)'
        return [
            f"[w{key}]",
            "Measure=Plugin",
            "Plugin=WebParser",
            "URL=[WebSummary]",
            f"RegExp={pat}",
            f"FallbackString={fb0}",
            "",
        ]

    for k in ["status", "host", "gpuW", "totalW", "cpuUse", "memUse", "cpuTemp",
              "dimm", "vr", "maxCore", "costM", "costY", "costEst", "netTB",
              "netMB", "diskMB", "iface", "freqM"]:
        emit(*web(k, "0" if k in ("cpuUse", "memUse", "maxCore", "costM", "costY", "netTB", "netMB", "diskMB", "freqM") else ""))
    for k in ["cpuTone", "dimmTone", "vrTone", "costMTone", "costYTone", "netWarn", "threads", "ts"]:
        emit(*web(k, quoted=False))

    # 预算用常量（与 summary.py 一致，仅展示分母，客户端不重算）
    emit("[wcostMBudget]", "Measure=String", "String=500", "",
         "[wcostYBudget]", "Measure=String", "String=6000", "",
         "[wnetTotalTB]", "Measure=String", "String=1.5", "")

    # ---------- 数组区段（SectionParser） ----------
    emit("; ---------------- 模型服务 8 槽 ----------------")
    model_fields = {
        "name": ('"name":"([^"]*)"', ""),
        "value": ('"value":"([^"]*)"', ""),
        "cIdx": ('"cIdx":(\\d+)', "6"),
        "stIdx": ('"stIdx":(\\d+)', "3"),
    }
    for fld, (pat, fb) in model_fields.items():
        fbv = fb if fld in ("name", "value") else "0"
        for i in range(1, MODEL_SLOTS + 1):
            emit(
                f"[m{fld}{i}]",
                "Measure=Plugin",
                "Plugin=WebParser",
                "URL=[WebSummary]",
                f"RegExp={pat}",
                "SectionParser=2",
                f"SectionIndex={i}",
                f"FallbackString={fbv}",
                "",
            )

    emit("; ---------------- GPU 16 槽 ----------------")
    gpu_fields = {
        "label": ('"label":"([^"]*)"', ""),
        "meta": ('"meta":"([^"]*)"', ""),
        "memG": ('"memG":"([^"]*)"', ""),
        "util": ('"util":"([^"]*)"', "0"),
        "bar": ('"bar":(\\d+)', "8"),
        "mIdx": ('"mIdx":(\\d+)', "2"),
    }
    for fld, (pat, fb) in gpu_fields.items():
        for i in range(1, GPU_SLOTS + 1):
            quoted = fld in ("label", "meta", "memG", "util")
            emit(
                f"[g{fld}{i}]",
                "Measure=Plugin",
                "Plugin=WebParser",
                "URL=[WebSummary]",
                f"RegExp={pat}",
                "SectionParser=2",
                f"SectionIndex={i}",
                f"FallbackString={fb}",
                "",
            )

    # ---------- 派生层 ----------
    emit("; ---------------- 派生：新鲜度 / 样式档位 / 宽度 ----------------")
    emit(
        "[mAge]",
        "Measure=String",
        "StringFormula=now()-[wts]",
        "FallbackString=99999",
        "DynamicVariables=1",
        "",
        "[mStatStyle]",
        "Measure=String",
        "StringFormula=([mAge]<30)?(\"DotFresh\"):(([mAge]<120)?(\"DotStale\"):\"DotOff\")",
        "FallbackString=DotOff",
        "DynamicVariables=1",
        "",
        "[mStatText]",
        "Measure=String",
        "StringFormula=([mAge]<30)?(\"实时\"):(([mAge]<120)?(\"数据延迟\"):\"离线·检查网络\")",
        "FallbackString=离线",
        "DynamicVariables=1",
        "",
        "[mModelTotal]",
        "Measure=String",
        "StringFormula=" + "+".join(f"([mstIdx{i}]!=3)" for i in range(1, MODEL_SLOTS + 1)),
        "DynamicVariables=1",
        "",
        "[mModelOn]",
        "Measure=String",
        "StringFormula=" + "+".join(f"([mstIdx{i}]=0)" for i in range(1, MODEL_SLOTS + 1)),
        "DynamicVariables=1",
        "",
        "[mNetStyle]",
        "Measure=String",
        "StringFormula=([wnetWarn]=1)?(\"TxtRed\"):(\"TxtNormal\")",
        "FallbackString=TxtNormal",
        "DynamicVariables=1",
        "",
    )
    for i in range(1, MODEL_SLOTS + 1):
        emit(
            f"[mDotStyle{i}]",
            "Measure=String",
            f"StringFormula=([mcIdx{i}]<6)?((\"DotC\"&[mcIdx{i}])):(\"DotHidden\")",
            "FallbackString=DotHidden",
            "DynamicVariables=1",
            "",
            f"[mTxtStyle{i}]",
            "Measure=String",
            f"StringFormula=([mcIdx{i}]<6)?((\"TxtC\"&[mcIdx{i}])):(\"TxtIdle\")",
            "FallbackString=TxtIdle",
            "DynamicVariables=1",
            "",
            f"[mStStyle{i}]",
            "Measure=String",
            f"StringFormula=(\"TxtSt\"&[mstIdx{i}])",
            "FallbackString=TxtSt3",
            "DynamicVariables=1",
            "",
            f"[mStText{i}]",
            "Measure=String",
            f"String=[&mstIdx{i}]",
            'Substitute="0":"正常","1":"启动中","2":"离线","3":""',
            "FallbackString=",
            "DynamicVariables=1",
            "",
        )
    for i in range(1, GPU_SLOTS + 1):
        emit(
            f"[gBarStyle{i}]",
            "Measure=String",
            f"StringFormula=([gbar{i}]<6)?((\"GBar\"&[gbar{i}])):(([gbar{i}]=6)?((\"GBarIdle\")):(([gbar{i}]=7)?((\"GBarHot\")):(\"GBarHidden\")))",
            "FallbackString=GBarHidden",
            "DynamicVariables=1",
            "",
            f"[gLblStyle{i}]",
            "Measure=String",
            f"StringFormula=([gbar{i}]<6)?((\"TxtC\"&[gbar{i}])):(\"TxtIdle\")",
            "FallbackString=TxtIdle",
            "DynamicVariables=1",
            "",
            f"[gBarW{i}]",
            "Measure=String",
            f"StringFormula=Max(0,Min({G_BAR},[gutil{i}]*{G_BAR}/100))",
            "FallbackString=0",
            "DynamicVariables=1",
            "",
        )
    emit(
        "[mCpuBarW]", "Measure=String", f"StringFormula=Max(0,Min({BAR_FULL_W},[wcpuUse]*{BAR_FULL_W}/100))",
        "FallbackString=0", "DynamicVariables=1", "",
        "[mMemBarW]", "Measure=String", f"StringFormula=Max(0,Min({BAR_FULL_W},[wmemUse]*{BAR_FULL_W}/100))",
        "FallbackString=0", "DynamicVariables=1", "",
        "[mCostMBarW]", "Measure=String", f"StringFormula=Max(0,Min({QUOTA_BAR_W},[wcostM]/500*{QUOTA_BAR_W}))",
        "FallbackString=0", "DynamicVariables=1", "",
        "[mCostYBarW]", "Measure=String", f"StringFormula=Max(0,Min({QUOTA_BAR_W},[wcostY]/6000*{QUOTA_BAR_W}))",
        "FallbackString=0", "DynamicVariables=1", "",
        "[mNetBarW]", "Measure=String", f"StringFormula=Max(0,Min({QUOTA_BAR_W},[wnetTB]/1.5*{QUOTA_BAR_W}))",
        "FallbackString=0", "DynamicVariables=1", "",
        "[mCostMStyle]", "Measure=String", "StringFormula=([wcostMTone]=1)?(\"GBarWarn\"):(\"GBarBlue\")",
        "FallbackString=GBarBlue", "DynamicVariables=1", "",
        "[mCostYStyle]", "Measure=String", "StringFormula=([wcostYTone]=1)?(\"GBarWarn\"):(\"GBarBlue\")",
        "FallbackString=GBarBlue", "DynamicVariables=1", "",
        "[mNetBarStyle]", "Measure=String", "StringFormula=([wnetWarn]=1)?(\"GBarWarn\"):(\"GBarBlue\")",
        "FallbackString=GBarBlue", "DynamicVariables=1", "",
        "[mCpuTStyle]", "Measure=String", "StringFormula=([wcpuTone]=2)?(\"TxtRed\"):(([wcpuTone]=1)?((\"TxtWarn\")):(\"TxtNormal\"))",
        "FallbackString=TxtNormal", "DynamicVariables=1", "",
        "[mDimmTStyle]", "Measure=String", "StringFormula=([wdimmTone]=2)?(\"TxtRed\"):(([wdimmTone]=1)?((\"TxtWarn\")):(\"TxtNormal\"))",
        "FallbackString=TxtNormal", "DynamicVariables=1", "",
        "[mVrTStyle]", "Measure=String", "StringFormula=([wvrTone]=2)?(\"TxtRed\"):(([wvrTone]=1)?((\"TxtWarn\")):(\"TxtNormal\"))",
        "FallbackString=TxtNormal", "DynamicVariables=1", "",
    )

    # ---------- 绘制层 ----------
    y = 10
    emit(
        "",
        "; ---------------- 绘制层 ----------------",
        "[BG]",
        "Meter=Image",
        f"X=0 Y=0 W={CARD_W} H=800",
        "SolidColor=13,19,33,235",
        "SolidColor2=18,26,44,235",
        "GradientAngle=90",
        "",
        "[Brand]",
        "Meter=String",
        "MeterStyle=Base",
        "Text=vLLM SENTINEL",
        "FontSize=11",
        "FontWeight=700",
        "FontColor=226,232,240,255",
        f"X={M} Y={y}",
        "",
        "[HdrHost]",
        "Meter=String",
        "MeterStyle=Base,Right,Tiny",
        f"Text=[&whost] · 6s 刷新",
        f"X={M + CONTENT} Y={y + 4}",
        "DynamicVariables=1",
        "",
        "[HdrDot]",
        "Meter=Rectangle",
        f"X={M + CONTENT - 150} Y={y + 4}",
        "W=7 H=7",
        "LineCount=0",
        "StyleName=[&mStatStyle]",
        "DynamicVariables=1",
        "",
        "[HdrStat]",
        "Meter=String",
        "MeterStyle=Base,Tiny",
        "Text=[&mStatText]",
        f"X={M + CONTENT - 140} Y={y + 1}",
        "DynamicVariables=1",
    )

    y += 24

    def kv(row_y, label, value_meter, style="", x=M, label_style="Base"):
        emit(
            f"[K{row_y}{abs(hash(label))%9973}A",  # 占位防重名（会被 clean 处理）
        )
        L.pop()
        tag = f"kv{row_y}"
        emit(
            f"[{tag}L]",
            "Meter=String",
            f"MeterStyle={label_style},Tiny",
            f"Text={label}",
            f"X={x} Y={row_y}",
            "",
            f"[{tag}V]",
            "Meter=String",
            f"MeterStyle=Base,Right{style}",
            f"Text=[&{value_meter}]",
            f"X={x + CONTENT} Y={row_y}",
            "DynamicVariables=1",
        )
        return tag

    # 模型服务区
    emit(f"[SecModelsT]", "Meter=String", "MeterStyle=Base,SecTitle",
         "Text=模型服务  [&mModelOn]/[&mModelTotal] 在线", f"X={M} Y={y}", "DynamicVariables=1")
    y += 16
    for i in range(1, MODEL_SLOTS + 1):
        emit(
            f"[MDot{i}]", "Meter=Rectangle", f"X={M} Y={y + 4}", "W=6 H=6", "LineCount=0",
            f"StyleName=[&mDotStyle{i}]", "DynamicVariables=1",
            "",
            f"[MName{i}]", "Meter=String", f"MeterStyle=Base",
            f"Text=[&mname{i}]", f"X={M + DOT_W + 6} Y={y}", f"W={NAME_W}",
            "ClipString=2", f"StyleName=[&mTxtStyle{i}]", "DynamicVariables=1",
            "",
            f"[MStat{i}]", "Meter=String", "MeterStyle=Base,Small",
            f"Text=[&mStText{i}]", f"X={M + DOT_W + 6 + NAME_W + 6} Y={y + 1}", f"W={STAT_W}",
            f"StyleName=[&mStStyle{i}]", "DynamicVariables=1",
            "",
            f"[MVal{i}]", "Meter=String", "MeterStyle=Base,Small,Right",
            f"Text=[&mvalue{i}]", f"X={M + CONTENT} Y={y + 1}", f"W={VAL_W}",
            "ClipString=2", "FontColor=148,163,184,255", "DynamicVariables=1",
        )
        y += 17

    # GPU 区
    emit(f"[SecGpuT]", "Meter=String", "MeterStyle=Base,SecTitle",
         "Text=GPU × 16 · 总 [&wgpuW]W + 200W", f"X={M} Y={y + 2}", "DynamicVariables=1")
    y += 18
    bar_x = M + G_LBL + G_MEM + G_GAP * 2
    meta_x = M + G_LBL + G_MEM + G_GAP * 2 + G_BAR + G_GAP
    for i in range(1, GPU_SLOTS + 1):
        emit(
            f"[GLbl{i}]", "Meter=String", "MeterStyle=Base,Small",
            f"Text=[&glabel{i}]", f"X={M} Y={y}", f"W={G_LBL}", "ClipString=2",
            f"StyleName=[&gLblStyle{i}]", "DynamicVariables=1",
            "",
            f"[GMem{i}]", "Meter=String", "MeterStyle=Base,Small",
            f"Text=[&gmemG{i}]", f"X={M + G_LBL} Y={y}", f"W={G_MEM}",
            "StringAlign=Right", "FontColor=148,163,184,255", "DynamicVariables=1",
            "",
            f"[GBg{i}]", "Meter=Rectangle", f"X={bar_x} Y={y + 2}", f"W={G_BAR} H=5",
            "LineCount=0", "SolidColor=30,41,59,255",
            "",
            f"[GBf{i}]", "Meter=Rectangle", f"X={bar_x} Y={y + 2}",
            f"W=[&gBarW{i}] H=5", "LineCount=0",
            f"StyleName=[&gBarStyle{i}]", "DynamicVariables=1",
            "",
            f"[GMeta{i}]", "Meter=String", "MeterStyle=Base,Tiny",
            f"Text=[&gmeta{i}]", f"X={meta_x} Y={y + 1}", f"W={G_META}", "ClipString=2",
            "DynamicVariables=1",
        )
        y += 16

    # CPU 综合
    y += 4
    emit(f"[SecCpuT]", "Meter=String", "MeterStyle=Base,SecTitle",
         "Text=CPU 综合", f"X={M} Y={y}")
    y += 16
    kv(y, "总使用率", "wcpuUse%"); y += 15
    emit(f"[CpuBarBg]", "Meter=Rectangle", f"X={M} Y={y}", f"W={BAR_FULL_W} H=6",
         "LineCount=0", "SolidColor=30,41,59,255",
         "", f"[CpuBar]", "Meter=Rectangle", f"X={M} Y={y}", f"W=[&mCpuBarW] H=6",
         "LineCount=0", "StyleName=GBarBlue", "DynamicVariables=1"); y += 9
    kv(y, "内存使用率", "wmemUse%"); y += 15
    emit(f"[MemBarBg]", "Meter=Rectangle", f"X={M} Y={y}", f"W={BAR_FULL_W} H=6",
         "LineCount=0", "SolidColor=30,41,59,255",
         "", f"[MemBar]", "Meter=Rectangle", f"X={M} Y={y}", f"W=[&mMemBarW] H=6",
         "LineCount=0", "StyleName=GBarBlue", "DynamicVariables=1"); y += 9
    emit(f"[DimmT]", "Meter=String", "MeterStyle=Base,Tiny", "Text=内存温度", f"X={M} Y={y}",
         "", f"[DimmV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wdimm]", f"X={M + CONTENT} Y={y - 1}", "StyleName=[&mDimmTStyle]",
         "DynamicVariables=1"); y += 15
    emit(f"[VrT]", "Meter=String", "MeterStyle=Base,Tiny", "Text=内存供电温度", f"X={M} Y={y}",
         "", f"[VrV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wvr]", f"X={M + CONTENT} Y={y - 1}", "StyleName=[&mVrTStyle]",
         "DynamicVariables=1"); y += 15
    kv(y, "最高单核", "wmaxCore%"); y += 15
    emit(f"[CpuTempL]", "Meter=String", "MeterStyle=Base,Tiny", "Text=CPU 温度", f"X={M} Y={y}",
         "", f"[CpuTempV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wcpuTemp]", f"X={M + CONTENT} Y={y - 1}", "StyleName=[&mCpuTStyle]",
         "DynamicVariables=1"); y += 15
    kv(y, "线程数 / 频率", "wthreads"); y += 15
    emit(f"[ThrV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wfreqM]MHz", f"X={M + CONTENT} Y={y - 16}", "DynamicVariables=1")
    emit(f"[TotalWL]", "Meter=String", "MeterStyle=Base,Tiny", "Text=整机功耗（GPU+200W）", f"X={M} Y={y}",
         "", f"[TotalWV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wtotalW] W", f"X={M + CONTENT} Y={y - 1}", "DynamicVariables=1"); y += 17

    # 额度区
    def quota(row_y, tag, label, val_meter, style, text_right):
        emit(
            f"[{tag}L]", "Meter=String", "MeterStyle=Base,Tiny", f"Text={label}",
            f"X={M} Y={row_y + 3}",
            "", f"[{tag}Bg]", "Meter=Rectangle", f"X={M + QUOTA_LBL_W} Y={row_y + 3}",
            f"W={QUOTA_BAR_W} H=6", "LineCount=0", "SolidColor=30,41,59,255",
            "", f"[{tag}F]", "Meter=Rectangle", f"X={M + QUOTA_LBL_W} Y={row_y + 3}",
            f"W=[&{val_meter}] H=6", "LineCount=0",
            f"StyleName=[&{style}]", "DynamicVariables=1",
            "", f"[{tag}V]", "Meter=String", "MeterStyle=Base,Small",
            f"Text={text_right}", f"X={M + CONTENT} Y={row_y + 2}",
            "StringAlign=Right", "DynamicVariables=1",
        )

    emit(f"[SecQuotaT]", "Meter=String", "MeterStyle=Base,SecTitle",
         "Text=电费 / 流量额度", f"X={M} Y={y}")
    y += 15
    quota(y, "Q1", "本月额度", "mCostMBarW", "mCostMStyle", "[&wcostM]/500 元"); y += 13
    quota(y, "Q2", "本年额度", "mCostYBarW", "mCostYStyle", "[&wcostY]/6000 元"); y += 13
    emit(f"[NetL]", "Meter=String", "MeterStyle=Base,Tiny", "Text=网络流量（20日起）",
         f"X={M} Y={y}", "", f"[NetV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wnetTB] / 1.5 TB", f"X={M + CONTENT} Y={y - 1}",
         "StyleName=[&mNetStyle]", "DynamicVariables=1"); y += 15
    quota(y, "Q3", " ", "mNetBarW", "mNetBarStyle", ""); y += 13
    emit(f"[IONL]", "Meter=String", "MeterStyle=Base,Tiny", "Text=磁盘 IO / 网络",
         f"X={M} Y={y}", "", f"[IONV]", "Meter=String", "MeterStyle=Base,Right,Small",
         "Text=[&wdiskMB]/[&wnetMB] MB/s", f"X={M + CONTENT} Y={y - 1}",
         "DynamicVariables=1"); y += 15
    emit(f"[Foot]", "Meter=String", "MeterStyle=Base,Tiny",
         "Text=点击打开控制台 · 右键 Rainmeter 菜单可调透明度",
         f"X={M} Y={y}", "")
    y += 18

    # 底部高度裁剪：BG/Border 用固定 H，把总高写回
    total_h = y + 6
    for i, line in enumerate(L):
        if line == "SolidColor=13,19,33,235":
            pass
    L2 = []
    for line in L:
        line = line.replace(f"H=800", f"H={total_h}")
        L2.append(line)
    # 点击整卡打开控制台
    L2.extend([
        "",
        "[ClickZone]",
        "Meter=Image",
        f"X=0 Y=0 W={CARD_W} H={total_h}",
        "SolidColor=0,0,0,1",
        "LeftMouseUpAction=[\"[#SERVER]\"]",
        "DynamicVariables=1",
        "",
    ])
    # kv() 里 value 带单位后缀的写法：% 直接拼在 Text 里，wcpuUse% 需要改成 [&wcpuUse]&\"%\"
    L3 = []
    for line in L2:
        line = line.replace("Text=[&wcpuUse%]", "Text=[&wcpuUse] %")
        line = line.replace("Text=[&wmemUse%]", "Text=[&wmemUse] %")
        line = line.replace("Text=[&wmaxCore%]", "Text=[&wmaxCore] %")
        line = line.replace("Text=[&wthreads]", "Text=[&wthreads] 线程")
        L3.append(line)

    # Rainmeter 坐标默认相对定位（上一元素位置 + 值），纯数字会全线累加堆叠。
    # 本皮肤绘制层全部改绝对定位：行首与同行组合的 X=/Y= 纯数值统一补 # 前缀。
    import re as _re
    L4 = []
    for line in L3:
        line = _re.sub(r"^([XY])=(-?[\d.]+)(?![re])", r"\1=#\2", line)
        line = _re.sub(r"(?<= )Y=(-?[\d.]+)(?![re])", r"Y=#\1", line)
        L4.append(line)
    L3 = L4

    path = os.path.join(outdir, "vLLMSentinel.ini")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L3) + "\n")
    return path, total_h


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    path, h = main(outdir)
    print(f"written: {path}  (皮肤高度 {h}px)")
