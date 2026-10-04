#!/usr/bin/env python3
"""从官方 manual 的本地 HTML 快照生成选项白名单（docs/options_whitelist.json）。

白名单 = 各文档页里出现的 <dt id="..."> 与 <code>名</code> 记号，按作用域归并：
  meter_general / meter_string / meter_image / meter_bar / meter_shape
  measure_general / measure_string / measure_calc / webparser / skin_rainmeter

生成后由 validate_ini.py 机械校验皮肤 ini，凡不在白名单的键都视为错误——
这样"我凭印象发明的选项"（StyleName/StringFormula/FallbackString/SectionParser 等）
会被立刻挡下，而不是等实机糊屏才发现。

抓取快照：见 docs/ 下同名 html；更新快照用 curl 拉取官方页即可。
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")

MAP = {
    "meters_general-options.html": ["meter_general"],
    "meters_string.html": ["meter_string"],
    "meters_image.html": ["meter_image"],
    "meters_bar.html": ["meter_bar"],
    "meters_shape.html": ["meter_shape"],
    "measures_general-options.html": ["measure_general"],
    "measures_string.html": ["measure_string"],
    "measures_calc.html": ["measure_calc"],
    "webparser.html": ["webparser", "meter_plugin"],
    "plugins_webparser.html": ["webparser", "meter_plugin"],
    "skins_rainmeter-section.html": ["skin_rainmeter"],
    "mouse_actions.html": ["meter_general"],
}


def tokens(path):
    text = open(path, encoding="utf-8", errors="ignore").read()
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S)
    names = set()
    for m in re.finditer(r'<dt[^>]*id="([^"]+)"', text):
        names.add(m.group(1))
    # 单字母选项（X/Y/W/H）也要收：长度 1~25
    for m in re.finditer(r"<code>([A-Za-z][A-Za-z0-9_]{0,24})</code>", text):
        names.add(m.group(1))
    # 文档里选项常写成标题/锚点（<h2 id="StringIndex"> 与 <a href="#StringIndex">）
    for m in re.finditer(r'(?:id|href="#)="?([A-Za-z][A-Za-z0-9_]{0,24})"', text):
        names.add(m.group(1))
    return {n for n in names if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,24}", n)}


def main():
    wh: dict[str, set[str]] = {}
    for fname, scopes in MAP.items():
        path = os.path.join(DOCS, fname)
        if not os.path.exists(path):
            print(f"跳过（缺快照）: {fname}")
            continue
        toks = tokens(path)
        for s in scopes:
            wh.setdefault(s, set()).update(toks)
    out = {k: sorted(v) for k, v in wh.items()}
    dest = os.path.join(DOCS, "options_whitelist.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in sorted(out):
        print(f"{k:<16} {len(out[k]):>4} 项")
    print("written:", dest)


if __name__ == "__main__":
    main()
