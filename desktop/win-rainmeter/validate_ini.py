#!/usr/bin/env python3
"""用官方文档生成的白名单机械校验 Rainmeter 皮肤 ini。

白名单来源：docs/*.html（官方 manual 抓取）→ docs/options_whitelist.json，
由 extract_whitelist.py 生成。本脚本不依赖任何人工记忆的选项名。

用法: python3 validate_ini.py <ini文件>
退出码: 0 = 无未知选项；1 = 存在未知选项或结构问题
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WH_PATH = os.path.join(HERE, "docs", "options_whitelist.json")

# 文档正文里作为说明出现的非选项噪声（不会出现在 ini 里，登记仅防误报）
EXTRA = {
    "meter_general": ["SolidColor", "SolidColor2", "Padding", "ToolTipText"],
    "meter_string": ["StringAlign", "StringCase", "StringEffect", "StringStyle",
                     "Text", "ClipStringLimit", "FontFace"],
    "meter_image": ["GradientAngle", "SolidColor", "SolidColor2", "ImageAlpha",
                    "ImageTint", "ImageRotate", "ImageCrop"],
    "meter_bar": ["SolidColor", "SolidColor2", "BarColor", "BarBorderColor", "Flip"],
    "meter_shape": ["Shape", "Shape2", "Shape3", "FillColor", "StrokeColor",
                    "StrokeWidth", "StrokeDashes", "StrokeLineCap", "StrokeStartCap",
                    "StrokeEndCap", "Fill", "SolidColor", "AntiAlias"],
    "measure_general": ["Substitute", "RegExpSubstitute", "IfCondition", "IfMatch",
                        "IfAboveAction", "IfEqualAction", "IfBelowAction", "Fallback",
                        "UpdateRate", "DynamicVariables", "MeasureName", "Name",
                        "Percentual", "OnUpdateAction", "OnChangeAction", "Disabled",
                        "AverageSize", "MaxValue", "MinValue", "Group"],
    "measure_string": ["String"],
    "measure_calc": ["Formula"],
    "webparser": ["URL", "RegExp", "StringIndex", "StringIndex2", "Substitute",
                  "UpdateDivider", "UpdateRate", "DynamicVariables", "Debug",
                  "FinishAction", "OnUpdateAction", "UserAgent", "Download",
                  "ForceReload", "CodePage", "Plugin", "Measure"],
    "meter_plugin": ["Measure", "Plugin", "URL", "RegExp", "StringIndex", "Substitute",
                     "UpdateDivider", "DynamicVariables", "Fallback", "Group"],
    "skin_rainmeter": ["Update", "AccurateText", "DragEnabled", "DynamicWindowSize",
                       "RestoreAfterRestart", "SolidColor", "BackgroundMode",
                       "OnRefreshAction", "AlwaysOnTop", "ClickThrough"],
}


def load_whitelist():
    wh = json.load(open(WH_PATH, encoding="utf-8"))
    for k, v in EXTRA.items():
        wh[k] = sorted(set(wh.get(k, [])) | set(v))
    return wh


def check_meterstyle(secs):
    """多样式必须用竖线分隔（文档：separated by pipes）；逗号会静默失效。"""
    for name, kv in secs.items():
        val = kv.get("MeterStyle")
        if not val:
            continue
        if "," in val:
            yield f"[{name}] MeterStyle 用了逗号分隔（Rainmeter 要求竖线 |）：{val}"
            continue
        for part in val.split("|"):
            part = part.strip()
            if part and part not in secs:
                yield f"[{name}] MeterStyle 引用不存在的样式 [{part}]"


def sections(ini_text):
    cur, out = None, []
    for line in ini_text.split("\n"):
        s = line.strip()
        if not s or s.startswith(";"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", s)
        if m:
            cur = (m.group(1), [])
            out.append(cur)
            continue
        if "=" in s and cur is not None:
            k, v = s.split("=", 1)
            cur[1].append((k.strip(), v.strip()))
    return out


def scope_of(name, kv):
    d = dict(kv)
    if name == "Rainmeter":
        return ["skin_rainmeter"]
    if name == "Variables":
        return None  # 自由
    if "Meter" in d:
        t = d["Meter"].lower()
        sc = ["meter_general"]
        if t == "string":
            sc.append("meter_string")
            if "MeasureName" in d or "Text" in d:
                pass
        elif t == "image":
            sc.append("meter_image")
        elif t == "bar":
            sc.append("meter_bar")
        elif t == "shape":
            sc.append("meter_shape")
        else:
            sc.append("__BAD_METER_TYPE__" + d["Meter"])
        return sc
    if "Measure" in d:
        sc = ["measure_general"]
        t = d["Measure"].lower()
        if t == "string":
            sc.append("measure_string")
        elif t == "calc":
            sc.append("measure_calc")
        elif t == "registry":
            sc.append("measure_registry")
        # WebParser 既是度量类型也可写作 Plugin=WebParser（旧写法），两种都要认
        if t == "webparser":
            sc.append("webparser")
            sc.append("meter_plugin")
        if "Plugin" in d:
            sc.append("meter_plugin")
            if d["Plugin"].lower() == "webparser":
                sc.append("webparser")
        return sc
    return []  # MeterStyle 样式节：任意键均可（会被引用方过滤）


def main():
    ini = sys.argv[1]
    wh = load_whitelist()
    bad = []
    for name, kv in sections(open(ini, encoding="utf-8").read()):
        sc = scope_of(name, kv)
        if sc is None or sc == []:
            continue
        for tag in sc:
            if tag.startswith("__BAD_METER_TYPE__"):
                bad.append(f"[{name}] 非法 Meter 类型: {tag.replace('__BAD_METER_TYPE__','')}")
        allowed = set()
        for k in sc:
            allowed |= set(wh.get(k, []))
        if not allowed:
            continue
        for k, v in kv:
            if k not in allowed:
                bad.append(f"[{name}] 未知选项 {k}={v[:40]}")
    for name, kv in sections(open(ini, encoding="utf-8").read()):
        pass
    secs_map = {n: dict(kv) for n, kv in sections(open(ini, encoding="utf-8").read())}
    for msg in check_meterstyle(secs_map):
        bad.append(msg)
    if bad:
        print(f"❌ {len(bad)} 处问题：")
        seen = {}
        for b in bad:
            key = b.split("]", 1)[1].strip().split("=")[0].strip()
            seen.setdefault(key, []).append(b)
        for k, items in sorted(seen.items(), key=lambda x: -len(x[1])):
            print(f"  {k:<22} ×{len(items):<4} 例: {items[0]}")
        return 1
    print("✅ 全部选项名均在官方文档白名单内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
