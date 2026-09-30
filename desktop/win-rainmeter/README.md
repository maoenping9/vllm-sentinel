# vLLM Sentinel · Windows 桌面组件（Rainmeter 皮肤）

Mac Übersicht 组件（v97.x）的 Windows 平面版：模型服务 / GPU 16 卡阵列 / CPU 综合 /
电费与流量额度，版式与配色对齐 Mac 组件（3D 机箱图为 Mac 独有，此版按平面条呈现）。

## 截图

见 `preview_shot.png`（真实线上数据 1:1 布局预览）。

## 安装（一次约 10 分钟）

1. **装 Rainmeter**（≥4.5，必需——动态配色用到 4.5 特性）
   官网 https://rainmeter.net/ 下载安装，一路下一步。
2. **通内网**：装 EasyTier Windows 客户端（与 Mac 同组网，能 ping 通 `your-server-ip` 即可）。
3. **放皮肤**：把 `vLLMSentinel` 文件夹整个复制到
   `%APPDATA%\Rainmeter\Skins\`（资源管理器地址栏直接粘贴该路径）。
4. **改地址**（如果控制台不是 your-server-ip:8889）：右键皮肤 → Edit skin，或直接编辑
   `vLLMSentinel.ini` 顶部 `[Variables]` 里的 `SERVER`。
5. **加载**：打开 Rainmeter 主界面 → Load → vLLMSentinel → 点 `vLLMSentinel.ini`。
   拖皮肤本体移动位置；数据每 6 秒自动刷新。

## 使用

- 左键点击组件 → 浏览器打开 Web 控制台
- 右键组件 → Rainmeter 菜单（透明度、开机自启等）
- 头部右侧状态点：绿=实时 / 黄=数据延迟（隧道抖动，沿用旧数据）/ 红=离线

## 设计约定（改动前必读）

- **单一数据源**：一个请求 `GET {SERVER}/api/summary`，所有展示语义
  （模型归一、短名、配色序号、排序、三态、进度条档位）都在服务器
  `vllm-sentinel/backend/summary.py` 算好——客户端只画。模型增减、改名不需要动本皮肤。
- 数组固定槽位：模型 8 行 / GPU 16 行由服务端补空行，皮肤 Meter 池固定。
- 断连沿用旧值（与 Mac 组件 v97.3 同思路），刷新间隔 6s 大于取数耗时（v97.5 教训）。
- 版式/几何如需调整：改 `desktop/win-rainmeter/gen_skin.py` 常量后重新生成
  `vLLMSentinel.ini`，不要手改生成物。

## 常见问题

| 现象 | 处理 |
|---|---|
| 全组件显示 "--" / 状态红 | EasyTier 没起来或 SERVER 写错；浏览器直接开 `http://your-server-ip:8889/api/summary` 验证 |
| 文字发虚 | Rainmeter 菜单 → Skin → 勾 Auto update；系统缩放建议 100–125% |
| 中文方块 | 系统缺"微软雅黑 UI"字体（Win10/11 自带；Win7 需装雅黑） |
| 颜色不变化 | Rainmeter 版本 <4.5，升级后重载皮肤 |
