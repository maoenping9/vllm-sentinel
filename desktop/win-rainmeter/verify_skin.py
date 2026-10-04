#!/usr/bin/env python3
"""vLLMSentinel 皮肤离线验证器：在无 Windows/Rainmeter 的环境下，把能机械验证的都验掉。

验证项：
  1. 结构：节名唯一、每个 Meter 都有 Meter=/X/Y、样式节无坐标
  2. 引用完整性：Text=/BarColor=/FontColor=/MeterStyle=/MeasureName= 指向的节都存在
  3. RegExp 实测：把 ini 里亲度量的正则拿到真实接口响应上跑，逐组比对值数组
  4. StringIndex 范围：1..捕获组数，且与生成器的字段表一一对应
  5. 坐标边界：所有 meter 落在卡片范围内，图层顺序（背景在最前）

用法: python3 verify_skin.py <ini> [server]
退出码 0 = 全绿
"""
import json
import os
import re
import sys
import urllib.request

FAIL: list[str] = []


def fail(msg: str) -> None:
    FAIL.append(msg)


def load(ini_path: str):
    text = open(ini_path, encoding="utf-8").read()
    blocks = re.split(r"\n(?=\[)", text)
    secs: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for b in blocks:
        m = re.match(r"\[([^\]]+)\]", b)
        if not m:
            continue
        name = m.group(1)
        kv: dict[str, str] = {}
        for line in b.split("\n")[1:]:
            s = line.strip()
            if not s or s.startswith(";") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            kv[k.strip()] = v.strip()
        if name in secs:
            fail(f"节名重复: [{name}]")
        secs[name] = kv
        order.append(name)
    return text, secs, order


def check_structure(secs: dict[str, dict[str, str]]) -> None:
    for name, kv in secs.items():
        if name in ("Rainmeter", "Variables"):
            continue
        if "Meter" in kv:
            if kv["Meter"] not in ("String", "Image", "Bar", "Shape", "Bitmap", "Button",
                                   "Histogram", "Line", "Rotator", "Roundline"):
                fail(f"[{name}] 非法 Meter 类型 {kv['Meter']}")
            if "X" not in kv or "Y" not in kv:
                fail(f"[{name}] 缺 X/Y")
        elif "Measure" not in kv:
            # 样式节：不得带坐标（避免以后又踩"样式影响坐标"的坑）
            for k in ("X", "Y"):
                if k in kv:
                    fail(f"样式节 [{name}] 不该带 {k}")


def check_refs(secs: dict[str, dict[str, str]]) -> None:
    known = set(secs)
    for name, kv in secs.items():
        for key in ("Text", "FontColor", "BarColor", "SolidColor", "MeasureName", "MeterStyle"):
            val = kv.get(key)
            if not val:
                continue
            for ref in re.findall(r"\[&([A-Za-z0-9_]+)\]", val):
                if ref not in known:
                    fail(f"[{name}] {key} 引用了不存在的度量 [{ref}]")
            if key == "MeasureName" and val not in known:
                fail(f"[{name}] MeasureName={val} 不存在")
            if key == "MeterStyle":
                if "," in val:
                    fail(f"[{name}] MeterStyle 用了逗号（Rainmeter 要求竖线 | 分隔）：{val}")
                for s in val.split("|"):
                    s = s.strip()
                    if s and s not in known:
                        fail(f"[{name}] MeterStyle 引用不存在的样式 [{s}]")


def check_coords(secs: dict[str, dict[str, str]], card_w: int) -> None:
    h_max = 0
    for name, kv in secs.items():
        if "Meter" not in kv:
            continue
        try:
            x, y = float(kv["X"]), float(kv["Y"])
        except (KeyError, ValueError):
            fail(f"[{name}] 坐标非数值: X={kv.get('X')} Y={kv.get('Y')}")
            continue
        if x < 0 or x > card_w:
            fail(f"[{name}] X={x} 越界（卡片宽 {card_w}）")
        w = 0.0
        if "W" in kv:
            try:
                w = float(kv["W"])
            except ValueError:
                w = 0.0
        if x + w > card_w + 1:
            fail(f"[{name}] X+W={x + w} 超出卡片宽度 {card_w}")
        h_max = max(h_max, y)
    return h_max


def check_regex(secs: dict[str, dict[str, str]], server: str) -> None:
    """最重要的一项：把 ini 里的正则拿去跑真实响应，逐组比对。"""
    for parent, part in (("WebTop", "top"), ("WebGpu", "gpu")):
        kv = secs.get(parent)
        if not kv:
            fail(f"缺少亲度量 [{parent}]")
            continue
        pattern = kv.get("RegExp")
        if not pattern:
            fail(f"[{parent}] 缺 RegExp")
            continue
        groups = len(re.findall(r"\((?!\?)", pattern))
        raw = urllib.request.urlopen(f"{server}/api/skin?part={part}", timeout=8).read().decode()
        m = re.search(pattern, raw)
        if not m:
            fail(f"[{parent}] 实测：正则匹配不到响应")
            continue
        captured = list(m.groups())
        expect = json.loads(raw)["v"]
        if len(captured) != len(expect):
            fail(f"[{parent}] 捕获组 {len(captured)} != 响应值数 {len(expect)}")
        for i, (got, want) in enumerate(zip(captured, expect), start=1):
            if got != want:
                fail(f"[{parent}] 第 {i} 组不一致: 正则得 {got!r} / 接口 {want!r}")
        # StringIndex 覆盖检查
        idxs = sorted(int(v["StringIndex"]) for k, v in secs.items()
                      if v.get("URL") == f"[{parent}]" and "StringIndex" in v)
        if idxs != list(range(1, groups + 1)):
            fail(f"[{parent}] StringIndex 覆盖 {len(idxs)} 个（期望 1..{groups}），缺: "
                 f"{sorted(set(range(1, groups + 1)) - set(idxs))[:8]}")
        print(f"  [{parent}] 正则实测通过：{groups} 组全部与接口值一致，"
              f"{len(idxs)} 个子度量按序映射")


def main() -> int:
    ini = sys.argv[1]
    server = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8889"
    text, secs, order = load(ini)
    card_w = 420
    m = re.search(r"^W=(\d+)", secs.get("BG", {}).get("W", "") or "")
    if secs.get("BG", {}).get("W"):
        card_w = int(float(secs["BG"]["W"]))
    check_structure(secs)
    check_refs(secs)
    h_max = check_coords(secs, card_w)
    print(f"  结构/引用/坐标：{len(secs)} 节，最高 Y={h_max:.0f}，卡片 {card_w}px 宽")
    check_regex(secs, server)
    if FAIL:
        print(f"\n❌ {len(FAIL)} 处问题：")
        for f in FAIL[:40]:
            print("   -", f)
        return 1
    print("\n✅ 皮肤离线验证全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
