# vLLM Sentinel · Windows 桌面组件（Rainmeter 皮肤）v2

Mac Übersicht 组件（v97.x）的 Windows 平面版。显示模型服务 / GPU 16 卡阵列 / CPU 综合 /
电费与流量额度，配色与版式对齐 Mac 组件。

包内有两个皮肤：

| 皮肤 | 用途 |
|---|---|
| `vLLMSentinel` | 正式组件 |
| `vLLMSentinelSelftest` | **自检用**：出问题时先加载它，一眼分清是坐标渲染问题还是数据链路问题 |

## 安装（约 5 分钟）

1. **装 Rainmeter**：https://rainmeter.net/ （任意较新版本即可，本皮肤只用基础特性）
2. **通内网**：EasyTier Windows 客户端在线，能打开 `http://your-server-ip:8889/api/skin?part=top` 看到一坨 JSON
3. **放皮肤**：把 `vLLMSentinel` 和 `vLLMSentinelSelftest` 两个文件夹放进
   `%APPDATA%\Rainmeter\Skins\`
   （若之前装过旧版，先**删掉旧的 `vLLMSentinel` 文件夹再放新的**，否则会加载到旧文件）
4. **加载**：Rainmeter 主界面 → 找到 `vLLMSentinel` → 双击 `vLLMSentinel.ini`
5. 拖皮肤本体可移动位置；数据每 6 秒刷新；左键点击打开 Web 控制台

改服务器地址：右键皮肤 → 「编辑皮肤」，改 `[Variables]` 里的 `SERVER`。

## 出问题时的排查顺序

1. **先加载 `vLLMSentinelSelftest`**
   - 三行彩色文字自上而下分开 → Rainmeter 渲染正常，问题在数据链路
   - 第 4 行有「标题 / 状态 / 颜色」→ 数据链路正常
   - 第 5 行有彩条 → Bar 度量正常
2. **三行文字叠在一起** → 不是皮肤问题，是 Rainmeter 没重新加载（卸载后重新加载，或退出 Rainmeter 再开）
3. **数据行为空** → 在浏览器打开 `http://your-server-ip:8889/api/skin?part=top`：
   - 打不开 → EasyTier 没通或地址写错
   - 打得开但皮肤空 → 皮肤里的 `SERVER` 写错（注意不要有多余空格）
4. 还不行：Rainmeter 托盘图标右键 → 「关于」→ 「日志」标签，把日志文本发给 AI（日志会直接点名哪个节哪一行有问题）

## 数据链路

- 皮肤只发两个请求：`/api/skin?part=top`（81 个值）与 `/api/skin?part=gpu`（81 个值）
- **为什么是"值数组"而不是带字段名的 JSON**：Rainmeter 的 WebParser 单个亲度量最多 99 个
  `StringIndex`，且按字段名写正则会把皮肤绑死在 JSON 键序上（改一个字段就全线错位）。
  值数组 + 序号取值，两端只依赖一份「字段顺序表」。
- 展示语义（模型归一、短名、配色、排序、单位、取整、限长、状态三档）全部在服务器
  `backend/summary.py::build_skin_payload` 算好，皮肤只负责画。
- 字段顺序表：top = 标题 / 状态文字 / 状态色 / 模型表头 / 模型 8 行×4 / CPU 8 行×4 /
  额度 3 行×4 / 页脚；gpu = 表头 / 16 行×5（标签、显存、元信息、负载%、条色）。

## 改版式 / 改字段

- 版式：改 `gen_skin2.py` 顶部几何常量后重新生成，**不要手改 ini**
- 字段：先改 `backend/summary.py::build_skin_payload`，再同步 `gen_skin2.py` 的字段表
- 改完必须跑两个校验（都绿才能发布）：

```bash
python3 extract_whitelist.py            # 从官方文档快照重建选项白名单（偶尔重建即可）
python3 validate_ini.py build/vLLMSentinel/vLLMSentinel.ini     # 选项名是否真存在
python3 verify_skin.py  build/vLLMSentinel/vLLMSentinel.ini     # 正则实测 + 引用 + 坐标
```

## 已踩过的坑（v1 糊屏的原因，务必别再犯）

| 错误写法 | 为什么错 | 正确写法 |
|---|---|---|
| `Meter=Rectangle` | Rainmeter 没有 Rectangle 这种 Meter | `Meter=Bar`（进度条）/ `Meter=Shape` / `Meter=Image`+SolidColor |
| `StyleName=` | 不存在这个选项 → 动态样式全部失效 | 动态颜色用 `FontColor=[&某度量]` + `DynamicVariables=1` |
| `StringFormula=` | 不存在 → 派生数值全空 | `Measure=Calc` 的 `Formula=` |
| `FallbackString=` | 不存在 | WebParser 用 `ErrorString`；度量用 `Fallback` |
| `SectionParser=` / `SectionIndex=` | 不存在 | 子度量 `Measure=WebParser` + `URL=[父]` + `StringIndex=N` |
| `FontFamily=` | 字符串 meter 没这个选项 | `FontFace=` |
| 单个亲度量塞 154 个捕获组 | WebParser 上限 99 个 StringIndex | 拆成两个亲度量（本项目 top/gpu 各 81） |
| 右对齐列同时给 `X` 和 `W` | `StringAlign=Right` 时 X 是右边界，W 的裁剪框语义有歧义 | 右对齐只给 X（在服务端限长）；左对齐才用 W+ClipString |
| 样式节里写 `X=`/`Y=` | 虽则 Meter 自身优先，但极易误判（v1 曾误诊在此） | 样式节只放字体/颜色 |

以上每一条都由 `validate_ini.py`（官方文档白名单）与 `verify_skin.py` 机械拦截。
