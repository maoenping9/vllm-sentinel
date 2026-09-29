//
// vLLM Sentinel — macOS 桌面小组件 (Übersicht)
// 组件版本 v97.2 · 随 vLLM Sentinel v2.2 发布（2026-09-29）
// 直接渲染在桌面上：壁纸之上、窗口之下，2 秒实时刷新。
//
// 数据源：vLLM Sentinel 控制台 /api/state
// 取数方式：curl（Mac 本地执行，无 CORS 问题）
//
// v21 已修复：模型服务"按模型聚合"的 tok/KV 用数值相加（原 num() 返回字符串被
// 字符串拼接，导致多实例 Qwen 出现 24000t/s/2333% 的错误值）。
//
// 更新记录：
//   - v97.2（随 v2.2 发布）：流量累计改读后端持久累加值（不再跳动）；本月/本年额度条改用真实自然月/年累计；
//     CPU 区新增内存使用率条 + 内存条温度 0/1 + 内存供电温度 0/1；GPU 转速读数修复（多串口盒选口 + 帧解析）；
//     DeepSeek V4.1 / Qwen3.8 家族命名对齐；卡堆间距按卡数自适应
//   - GPU 全量显示：14 张卡全部列出（不再截断 Top-N），按 负载×0.7+温度×0.3 降序
//   - 负载条改为 CSS transition 实时动画：宽度平滑渐变 + 温度阈值变色（>=72C 红橙色，否则蓝绿色）
//   - 新增 CPU 区块：逐核负载条（最多 32 线程）+ 总使用率/频率
//   - 内存 / 磁盘IO / 网络 / 电源额定汇总
//   - v10 双塔机箱 3D 布置图（2026-09-12 现场版）：
//     · 真实拓扑：3 台 1000D Commander（A 路 3-2.3 / B 路 3-4.2 / 3-4.3），每台 6 口
//     · 风扇转速全部实时：GPU 专属扇=PWM×3450 反算（后端 /etc/gpu-mapping.conf 总线版映射），
//       机箱扇=hwmon tach 实测 RPM（经 BMC/宿主机读数），不再硬编码
//     · 双塔 3D 造型：左塔 A 路 + 右塔 B 路，13 卡垂直堆叠，前后仓进风 → 显卡仓 → 后排风
//     · 风扇叶片 CSS 旋转动画：转速越快转得越快（animation-duration 反比于 RPM）
//   - v12/v13 整体重构（2026-09-13）：
//     · v12：单一 world 舞台共享透视 + 双塔同转 + 共享底座（解决割裂）
//     · v13：360°整圈自转会在侧向塌缩成细条（截图证实）→ 改为 -20°↔-48° 摆动（18s 来回，永不侧翻）
//     · 1000D 真机质感（guru3d 官方口径）：烟熏钢化玻璃面板（深色半透明）+ 拉丝铝描边（银灰金属边）
//     · 前面板 G1 进风/G2 排风 + 顶排扇 + 右侧 13 卡竖装温度条 + 塔脚投影 + 共享底座
//   - v23 机箱重构（2026-09-13，现场拓扑校正版）：
//     · 左塔（系统塔）：前面板 3×G1 + 中下部 CPU/FCH + 下部后 1×G2 + 顶部 3×12NF
//     · 右塔（GPU 塔）：后面 4×G2 排风 + 中部 13×170HX 竖装（各带 9733）+ 顶部预留 +
//       前面板 3×G1 + 最下 1×12NF
//     · GPU 仓横向 13 条：每卡一条（温度半 + 功耗条半），实时数据直读 gpu.items
//     · spinDot 对齐 SVG 圆心（v22 错位修复）；num() 遮蔽崩溃修复（v23 同批）
//   - v96 网络流量周期（2026-09-22，用户定稿）：
//     · 新增「网络流量（20日起）」区块：每月 20 号开始到下个月 20 号（跨月周期，含当天）
//     · 总流量配额 1.5TB（NET_TOTAL_TB），周期累计达 1TB（NET_WARN_TB）时数值与进度条变红
//     · 周期累计由 tx/rx 瞬时速率积分还原（netCycleTraffic，20 号 00:00 起算）
//   - v96.1 手工基准（2026-09-22）：
//     · 用户实测周期内已用 250G，积分只算出 ~80G（单网卡速率漏 Mac/其他设备全网流量）
//     · NET_USED_GB_OVERRIDE=250：显示与红色判断用 max(积分, 250G)，积分超过后自动切回
//     · 显示值带 * 后缀表示当前用的是手工基准（积分尚未追上）
//
// 安装（Intel Mac）：
//   1. 安装 Übersicht:  brew install --cask ubersicht
//   2. 把整个 vllm-sentinel.widget 文件夹拷到:
//      ~/Library/Application Support/Übersicht/widgets/
//   3. 如服务器 IP 不是 your-server-ip:8889，改下面 SERVER 常量即可。
//

// ===== 可配置 =====
const SERVER = "http://your-server-ip:8889" // vLLM Sentinel 控制台地址（改成你的服务器 IP）
const REFRESH_MS = 2000                        // 刷新间隔（2026-09-22 流量优化：1000→2000ms，流量减半；摆动 20s 周期 sin 波 2s 步长仍平滑）
const HOT_TEMP = 75                           // >= 此温度变红（GPU 负载条 + CPU 温度）
const OTHER_W = 200                            // 整机功耗估算的"其他"补偿值
const PSU = "2600 + 2200 W"                    // 电源额定
// v61 电费预算额度（进度条分母，改这里一处即可）：月 500 元 / 年 6000 元
// TODO: [待确认] 用户说"修改本月额度 年额度"但未给新数值，暂沿用 500/6000
const MONTH_BUDGET = 500                       // 本月电费预算 元
const YEAR_BUDGET = 6000                       // 本年电费预算 元

// ===== v96 网络流量周期（2026-09-22 用户定稿）：每月 20 号开始到下个月 20 号 =====
// 总流量配额 1.5TB，累计达 1TB（≈2/3）时进度条变红提示
const NET_CYCLE_START_DAY = 20                 // 周期起点：每月 20 号（含当天）
const NET_TOTAL_TB = 1.5                       // 总流量配额 TB
const NET_WARN_TB = 1.0                        // 达到此累计流量时标红（红色提示）
// v96.1 手工基准（2026-09-22）：用户实测"到今天(9/22)为止周期内已用 250G"，
// 而 /api/state 的 tx/rx 只是服务器单网卡速率（积分仅 ~80G），漏了 Mac/其他设备等全网流量。
// 显示与红色判断都用 max(积分, OVERRIDE)——今天显示 250G；积分超过 250G 后自动切回积分跟踪。
const NET_USED_GB_OVERRIDE = 250               // 周期内已用 GB（用户手工实测值，改这里）

// ===== 实时电费（浙江滨江 办公楼商业用电 单一制不满1千伏，2026年9月价，国网浙江代理购电公告） =====
const PRICE_FLAT = 0.736945                    // 平段/非分时 元/度
const PRICE_PEAK = 1.133475                    // 高峰 元/度
const PRICE_VALLEY = 0.457041                  // 低谷 元/度
// 春秋季(2-6月、9-11月)：低谷 0:00-7:00、11:00-14:00；平段 7:00-11:00、14:00-16:00、23:00-24:00；高峰 16:00-23:00
// 夏冬季(1月、7月、8月、12月)：低谷/平段同春秋；尖峰 18:00-22:00；高峰 16:00-18:00、22:00-23:00
function touPrice(date) {
  const hm = date.getHours() * 60 + date.getMinutes()
  const summer = [0, 6, 7, 11].indexOf(date.getMonth()) >= 0
  if (hm < 420 || (hm >= 660 && hm < 840)) return { price: PRICE_VALLEY, tier: "谷" }
  if (summer && hm >= 1080 && hm < 1320) return { price: PRICE_PEAK * 1.0, tier: "尖" }
  if ((hm >= 420 && hm < 660) || (hm >= 840 && hm < 960) || hm >= 1380) return { price: PRICE_FLAT, tier: "平" }
  return { price: PRICE_PEAK, tier: summer ? "峰" : "峰" }
}

// ===== v96 网络流量周期函数（每月 20 号 → 下月 20 号，跨月周期） =====
// 返回 { tb: 周期累计 TB, warn: 是否已达 1TB 红色提示, days: 周期已过天数, baseGb: 计入的手工基准 GB }
// v97.2（2026-09-29 用户："网络流量显示还是没有实时显示，会跳动，0.41这个数据是对的"）：
//   ① 周期累计改为读**后端持久累加值**（/api/energy 的 net_cycle_bytes）——后端按 WAN 出口网卡
//      （默认路由口）累计，LAN 互传/VPN/docker 网桥不计入 ISP 配额，且日汇总表永不被 31 天裁剪，
//      所以数值单调递增、每 2 秒实时刷新，不再随瞬时速率跳动。
//   ② 旧实现是「瞬时速率 × 周期已过时长」，同一秒内速率一变数值就跳（且把 10G 内网互传也算进去，
//      9/28 单日曾虚增 2.9TB）。仅在拿到不到后端字段时（旧后端）才退回旧算法兜底。
function netCycleTraffic(nowMs, net, energy) {
  const n = nowMs ? new Date(nowMs) : new Date()
  const day = n.getDate()
  // 周期起点：day>=20 → 本月 20 号 00:00；day<20 → 上月 20 号 00:00
  let startMs
  if (day >= NET_CYCLE_START_DAY) {
    startMs = new Date(n.getFullYear(), n.getMonth(), NET_CYCLE_START_DAY).getTime()
  } else {
    const pm = new Date(n.getFullYear(), n.getMonth(), 0)   // 上月最后一天 → 取上月
    startMs = new Date(pm.getFullYear(), pm.getMonth(), NET_CYCLE_START_DAY).getTime()
  }
  const elapsedHours = Math.max(0, (n.getTime() - startMs) / 3600000)
  const days = Math.floor(elapsedHours / 24)
  // ① 首选：后端持久累计（真实、单调、实时）
  if (energy && typeof energy.net_cycle_bytes === "number") {
    const tb = energy.net_cycle_bytes / 1e12
    const baseGb = typeof energy.net_cycle_base_bytes === "number" ? energy.net_cycle_base_bytes / 1e9 : 0
    return { tb: tb, warn: tb >= NET_WARN_TB, days: days, baseGb: baseGb, source: "api" }
  }
  // ② 兜底：旧后端 —— 瞬时速率 × 周期已过时长（会跳动，仅当拿不到后端字段时用）
  const tbIntegral = ((Number(net.tx_bps) || 0) + (Number(net.rx_bps) || 0)) * elapsedHours * 3600 / 1e12
  const tb = Math.max(tbIntegral, NET_USED_GB_OVERRIDE / 1000)
  return { tb: tb, warn: tb >= NET_WARN_TB, days: days, baseGb: NET_USED_GB_OVERRIDE, source: "integral" }
}

// ===== 数据拉取 =====
export const command = `curl -s --max-time 10 --retry 1 --retry-delay 1 ${SERVER}/api/state?light=1 2>/dev/null; echo; curl -s --max-time 10 ${SERVER}/api/energy 2>/dev/null`
export const refreshFrequency = REFRESH_MS

// ===== 样式（深海蓝玻璃，与控制台 midnight 主题一致） =====
export const className = `
  top: 24px; right: 24px;
  width: 336px;
  font-family: -apple-system, "Helvetica Neue", sans-serif;
  color: #e2e8f0;
  transform: rotate(0deg);
`

const styles = {
  card: {
    // 不透明纯色背景：墙纸完全不透出，重渲染时不重新模糊，彻底消除闪烁
    background: "linear-gradient(150deg, #0d1828, #060c16)",
    border: "1px solid rgba(110,140,255,.22)",
    borderRadius: 16,
    padding: "14px 14px 10px",
    boxShadow: "0 14px 36px rgba(0,0,0,.30)",
    WebkitFontSmoothing: "antialiased",
  },
  head: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  brand: { fontSize: 13, fontWeight: 800, letterSpacing: ".06em", color: "#dbe4ff", textShadow: "0 1px 3px rgba(0,0,0,.5)" },
  live: { display: "flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 600, color: "#8ef0b4", textShadow: "0 1px 2px rgba(0,0,0,.5)" },
  dot: { width: 6, height: 6, borderRadius: 3, background: "#34d399", boxShadow: "0 0 6px rgba(52,211,153,.8)" },
  instDotOn: { width: 5, height: 5, borderRadius: 3, background: "#34d399", boxShadow: "0 0 5px rgba(52,211,153,.8)", flexShrink: 0 },
  instDotOff: { width: 5, height: 5, borderRadius: 3, background: "#ef4444", boxShadow: "0 0 5px rgba(239,68,68,.7)", flexShrink: 0 },
  instStatus: { display: "flex", alignItems: "center", gap: 3, marginLeft: 5, fontSize: 10, fontWeight: 700, flexShrink: 0 },
  dotOff: { width: 6, height: 6, borderRadius: 3, background: "#ef4444" },
  section: { fontSize: 10, fontWeight: 800, letterSpacing: ".1em", color: "#8ba3ff", margin: "9px 0 4px", textShadow: "0 1px 2px rgba(0,0,0,.5)" },
  inst: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid rgba(110,140,255,.14)" },
  instName: { fontSize: 11, fontWeight: 700, color: "#f1f5f9", textShadow: "0 1px 2px rgba(0,0,0,.5)" },
  instVal: { fontFamily: "\"JetBrains Mono\",\"SF Mono\",monospace", fontSize: 11, fontWeight: 500, color: "#aab8cc", flexShrink: 0, marginLeft: "auto" },
  gpuRow: { display: "flex", alignItems: "center", gap: 8, padding: "3px 0" },
  gpuIdx: { fontFamily: "\"JetBrains Mono\",\"SF Mono\",monospace", fontSize: 10, fontWeight: 700, color: "#8ba3ff", width: 108, flexShrink: 0, whiteSpace: "nowrap", textShadow: "0 1px 2px rgba(0,0,0,.5)" },
  gpuMem: { fontFamily: "\"JetBrains Mono\",\"SF Mono\",monospace", fontSize: 9, fontWeight: 600, color: "#aab8cc", width: 40, textAlign: "right", flexShrink: 0 },
  gpuBarWrap: { flex: 1, height: 5, borderRadius: 3, background: "rgba(110,140,255,.20)", overflow: "hidden" },
  gpuBar: { display: "block", height: "100%", minWidth: 2, borderRadius: 3, background: "linear-gradient(90deg,#6e8cff,#34d399)", transition: "background .9s ease-out" },
  gpuBarHot: { display: "block", height: "100%", minWidth: 2, borderRadius: 3, background: "linear-gradient(90deg,#f59e0b,#ef4444)", transition: "background .9s ease-out" },
  // v23 修复：GPU 行行内 { background: mColor } 只替换 background-image（渐变是 image），
  // background-color 仍是 gpuBarHot 的红橙 —— 温度≥75C 时模型色盖不住报警色。补 bg-color 覆盖。
  gpuBarModel: { display: "block", height: "100%", minWidth: 2, borderRadius: 3, transition: "background .9s ease-out" },
  gpuMeta: { fontFamily: "\"JetBrains Mono\",\"SF Mono\",monospace", fontSize: 9, fontWeight: 500, color: "#aab8cc", width: 92, textAlign: "right", flexShrink: 0 },
  barRow: { display: "flex", alignItems: "center", marginTop: 3 },
  barWrap: { flex: 1, height: 4, borderRadius: 2, background: "rgba(110,140,255,.20)", overflow: "hidden" },
  barFill: { display: "block", height: "100%", minWidth: 2, borderRadius: 2, background: "linear-gradient(90deg,#6e8cff,#7ee2a8)", transition: "background .9s ease-out" },
  kvRow: { display: "flex", justifyContent: "space-between", marginTop: 4 },
  kvLabel: { fontSize: 11, fontWeight: 500, color: "#aab8cc" },
  kvVal: { fontFamily: "\"JetBrains Mono\",\"SF Mono\",monospace", fontSize: 11, fontWeight: 600, color: "#f1f5f9", textShadow: "0 1px 2px rgba(0,0,0,.4)" },
  kvValGpu: { fontFamily: "\"JetBrains Mono\",\"SF Mono\",monospace", fontSize: 11, fontWeight: 700, color: "#6a83d0", textShadow: "0 1px 2px rgba(0,0,0,.5)" },
  foot: { marginTop: 8, paddingTop: 6, borderTop: "1px solid rgba(110,140,255,.12)", display: "flex", justifyContent: "space-between", fontSize: 10, fontWeight: 500, color: "#8b98ad" },
  fanScene: { marginTop: 6 },
  sceneSvg: { display: "block", width: 340, height: 300, margin: "0 auto" },
  chip: { position: "absolute", fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 6, background: "rgba(10,20,36,.82)", border: "1px solid rgba(110,140,255,.45)", color: "#cfe0ff", whiteSpace: "nowrap" },
  chipOk: { color: "#7ee2a8", borderColor: "rgba(126,226,168,.5)" },
  zoneLabel: { position: "absolute", fontSize: 8, fontWeight: 700, color: "#8ba3ff", letterSpacing: ".04em" },
  fanDot: { position: "absolute", borderRadius: "50%", background: "radial-gradient(circle at 35% 30%, #9fc4ff, #4e7bd0 70%)", boxShadow: "0 0 4px rgba(110,140,255,.5)" },
  fanDotStop: { position: "absolute", borderRadius: "50%", background: "radial-gradient(circle at 35% 30%, #ff8787, #c81e1e 70%)", boxShadow: "0 0 6px rgba(239,68,68,.8)" },
  fanDotSpin: { position: "absolute", borderRadius: "50%", background: "radial-gradient(circle at 35% 30%, #ffe08a, #e0912f 70%)", boxShadow: "0 0 6px rgba(224,145,47,.6)" },
  fanRing: { position: "absolute", borderRadius: "50%", border: "1px dashed rgba(110,140,255,.35)" },
  bladeWheel: { position: "absolute", borderRadius: "50%", animation: "vss-spin 1.6s linear infinite", transformOrigin: "50% 50%" },
  cardSlab: { position: "absolute", left: 10, height: 4, borderRadius: 2, background: "linear-gradient(90deg, rgba(110,140,255,.55), rgba(52,211,153,.45))" },
  cardSlabHot: { position: "absolute", left: 10, height: 4, borderRadius: 2, background: "linear-gradient(90deg, #f59e0b, #ef4444)" },
  airflowArrow: { position: "absolute", fontSize: 11, color: "rgba(126,226,168,.75)" },
  fanLegend: { fontSize: 9, color: "#8b98ad", marginTop: 6, textAlign: "center" },
}
// 风扇叶片旋转 keyframes（Übersicht 注入全局 <style>；页面版同样内联）
// v24 场景改为【构建期 3D 投影 SVG】：参考 1000D 真机口径（BuildCores 官方图，等轴 3/4 视角），
// 双塔立方体的 6 个面 + 13 卡 + 风扇全部在构建期用 3D 旋转矩阵算好投影坐标，直接画成静态
// SVG polygon/circle —— 无 preserve-3d 依赖（v12-v14 截图证实 WKWebView 拍平），但保留真 3D 体感。
// 摆动动画用 2D transform rotate（-14°↔-38°，24s 来回）模拟机箱左右转头，永不侧翻。
// 实时数据用纯 2D 芯片叠加；叶片旋转指示用 CSS 动画（2D 元素，不受影响）。
const FAN_KEYFRAMES = `
@keyframes vss-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes vss-airflow { 0% { opacity: .15; transform: translateY(0) } 50% { opacity: .85 } 100% { opacity: .15; transform: translateY(-3px) } }
`

// ===== 3D 投影引擎（v25，构建期一次性计算） =====
// 等轴投影：yaw（水平转角）+ pitch（俯角）→ (x, y) 屏幕坐标
// v42 修正（2026-09-22）：用户反馈"不是让你调转方向，是在原来的基础上调换下方向"
// ——撤销 v41 的视角旋转（yaw=-75°），恢复原视图 yaw=-25° SC=0.82 OY=64.5；
// 只对调方位含义：右外壁（窄条）=新前面、正面（大面）=新右面、
// 旧左面=新后面、旧后面=新左面（CPU 仓）——方位标注对调体现。
// 显卡条不动（x[-145,90] z=35）；GPU 扇条右缘外（x_old=100）、卡号条内右端对应。
const ISO_YAW = -25 * Math.PI / 180
// v81：pitch 2°→10°——顶面投影 9px→46px 宽，顶面立体感明显（用户："顶部要看着宽一点"）
const ISO_PITCH = 10 * Math.PI / 180
// v80 纯 yaw 扫摆（专家方案 d）：把摆动搬进 isoProject——机箱真水平转头
// （侧壁宽呼吸 57→70px、前面板 263→240px、竖直棱线全程竖直无倾斜），
// CSS 2D rotate 是屏幕平面整体旋转（跷跷板倾斜+平移），观感是"前后摆动"故弃
// v81：幅度 ±4°→±8°（用户"摆动幅度很小"），refreshFrequency 2000→1000ms 步长减半
// v82：摆动中心 -34°→-38°（左壁 52→58px 更宽，后面立体面加宽），幅度 ±8° 保持
const ISO_YAW_BASE = -38 * Math.PI / 180   // 摆动中心（-38° 左壁更宽）
const SWING_AMP = 12 * Math.PI / 180        // v87 幅度 ±12°（-26°↔-50°，用户：转动幅度大一点）
const SWING_PERIOD = 26000                 // v87 26s 一个来回（更慢更流畅，用户：流畅一点）
const spinYaw = function () {
  if (!SWING_AMP) return ISO_YAW
  return ISO_YAW_BASE + SWING_AMP * Math.sin(2 * Math.PI * (Date.now() % SWING_PERIOD) / SWING_PERIOD)
}
// v67 180° 旋转：绕竖直轴转 180°（x、z 取反），从背面看机箱——
// 大面=后板(z=-55)、窄条=左外壁(x=-155)、可见顶面不变；风扇/卡条/标注随整机一起转。
// 投影 x 范围对称[-160,160]，居中偏移(PJ_OX/PJ_OY/SC)无需重算。
const ROT_180 = true
// 3D 点 (x, y, z) → 屏幕 (sx, sy, depth)：绕 Y 轴转 yaw 再绕 X 轴转 pitch，正交投影
// x 向右、y 向下（屏幕系）、z 向观察者；v78 返回第三元素 z1（面深度排序用，pj 只取前两个）
const isoProject = function (x, y, z) {
  if (ROT_180) { x = -x; z = -z }
  const YAW = spinYaw()
  const cosY = Math.cos(YAW), sinY = Math.sin(YAW)
  const cosP = Math.cos(ISO_PITCH), sinP = Math.sin(ISO_PITCH)
  // 绕 Y 轴
  const x1 = x * cosY + z * sinY
  const z1 = -x * sinY + z * cosY
  // 绕 X 轴（y 向下为正：俯视时远处的 y 更靠上）
  const y2 = y * cosP - z1 * sinP
  return [x1, y2, z1]
}
// v25：投影范围居中偏移（构建期算好：两座独立塔 x∈[-155,-15]∪[15,155]、z∈[-55,55]、CH=170）
// v81：pitch=10° 重算居中（minX*SC=-141.3 minY*SC=-20.5 → OX=149.3 OY=28.5）
const PJ_OX = 149.3
const PJ_OY = 28.5
// v79 风扇压扁方向：面法线经同款旋转矩阵后的投影压缩方向角（atan2）
// 立面(n=z)→竖直压 θ≈0；顶面(n=y)→斜向压 θ 随 yaw；侧壁(n=x)→介于两者
const squashAngle = function (nx, ny, nz) {
  if (ROT_180) { nx = -nx; nz = -nz }
  const YAW = spinYaw()
  const cosY = Math.cos(YAW), sinY = Math.sin(YAW)
  const cosP = Math.cos(ISO_PITCH), sinP = Math.sin(ISO_PITCH)
  // 法线绕 Y 轴
  const x1 = nx * cosY + nz * sinY
  const z1 = -nx * sinY + nz * cosY
  // 法线绕 X 轴后的屏幕投影 (x1, y2)；压缩方向 = 投影平面内椭圆短轴方向
  const y2 = ny * cosP - z1 * sinP
  return Math.atan2(y2, x1)
}

// ===== 模型配色（每模型固定一种颜色，GPU 行与模型行颜色对应） =====
// 启动脚本出处（内网温控脚本，见 gpu-fan-control 仓库）：
//   GLM-5.3-Flash   <- glm5.3-pp8.sh            (CUDA_DEVICES=0,3,12,13, PP4, port 40053)
//   DSV4-Vision-Exp <- run-dsv4v-vision-pp3.sh  (GPUS=4,5,6,7,8,      PP5, port 40017)
//   Qwen3.8-27B-W4A16 <- 170-qwen38-* 系列      (单卡: 9/10/11, tmux w4a16-38024/25/27)
const MODEL_COLORS = ["#4e9cff", "#34d399", "#f59e0b", "#a78bfa", "#f472b6", "#22d3ee"]

// ===== 每个模型固定唯一配色（模型服务列表与 GPU 行一致：同名同色、不同模型不同色） =====
const MODEL_COLOR_MAP = {
  "DeepSeek-V4-Flash-Exp": "#4e9cff",
  "DeepSeek-V4.1-Flash": "#4e9cff",
  "GLM-5.3-Flash": "#34d399",
  "Qwen3.8-27B-W4A16": "#f59e0b",
  "WeMM-Embedding-9B": "#a78bfa",
  "Meeting-ASR": "#f472b6",
  "MiniMax-H3": "#22d3ee",
  "WeMM-Embedding-9B-CPU": "#facc15",
  "Qwen3-Embedding-0.6B": "#60a5fa",
  "CosyVoice-TTS": "#fb923c",
  "FishSpeech-TTS": "#4ade80",
  "GPT-SoVITS-TTS": "#c084fc",
  "Whisper-ASR": "#2dd4bf",
  "Unlimited-OCR": "#e879f9",
}
const modelColor = function (name) {
  if (MODEL_COLOR_MAP[name]) return MODEL_COLOR_MAP[name]
  let h = 0
  const s = name || ""
  for (let i = 0; i < s.length; i++) h = (h + s.charCodeAt(i) * (i + 7)) % 997
  return MODEL_COLORS[h % MODEL_COLORS.length]
}

// ===== 工具 =====
// v23 修复：num() 在 .map() 回调里被遮蔽（回调参数也叫 num），导致 ReferenceError ——
// 恢复全局唯一定义；调用处一律用 gNum()/clamp() 替代（GPU 行原来 num(g.utilization)*0.7
// 与字符串拼接 bug 同源，见 v21 修复注释）。
const num = (v, d = 0) => (v === null || v === undefined || isNaN(v) ? 0 : Number(v).toFixed(d))
const gNum = (v, d = 0) => (v === null || v === undefined || isNaN(v) ? 0 : Number(v).toFixed(d))
const clamp = (v) => Math.max(0, Math.min(100, Number(v) || 0))
const clamp01 = (v) => Math.max(0, Math.min(100, Number(v) || 0))
const gpuScore = (g) => gNum(g.utilization, 0) * 0.7 + gNum(g.temperature, 0) * 0.3

// v96.9：BMC 传感器配色档位——优先用传感器自带门槛（upper_warning/upper_critical），
// 没门槛的（如 CPU0_DTS）回落到组件统一的 HOT_TEMP。内存条要用这个：DIMM 的 BMC 门槛是
// 85/87°C，若直接套 GPU 用的 75°C，会常年显示红色（当前 82/79°C 实测）。
const sensorTone = function (sensor) {
  if (!sensor || sensor.value === null || sensor.value === undefined) return "#e2e8f0"
  const v = Number(sensor.value)
  if (!isFinite(v)) return "#e2e8f0"
  const warn = (sensor.upper_warning === null || sensor.upper_warning === undefined) ? HOT_TEMP : Number(sensor.upper_warning)
  const crit = (sensor.upper_critical === null || sensor.upper_critical === undefined) ? warn + 10 : Number(sensor.upper_critical)
  if (v >= crit) return "#ef4444"
  if (v >= warn) return "#fbbf24"
  return "#e2e8f0"
}

// v96.9：一行内并排显示 0/1 两路温度（内存条温度、内存供电温度共用），各自按自己的门槛上色；
// 取不到的那一路渲染 "--"（BMC 掉线时两路都是 "--"，不会整行空白）
const pairSpans = function (pair) {
  return (pair || []).map(function (s2, i2) {
    return (
      <span key={"t" + i2} style={{ marginLeft: i2 === 0 ? 0 : 10, color: sensorTone(s2) }}>
        {i2 + " " + (s2 && s2.value !== null && s2.value !== undefined ? gNum(s2.value, 0) + "°C" : "--")}
      </span>
    )
  })
}

// ===== 短名映射（GPU 行标签 & 模型服务行用，避免长模型名溢出） =====
const SHORT_NAMES = {
  "GLM-5.3-Flash": "GLM-5.3",
  "DeepSeek-V4-Flash-Exp": "DSV4-V",
  "DeepSeek-V4.1-Flash": "DSV4.1",
  "Qwen3.8-27B-W4A16": "Qwen3.8",
  "WeMM-Embedding-9B": "EB-9B",
  "MiniMax-H3": "MiniMax-H3",
  // v96.8：Qwen3.8 体量区分——INT8 全量 27B 与 Flash-Next 精简是两个不同模型，短名分开标注
  "Qwen3.8-27B-INT8": "Qwen3.8-INT8",
  "Qwen3.8-Flash-Next": "Qwen3.8-Next",
  // 探针上报的历史/别名一律归一到规范短名
  "DSV4-Flash-0731": "DSV4-V",
  "DSV4-Flash-Exp": "DSV4-V",
  "DeepSeek-V4-Flash-0731": "DSV4-V",
  "qwen3.8-27b": "Qwen3.8",
  // 小模型（GPU/CPU 上跑的嵌入/TTS/ASR 等）
  "Meeting-ASR": "Meet-ASR",
  "WeMM-Embedding-9B-CPU": "EB-CPU",
  "Qwen3-Embedding-0.6B": "Emb-0.6B",
  "CosyVoice-TTS": "CosyTTS",
  "FishSpeech-TTS": "FishTTS",
  "GPT-SoVITS-TTS": "SoVITS",
  "Whisper-ASR": "Whisper",
  "Unlimited-OCR": "OCR",
}

// ===== 渲染 =====
let _lastGoodData = null
let _lastGoodAt = 0
let _lastEnergy = null          // 最后一次成功的 /api/energy 数据
let _lastEnergyAt = 0
let _netMbEma = null            // v96.2 MB/s EMA 平滑状态（跨渲染保持，抹平逐秒毛刺）
let _netMbEmaAt = 0
const STALE_GRACE_MS = 15000   // 断连宽限：最后一次成功数据的保鲜期

export const render = ({ output }) => {
  let data = null
  let energy = null
  const parts = (output || "").split(/\n(?=\{)/)   // 按行首 { 分割：[0]=/api/state, [1]=/api/energy
  try { data = JSON.parse(parts[0] || "null") } catch (e) { data = null }
  try { energy = JSON.parse(parts[1] || "null") } catch (e) { energy = null }
  if (data && data.host) {
    _lastGoodData = data
    _lastGoodAt = Date.now()
    if (energy && typeof energy.cost === "number") { _lastEnergy = energy; _lastEnergyAt = Date.now() }
  } else if (_lastGoodData && Date.now() - _lastGoodAt < STALE_GRACE_MS) {
    // 本次取数失败：沿用最后一次成功数据（保鲜期内不闪断）
    data = _lastGoodData
    if (_lastEnergy && Date.now() - (_lastEnergyAt || 0) < STALE_GRACE_MS) energy = _lastEnergy
    else energy = null
  }

  if (!data || !data.host) {
    return (
      <div style={styles.card}>
        <div style={styles.head}>
          <span style={styles.brand}>vLLM SENTINEL</span>
          <span style={styles.live}><i style={styles.dotOff} />离线</span>
        </div>
        <div style={{ fontSize: 12, color: "#aab8cc", padding: "8px 0" }}>
          无法连接 {SERVER}
          <div style={{ ...styles.kvLabel, marginTop: 4 }}>检查服务器与网络后自动重试（{REFRESH_MS / 1000}s）</div>
        </div>
      </div>
    )
  }

  // 补齐已知槽位：驱动失联的卡（探针漏报）合成占位行，保证行数齐全
  // v96.3 动态化：槽位数跟本机实际显卡数对应（不再 hardcode 14）——15 卡机（GPU0-14）全量显示
  const GPU_COUNT = Math.max(((data.gpu && data.gpu.items) || []).length, 14)
  const knownSlots = Array.from({ length: GPU_COUNT }, function (_, i2) { return i2 })
  const seenIdx = {}
  ;((data.gpu && data.gpu.items) || []).forEach(function (g2) { seenIdx[g2.index] = true })
  const missingSlots = knownSlots.filter(function (i2) { return !seenIdx[i2] }).map(function (i2) {
    return { index: i2, uuid: "missing-" + i2, name: "NVIDIA GPU（驱动失联）", utilization: 0, memory_utilization: 0, memory_total_mb: 0, memory_used_mb: 0, memory_free_mb: 0, memory_percent: 0, temperature: 0, power_w: 0, power_limit_w: 0, fan_percent: 0, fan_pwm: 0, fan_rpm: 0, clock_sm_mhz: 0, clock_memory_mhz: 0, pstate: "P?", processes: [], _missing: true }
  })
  const gpus = ((data.gpu && data.gpu.items) || []).concat(missingSlots).slice().sort((x, y) => gpuScore(y) - gpuScore(x))
  const cpu = (data.host.cpu) || {}
  const bmcTemps = (data.bmc && data.bmc.temperatures) || []
  const cpuSensor = bmcTemps.find(function (t) { return t.name === "CPU0_TEMP" }) || bmcTemps.find(function (t) { return (t.name || "").indexOf("CPU") === 0 })
  const cpuTemp = cpuSensor ? cpuSensor.value : null
  // v96.9：内存相关温度——两组，各取 0/1 两路
  //   ① 内存条温度 DIMMG0_TEMP / DIMMG1_TEMP（技嘉 BMC 命名，对应"内存0/1"）
  //   ② 内存供电 VR 温度 VR_DIMMG0_TEMP / VR_DIMMG1_TEMP（门槛 115/120，比内存条高得多）
  // 换板子命名不同时兜底取前两个同前缀传感器；取不到补 null → 渲染成 "--"（BMC 掉线也走这条）。
  const pickSensorPair = function (names, prefix) {
    const named = names.map(function (n) {
      return bmcTemps.find(function (t) { return t.name === n }) || null
    })
    if (named[0] || named[1]) return named
    const fallback = bmcTemps.filter(function (t) { return (t.name || "").indexOf(prefix) === 0 }).slice(0, 2)
    return [fallback[0] || null, fallback[1] || null]
  }
  const dimmSensors = pickSensorPair(["DIMMG0_TEMP", "DIMMG1_TEMP"], "DIMM")
  const dimmVrSensors = pickSensorPair(["VR_DIMMG0_TEMP", "VR_DIMMG1_TEMP"], "VR_DIMM")
  const perCore = Array.isArray(cpu.per_core) ? cpu.per_core : []
  const mem = (data.host.memory) || {}
  const net = (data.host.network) || {}
  const disk = (data.host.disk) || {}
  // v96.2 MB/s EMA 平滑：α=0.3（新样本权重 30%），突发毛刺抹平、趋势仍实时；
  // 数据新鲜时才更新（沿用旧值的断连场景不更新，避免假平稳）
  if (data.host === _lastGoodData?.host || data === _lastGoodData) {
    if (net.tx_bps !== undefined || net.rx_bps !== undefined) {
      const mbNow = ((Number(net.tx_bps) || 0) + (Number(net.rx_bps) || 0)) / 1048576
      _netMbEma = _netMbEma === null ? mbNow : _netMbEma * 0.7 + mbNow * 0.3
      _netMbEmaAt = Date.now()
    }
  }
  const modelGpuMap = {}
  // 动态归属：后端 /api/state 已按进程实时解析"GPU→模型"（data.gpu.items[*].service 与 gpu_map）。
  // GPU 序号 / 运行模型变化时自动更新；组件只做"服务名 → 规范模型名"归一，不再写死 GPU 清单。
  const canonModel = function (raw) {
    const r = raw || ""
    // v96.8：Qwen3.8 家族区分体量——INT8(27B 全量 INT8) 与 Flash-Next(精简) 是不同模型，
    // 不能再都归一成 Qwen3.8-27B-W4A16（否则 GPU 阵列/模型服务把 GPU7 的 INT8 和 3/5/6 的
    // Flash-Next 混成一个"Qwen3.8"）。精确匹配在通用 qwen3.8 前缀归一派之前。
    if (/^qwen3\.8-27b-int8/i.test(r)) return "Qwen3.8-27B-INT8"
    if (/^qwen3\.8-flash[\s_-]?next/i.test(r)) return "Qwen3.8-Flash-Next"
    if (/^qwen3\.8/i.test(r)) return "Qwen3.8-27B-W4A16"
    // v96.9：DeepSeek V4.1 用裸名（DeepSeek-V4.1-Flash）上报，不带 DSV4 前缀——
    // 旧规则只认 DSV4* / DeepSeek-V4-Flash-Exp，导致新名落到兜底分支，
    // GPU 行只显示 slice(0,7)="DeepSee"、配色也退化成哈希色。V4.1 精确匹配排在前。
    if (/^DeepSeek[-_ ]?V4\.1/i.test(r)) return "DeepSeek-V4.1-Flash"
    if (/^DSV4/i.test(r)) return "DeepSeek-V4-Flash-Exp"
    if (/^DeepSeek[-_ ]?V4/i.test(r)) return "DeepSeek-V4-Flash-Exp"
    if (/^GLM/i.test(r)) return "GLM-5.3-Flash"
    if (/^WeMM/i.test(r)) return "WeMM-Embedding-9B"
    if (/^Unlimited[-_ ]?OCR/i.test(r)) return "Unlimited-OCR"
    if (/^MiniMax/i.test(r)) return "MiniMax-H3"
    return r
  }
  ;((data.gpu && data.gpu.items) || []).forEach(function (g2) {
    const svc = g2.service || ""
    if (!svc) return
    const canon = canonModel(svc)
    let online = true
    const inst = (data.vllm && data.vllm.instances || []).find(function (i2) {
      return i2.name === svc || (i2.models || []).indexOf(svc) >= 0 || (i2.models || []).indexOf(canon) >= 0
    })
    if (inst) online = inst.online
    else online = (g2.memory_used_mb || 0) > 1024
    modelGpuMap[g2.index] = { model: canon, online: online }
  })
  // ===== 模型服务：按模型名聚合 vLLM 实例（Qwen 只显示一行，含实例数/GPU/合计 tok·KV） =====
  // v96.7 修复模型显示重复：gpu_map / small_models 去重只查 byCanon 却从不写入，
  // 同一模型出现在多个来源（如 gpu_map 与 small_models / 多个 gpu_map 条目归一到同一规范名）时
  // 会被重复 push 成多行。现在所有来源共享同一个 byCanon，按规范名合并 GPU 列表，每个模型恒一行。
  const modelRows = (() => {
    const byCanon = {}
    const mergeGpus = function (r, gpus) { (gpus || []).forEach(function (gi) { if (r.gpus.indexOf(gi) < 0) r.gpus.push(gi) }) }
    // 取规范名对应的聚合行（不存在则新建并写入 byCanon → 天然去重）
    const getRow = function (canon) {
      const r = byCanon[canon] || (byCanon[canon] = { name: canon, count: 0, online: 0, tok: 0, kv: 0, kvN: 0, gpus: [], _fromVllm: false, _fromGpu: false, _fromCpu: false })
      return r
    }
    // vLLM 实例（有吞吐/KV 的主模型）
    ;((data.vllm && data.vllm.instances) || []).forEach(function (inst) {
      const raw = inst.models && inst.models[0] ? inst.models[0] : inst.name
      const canon = canonModel(raw)
      const r = getRow(canon)
      r.count += 1
      r._fromVllm = true
      if (inst.online) { r.online += 1; r.tok += Number(inst.generation_tokens_per_second) || 0; r.kv += Number(inst.kv_cache_percent) || 0; r.kvN += 1 }
      mergeGpus(r, inst.gpus)
    })
    // GPU 上跑的非 vLLM 小模型（EB 嵌入等）：从 gpu_map 补充；与 vLLM 同规范名 → 合并 GPU 不新增行
    ;((data.gpu_map) || []).forEach(function (gm) {
      const canon = canonModel(gm.service)
      const r = getRow(canon)
      r.count += 1
      r._fromGpu = true
      r.online = Math.max(r.online, 1)
      mergeGpus(r, gm.gpus)
    })
    // CPU 上跑的小模型（TTS/ASR/embed 等）：从 small_models 补充
    ;((data.small_models) || []).forEach(function (sm) {
      const canon = canonModel(sm.name)
      const r = getRow(canon)
      r.count += 1
      r._fromCpu = true
      r.online = Math.max(r.online, 1)
    })
    // 展示类型：CPU 优先；否则仅当非 vLLM（无吞吐数据）才走显存/GPU-svc 行
    return Object.keys(byCanon).map(function (canon) {
      const r = byCanon[canon]
      r.gpus.sort(function (x, y) { return x - y })
      return {
        name: r.name, count: r.count, online: r.online > 0,
        tok: r.tok, kv: r.kvN ? r.kv / r.kvN : 0, gpus: r.gpus,
        _cpu: !!r._fromCpu,
        _gpuSvc: !r._fromVllm && !!r._fromGpu,   // 仅 GPU 来源（非 vLLM）才用显存行
      }
    }).sort(function (x, y) { return (y.online - x.online) || x.name.localeCompare(y.name) })
  })()
  const modelsOnline = modelRows.filter(function (r) { return r.online }).length
  const modelsTotal = modelRows.length
  const gpuW = Number((data.gpu && data.gpu.power_w) || 0)   // 数字（v21 字符串拼接 bug 同源：num() 返回字符串，"+ OTHER_W" 会拼成 "1669200"）
  const totalW = gpuW + OTHER_W
  // v96 网络流量周期：每月 20 号 → 下月 20 号，1.5TB 配额，达 1TB 红色提示
  // v97.2：累计值优先取后端持久累加（energy.net_cycle_bytes）
  const nc = netCycleTraffic(Date.now(), net, energy)
  const stamp = data.timestamp ? new Date(data.timestamp * 1000).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "--"

  return (
    <div style={styles.card}>
      <div style={styles.head}>
        <span style={styles.brand}>vLLM SENTINEL</span>
        <span style={styles.live}><i style={Date.now() - _lastGoodAt > 4000 ? styles.dotOff : styles.dot} />{data.host.hostname} · {Date.now() - _lastGoodAt > 4000 ? "数据延迟" : "实时"}</span>
      </div>

      {/* 模型服务（按模型名聚合，每个模型一行：实例数 · GPU 集 · 合计 tok·KV） */}
      <div style={styles.section}>模型服务 {modelsOnline}/{modelsTotal} 模型在线</div>
      {modelRows.map((m) => {
        const iColor = modelColor(m.name)
        // v96.8：模型服务行显示模型全名（GPU 阵列行仍显示短名，见 GPU 区 SHORT_NAMES）
        const label = m.name || "?"
        const val = m._cpu
          ? "CPU · 进程在跑"
          : m._gpuSvc
            ? (() => {
                let used = 0
                ;(m.gpus || []).forEach(function (gi) { used += ((data.gpu && data.gpu.items || []).find(function (g2) { return g2.index === gi }) || {}).memory_used_mb || 0 })
                return "GPU " + (m.gpus.join(",") || "-") + " · " + gNum(used / 1024, 1) + "G 显存"
              })()
            : (m.online ? ("GPU " + (m.gpus.join(",") || "-") + " · " + gNum(m.tok, 1) + "t/s · K" + gNum(m.kv, 0) + "%") : "--")
        return (
        <div style={{ ...styles.inst, flexWrap: "nowrap" }} key={m.name}>
          <span style={{ ...styles.instName, ...(iColor ? { color: iColor } : {}), opacity: m.online ? 1 : .45, flexShrink: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={m.name}>
            {label}
          </span>
          <span style={{ ...styles.instStatus, color: m.online ? "#7ee2a8" : "#ef4444" }}>
            <i style={m.online ? styles.instDotOn : styles.instDotOff} />{m.online ? "正常" : "离线"}
          </span>
          <span style={{ ...styles.instVal, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 195 }} title={val}>{val}</span>
        </div>
        )
      })}

      {/* GPU 阵列（全量 14 张，负载×0.7+温度×0.3 降序） */}
      <div style={styles.section}>GPU × {gpus.length} · 总 {gpuW}W + {OTHER_W}W</div>
      {gpus.map((g) => {
        const mInfo = modelGpuMap[g.index]
        const mColor = mInfo && mInfo.model ? modelColor(mInfo.model) : null
        const load = clamp01(g.utilization)
        const isHot = gNum(g.temperature, 0) >= HOT_TEMP
        const isIdle = !g._missing && !(mInfo && mInfo.model)          // 空闲卡：没有模型归属
        return (
          <div style={styles.gpuRow} key={g.uuid || g.index}>
            <span style={{ ...styles.gpuIdx, width: 92, ...(mColor ? { color: mColor } : isIdle ? { color: "#64748b" } : {}) }}>
              {"GPU " + g.index}{mInfo && mInfo.model ? "·" + (SHORT_NAMES[mInfo.model] || mInfo.model.slice(0, 7)) : isIdle ? "·空闲" : ""}
            </span>
            <span style={styles.gpuMem}>{gNum(g.memory_used_mb / 1024, 1)}G</span>
            <span style={styles.gpuBarWrap}>
              <i style={{ ...(isHot ? styles.gpuBarHot : styles.gpuBar), ...(mColor ? { backgroundColor: mColor, backgroundImage: "none" } : {}), ...(isIdle ? { backgroundColor: "rgba(100,116,139,.35)", backgroundImage: "none" } : {}), width: load + "%" }} />
            </span>
            <span style={{ ...styles.gpuMeta, color: g._missing ? "#ef4444" : (gNum(g.temperature, 0) >= HOT_TEMP ? "#ef4444" : "#94a3b8") }}>{g._missing ? "驱动失联" : gNum(g.temperature, 0) + "°C · " + gNum(g.fan_rpm, 0) + " RPM"}</span>
          </div>
        )
      })}

      {/* CPU 综合汇总 */}
      <div style={styles.section}>CPU 综合</div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>总使用率</span>
        <span style={styles.kvVal}>{num(cpu.usage, 1)}%</span>
      </div>
      <div style={styles.barRow}>
        <span style={styles.barWrap}>
          <i style={{ ...styles.barFill, width: clamp01(cpu.usage) + "%" }} />
        </span>
      </div>
      {/* v96.9：CPU 条下面紧跟内存条 + 内存两组温度（内存条 DIMMG0/1、内存供电 VR_DIMM0/1）。
          原来"主机内存"那一条在额度条之后，这里上移并合并，避免同一数据出现两根条。
          温度按传感器自带门槛上色（内存条 85/87、供电 115/120）：正常灰/警告黄/危险红 */}
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>内存使用率</span>
        <span style={styles.kvVal}>{num(mem.percent, 1)}%</span>
      </div>
      <div style={styles.barRow}>
        <span style={styles.barWrap}>
          <i style={{ ...styles.barFill, width: clamp01(mem.percent) + "%" }} />
        </span>
      </div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>内存温度</span>
        <span style={styles.kvVal}>{pairSpans(dimmSensors)}</span>
      </div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>内存供电温度</span>
        <span style={styles.kvVal}>{pairSpans(dimmVrSensors)}</span>
      </div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>最高单核</span>
        <span style={styles.kvVal}>{num(Math.max.apply(null, perCore.concat([0])), 1)}%</span>
      </div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>CPU 温度</span>
        <span style={{ ...styles.kvVal, color: (cpuTemp !== null && cpuTemp >= HOT_TEMP) ? "#ef4444" : "#e2e8f0" }}>{cpuTemp !== null ? num(cpuTemp, 0) + "°C" : "--"}</span>
      </div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>线程数 / 频率</span>
        <span style={styles.kvVal}>{perCore.length}线程 · {num(cpu.frequency_mhz, 0)}MHz</span>
      </div>

      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>整机功耗（GPU实时+其他固定）</span>
        <span style={styles.kvValGpu}>{num(totalW, 1)} W</span>
      </div>
      {/* v62：电费预算两条进度条。v97.2（2026-09-29 用户："本月额度是否按自然月加总上去了，
          本年额度也要实时加总，不要只有7天加上"）：两条都改用**后端真实累计值**——
          cost_month = 自然月（本地时区）已累计电费、cost_year = 自然年累计；
          数据来自永不被 31 天裁剪的 daily 汇总表，故年度值会跨月持续增长，不再是"只有最近一个月"。
          预估（cost_month_est）仍由后端提供，放在进度条 title 里备查，不再驱动进度。 */}
      <div style={styles.barRow}>
        <span style={styles.kvLabel}>本月额度</span>
        <span style={styles.barWrap} title={energy && typeof energy.cost_month === "number" ? ("本月已累计 " + num(energy.cost_month, 2) + " 元" + (typeof energy.cost_month_est === "number" ? "，按当前速率预估月底 " + num(energy.cost_month_est, 2) + " 元" : "")) : ""}>
          <i style={{ ...styles.barFill, width: clamp01(energy && typeof energy.cost_month === "number" ? energy.cost_month / MONTH_BUDGET * 100 : 0) + "%", ...(energy && typeof energy.cost_month === "number" && energy.cost_month > MONTH_BUDGET * 0.9 ? { background: "linear-gradient(90deg,#f59e0b,#ef4444)" } : {}) }} />
        </span>
      </div>
      <div style={styles.barRow}>
        <span style={styles.kvLabel}>本年额度</span>
        <span style={styles.barWrap} title={energy && typeof energy.cost_year === "number" ? ("本年已累计 " + num(energy.cost_year, 2) + " 元（自然年累计，跨月持续）") : ""}>
          <i style={{ ...styles.barFill, width: clamp01(energy && typeof energy.cost_year === "number" ? energy.cost_year / YEAR_BUDGET * 100 : 0) + "%", ...(energy && typeof energy.cost_year === "number" && energy.cost_year > YEAR_BUDGET * 0.9 ? { background: "linear-gradient(90deg,#f59e0b,#ef4444)" } : {}) }} />
        </span>
      </div>
      {/* v96.9：原"主机内存"条已上移到 CPU 综合区（CPU 条下面），这里不再重复显示 */}
      {/* v96 网络流量周期（每月 20 号 → 下月 20 号，总配额 1.5TB，达 1TB 红色提示） */}
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>网络流量（20日起）</span>
        <span
          style={{ ...styles.kvVal, ...(nc.warn ? { color: "#ef4444" } : {}) }}
          title={nc.source === "api"
            ? ("后端持久累计（WAN 出口 " + ((net && net.iface) || "?") + "），含手工基准 " + num(nc.baseGb, 0) + " GB；周期 " + nc.days + " 天")
            : "旧后端兜底：瞬时速率 × 周期已过时长（会跳动）"}
        >{gNum(nc.tb, 2)} / {NET_TOTAL_TB} TB{nc.baseGb > 0 ? " *" : ""}</span>
      </div>
      <div style={styles.barRow}>
        <span style={styles.barWrap}>
          <i style={{ ...styles.barFill, width: clamp01(nc.tb / NET_TOTAL_TB * 100) + "%", ...(nc.warn ? { background: "linear-gradient(90deg,#f59e0b,#ef4444)" } : {}) }} />
        </span>
      </div>
      <div style={styles.kvRow}>
        <span style={styles.kvLabel}>磁盘 IO / 网络</span>
        <span
          style={styles.kvVal}
          title={(net && net.iface ? "网络速率=WAN 出口 " + net.iface + "（不含内网互传/容器网桥）" : "")}
        >{num(disk.write_bps/1048576, 1)}/{num(_netMbEma !== null && Date.now() - _netMbEmaAt < STALE_GRACE_MS ? _netMbEma : (net && net.tx_bps ? net.tx_bps/1048576 : 0), 1)} MB/s</span>
      </div>

      {/* 3D 双塔机箱旋转图（v26：风扇重映射定稿版；构建期 3D 投影 + 摆动动画） */}
      {(() => {
        // ---- 实时数据来源 ----
        const gpuItems = (data.gpu && data.gpu.items) || []
        const gpuByIndex = {}
        gpuItems.forEach(function (g2) { gpuByIndex[g2.index] = g2 })
        // v96.3 动态化：9733 专属扇 RPM 取 GPU1..GPU_COUNT-1（GPU0=3090Ti 自控豁免）
        const gpuRpms13 = Array.from({ length: Math.max(1, GPU_COUNT - 1) }, function (_, i2) { return gNum((gpuByIndex[i2 + 1] || {}).fan_rpm, 0) })
        const bmcFans = (data.bmc && data.bmc.fans) || []
        const fanByName = {}
        bmcFans.forEach(function (f2) { fanByName[f2.name] = gNum(f2.value, 0) })
        // v96.6 Storm3 机箱扇实时档位（ch1/ch2=G2 后排双扇、ch3=G1 前排，gpu-fan-control 温控驱动）
        // ——此前漏显示：后 G2 用主板 IPMI SYS_FAN6/7、前 G1 硬编码 3450
        const stormFans = (data.gpu && data.gpu.storm_fans) || {}
        // v26 风扇重映射（2026-09-14 定稿，/etc/gpu-mapping.conf 13×9733 ↔ 13×CMP 全完成）：
        // GPU1-13 各配一颗专属 9733（fan_rpm = PWM×3450 反算，直读 gpu.items）；
        // GPU0=3090Ti 自控不在 1000D 上（豁免）。
        // 机箱扇（hwmon tach 实测，经 bmc.fans 上报）：
        //   G2 排风 = SYS_FAN6 + SYS_FAN7（1000D 后部两路 G2，实测 450-600）
        //   CPU = CPU0_FAN（实测 2700-3450）；FCH = FCH_FAN（实测 1500-2700）
        //   12NF（顶 3 + 前面板最下 1）后端无独立读数，按温控曲线同转速近似
        // v96.6: 后 G2 双扇 = Storm3 ch1/ch2（实时温控档位），fallback 主板 IPMI SYS_FAN6/7
        const rearRpmA = stormFans.g2 || fanByName.SYS_FAN6 || 0
        const rearRpmB = stormFans.g2b || fanByName.SYS_FAN7 || 0
        const rearRpm = Math.max(rearRpmA, rearRpmB)  // G2 排风代表值（取两路较大）
        // v96.6: 前 G1 排风 = Storm3 ch3（实时温控档位），fallback 硬编码 3450
        const frontG1Rpm = stormFans.g1 || 3450
        const cpuFanRpm = fanByName.CPU0_FAN || 0     // CPU 风扇
        const fchRpm = fanByName.FCH_FAN || 0         // FCH 风扇

        // ---- 3D 投影（v33：放大 3D 单机箱，yaw=-15° pitch=14° SC=0.82） ----
        // 用户定稿（2026-09-22）：放大形成 3D 机箱——从右前方看，正面大面+右外壁窄条。
        // v68：SC 0.951→0.85 机箱再缩小点（留边好看）
        const SC = 0.85, CH = 170
        // v96.9：卡堆间距自适应——卡条 y=15+i×10、高 6，卡数超过 15 时最后一条会越过
        // 机箱底（16 卡：15+15×10+6=171 > 170，GPU15 卡条/风机出底）。按可用高度反推 pitch：
        //   15 卡 → (170-8-6-15)/14 = 10.07 → 截到 10（与 v89/v90 定稿完全一致，外观不变）
        //   16 卡 → 141/15 = 9.4 → 堆底 162，仍留 8px 底隙
        // 风扇半径按同比例缩放（保持 v88 定稿"扇不互相碰"的间距比）。
        const STACK_Y0 = 15, STACK_GAP = 8, STACK_H = 6
        const STACK_PITCH = Math.min(10, (CH - STACK_GAP - STACK_H - STACK_Y0) / Math.max(1, GPU_COUNT - 1))
        const STACK_FAN_SCALE = STACK_PITCH / 10
        // 投影范围居中（构建期算好）
        const pj = function (x, y, z) { const p = isoProject(x, y, z); return [p[0] * SC + PJ_OX, p[1] * SC + PJ_OY] }
        // 3D 几何：正面 z=55 + 右外壁 x=155（可见）+ 顶面 y=0（可见）+ 后面板 z=-55（v45 新增）
        // 可见面：F + SE + T（从右前方看）；左外壁 x=-155 z1=-40 不可见不画
        // 后面板（z=-55）从右前方看大部分被正面遮住，只露出右缘一条（G2 竖列在此）
        const BOX = {
          F: [pj(-155, 0, 55), pj(155, 0, 55), pj(155, CH, 55), pj(-155, CH, 55)],
          SE: [pj(155, 0, -55), pj(155, 0, 55), pj(155, CH, 55), pj(155, CH, -55)],
          T: [pj(-155, 0, 55), pj(155, 0, 55), pj(155, 0, -55), pj(-155, 0, -55)],
          REAR: [pj(-155, 0, -55), pj(155, 0, -55), pj(155, CH, -55), pj(-155, CH, -55)],
          BASE_T: [pj(-160, CH + 2, 60), pj(160, CH + 2, 60), pj(160, CH + 2, -60), pj(-160, CH + 2, -60)],
          BASE_SE: [pj(160, CH + 2, 60), pj(160, CH + 2, -60), pj(160, CH + 8, -60), pj(160, CH + 8, 60)],
        }
        const poly = function (pts4) { return pts4.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1) }).join(" ") }

        // ---- 风扇（3D 局部坐标 → 投影圆心） ----
        // kind: "in"=进风（绿）/ "out"=排风（琥珀）/ "gpu"=GPU 专属 9733（按卡配色）
        // v58 全面重排（2026-09-15）：修掉 v55/v57 的位置错乱——每个扇落在正确的面上且互不打架
        //   · 前面板（右外壁 x=155 窄条，v42 方位约定"右外壁=前面"）：3×G1 竖列 + 最下 12NF
        //     全部画成壁面圆（z=-10 壁中央），从右前方看贴在壁面上
        //   · 顶部（y=0 顶面后沿）：3×12NF 排风（保持）
        //   · 后面（后面板 z=-55 右缘露出条，x=130）：4×G2 竖列 y 下段（真实 1000D 后部排风）
        //   · CPU/FCH：图形删除（属左塔系统仓，单箱体显卡仓模型里没有位置，转速进图例）
        //   · 左壁 2×G2 删除（左外壁不可见，画了也是空气）
        const FANS3D = [
          // 顶部 3×12NF（y=0 顶面后沿，均匀间距 90）
          // v85：dir="top" → scale(1,0.30) 躺平扁椭圆（顶面圆真实压扁比 sin(10°)=0.174，
          // 0.30 兼顾可读性；v84 rotate(90°)+sq0.92 椭圆几乎正圆 → 在扁顶面上「立起来」违和）
          // v79：nx/ny/nz 面法线（压扁方向用）+ wx/wy/wz 世界坐标（深度排序用）
          { c: pj(-90, 0, -25), nx: 0, ny: 1, nz: 0, wx: -90, wy: 0, wz: -25, r: 9.5, rpm: 3450, kind: "out", dir: "top" },
          { c: pj(0, 0, -25), nx: 0, ny: 1, nz: 0, wx: 0, wy: 0, wz: -25, r: 9.5, rpm: 3450, kind: "out", dir: "top" },
          { c: pj(90, 0, -25), nx: 0, ny: 1, nz: 0, wx: 90, wy: 0, wz: -25, r: 9.5, rpm: 3450, kind: "out", dir: "top" },
          // 前面板 6×G1 进风（右外壁 x=155 壁面圆，v86 双列 3+3：
          // 前列 z=25 + 后列 z=-30，v87 各列 y=30/62/94（间距 32 跟后面一致，
          // 拉开不挤——v86 y=40/60/80 间距 20 两排在屏幕上挤到一起）
          // v85：dir="wall" → scale(0.62,1) 竖椭圆不旋转（壁面圆投影 ry/rx≈1.6 高>宽，
          // 横向压跟壁面透视一致；v84 rotate(θ≈-7.7°) 猫扇整体倾斜，用户不要）
          { c: pj(155, 30, 25), nx: -1, ny: 0, nz: 0, wx: 155, wy: 30, wz: 25, r: 10, rpm: frontG1Rpm, kind: "in", dir: "wall" },
          { c: pj(155, 62, 25), nx: -1, ny: 0, nz: 0, wx: 155, wy: 62, wz: 25, r: 10, rpm: frontG1Rpm, kind: "in", dir: "wall" },
          { c: pj(155, 94, 25), nx: -1, ny: 0, nz: 0, wx: 155, wy: 94, wz: 25, r: 10, rpm: frontG1Rpm, kind: "in", dir: "wall" },
          { c: pj(155, 30, -30), nx: -1, ny: 0, nz: 0, wx: 155, wy: 30, wz: -30, r: 10, rpm: frontG1Rpm, kind: "in", dir: "wall" },
          { c: pj(155, 62, -30), nx: -1, ny: 0, nz: 0, wx: 155, wy: 62, wz: -30, r: 10, rpm: frontG1Rpm, kind: "in", dir: "wall" },
          { c: pj(155, 94, -30), nx: -1, ny: 0, nz: 0, wx: 155, wy: 94, wz: -30, r: 10, rpm: frontG1Rpm, kind: "in", dir: "wall" },
          // 最下 12NF 进风（右外壁 x=155 壁面圆 z=-10，v85 靠最下 y=150；v84 y=125 夹在 G1 之间）
          { c: pj(155, 150, -10), nx: -1, ny: 0, nz: 0, wx: 155, wy: 150, wz: -10, r: 6.5, rpm: 3450, kind: "in", dir: "wall" },
          // 后面 4×G2 排风（v89：z=22→28——卡条 z=45→50 前移后 -50° 极端角度
          // 扇左缘会压卡条右缘 2.6px，z=28 全清（余 1.3px）；v87 深度 10 保持
          // 完全可见=跟前扇一样大；
          // 均匀单列 y=15/47/79/111 间距 32 保持；dir="wall" 竖椭圆不旋转；
          // 位置紧邻「后」标签（屏幕右）＝后面 ✓；
          // 气流方向可视化：9733(前) → 卡条 → G2(排出)）
          { c: pj(-155, 15, 28), nx: -1, ny: 0, nz: 0, wx: -155, wy: 15, wz: 28, r: 10, rpm: rearRpm, kind: "out", stop: rearRpm === 0, dir: "wall" },
          { c: pj(-155, 47, 28), nx: -1, ny: 0, nz: 0, wx: -155, wy: 47, wz: 28, r: 10, rpm: rearRpm, kind: "out", stop: rearRpm === 0, dir: "wall" },
          { c: pj(-155, 79, 28), nx: -1, ny: 0, nz: 0, wx: -155, wy: 79, wz: 28, r: 10, rpm: rearRpm, kind: "out", stop: rearRpm === 0, dir: "wall" },
          { c: pj(-155, 111, 28), nx: -1, ny: 0, nz: 0, wx: -155, wy: 111, wz: 28, r: 10, rpm: rearRpm, kind: "out", stop: rearRpm === 0, dir: "wall" },
          // 后面最下排风（v88：也是 G2——r=6.5→10，后面 5×G2 均匀 y=15/47/79/111/150
          // 间距 32；v89 z=28 y=150 保持）
          { c: pj(-155, 150, 28), nx: -1, ny: 0, nz: 0, wx: -155, wy: 150, wz: 28, r: 10, rpm: rearRpm, kind: "out", stop: rearRpm === 0, dir: "wall" },
        ]
        // 13×9733（GPU 专属扇，2026-09-14 定稿映射）：每卡一颗
        // v41：GPU 扇移到条右缘外（x_old=100），卡号在扇正右方同行对应
        // v48：卡条靠前 z=45 + 间隔 y=12+i*12（顶部到底部），扇跟随
        // v57：9733 挪到「前面」——真实 1000D 里 9733 从前面板吹向卡面，应在卡条与
        // 正面板之间（x=100, z=52，卡条 z=45 与正面 z=55 的中前位），不再是卡条后方延伸线
        // v69：风扇停转标红——GPU1-13 9733 专属扇：卡在线且 fan_rpm=0 → 停转红；
        //   GPU0=3090Ti 自带扇有 0dB 停转模式，不判（豁免）；G2(后) 由 rearRpm=0 判停
        // v96.3 动态化：扇数跟本机实际显卡数对应（GPU0-GPU_COUNT-1，每卡一颗）
        const GPU_FANS13 = Array.from({ length: GPU_COUNT }, function (_, i2) {
          // v90：y=18+i*10 跟随卡条新间距/起点（slab_y+3）；x=130→132（卡条右缘
          // 120→106 后扇离卡条更远更清晰）；z=53（卡条 50 前）；r=4.4（涡轮扇）
          const y = STACK_Y0 + 3 + i2 * STACK_PITCH
          const gpc = gpuByIndex[i2] || {}
          const rpm = gNum(gpc.fan_rpm, 0)
          // 停转/失联：i2>=1（9733 专属）在线但无转速=停转；卡失联(驱动异常)也红（免 GPU0 在线 0dB 停转）
          // v79：扇跟随卡条居中 x=130（右缘 120+10）；v79 加 nx/ny/nz（近立面法线）+ wx/wy/wz
          // v88：r=4.6→4.2 sq=0.9→0.85——间距缩小后扇微缩不互相碰（屏幕高 7.14 vs 间距 7.53）
          const stopped = (i2 >= 1 && !gpc._missing && rpm === 0) || !!gpc._missing
          return { c: pj(132, y, 53), nx: 0, ny: 0, nz: 1, wx: 132, wy: y, wz: 53, r: 4.4 * STACK_FAN_SCALE, sq: 0.85, rpm: rpm, kind: "gpu", idx: i2, stop: stopped, miss: !!gpc._missing }
        })
        const fanKindColor = { "in": "#7ee2a8", "out": "#fbbf24", "sys": "#9fc4ff" }

        // ---- 13×170HX 竖装横条（显卡仓内 z=45 靠前，x∈[-145,90] 靠左贴左外壁） ----
        // v34 逼真：条高 4.5→6（170HX 卡厚），银灰金属质感（矿卡外观）
        // v36：卡条 x 范围靠左（x∈[-145,90]，贴左外壁间隙 10）
        // v38：卡条往前提 z=20→35（贴近正面）
        // v48：卡条靠前 z=35→45（与正面间隙 10）+ 间隔 y=12+i*12（13 条从顶部
        // y=12 排到底部 y=162，"刚好顶部和底部"）
        // v53：卡条 13→14 条（GPU0-13 全量，位置排序按 GPU0-13），y=10+i*11；
        // 显示显存占用+功率（v66：负载段改用显存百分比 memory_percent；颜色跟 GPU 详细信息一致：模型色/空闲灰/热点橙）
        // v79：卡条居中 x∈[-115,120]（中心 2.5，微偏右，左右空隙 40/35 近对称）
        // v89：SLAB_Z 45→50（用户：显卡条前面锁进一部分，与正面间隙 10→5）+
        //      间距 9→11（用户：间隔距离加大，让风扇和序号清晰一点）+
        //      起点 y=10→13（用户：显卡条可以离底部更近一点，堆底 162 离机箱底 170 间隙 8）
        // v90：卡条宽 -115..120→-110..106（用户：显卡条再缩短点）+ 间距 11→10
        // （再缩一点）+ 起点 y=13→15——风扇（x=132）与序号（offset 8）明显拉开距离
        const SLAB_H = STACK_H, SLAB_Z = 50
        const SLAB_L = -110, SLAB_R = 106
        // v96.3 动态化：卡条数跟本机实际显卡数对应（GPU0-GPU_COUNT-1 全量）
        const slabs13 = Array.from({ length: GPU_COUNT }, function (_, i2) {
          const g2 = gpuByIndex[i2] || {}
          const mInfo = modelGpuMap[i2]
          const y = STACK_Y0 + i2 * STACK_PITCH
          return {
            idx: i2, y: y,
            tl: pj(SLAB_L, y, SLAB_Z), tr: pj(SLAB_R, y, SLAB_Z),
            bl: pj(SLAB_L, y + SLAB_H, SLAB_Z), br: pj(SLAB_R, y + SLAB_H, SLAB_Z),
            util: gNum(g2.utilization, 0), mem: gNum(g2.memory_percent, 0), pw: gNum(g2.power_w, 0), temp: gNum(g2.temperature, 0),
            hot: gNum(g2.temperature, 0) >= HOT_TEMP,
            idle: !g2._missing && !(mInfo && mInfo.model),
            missing: !!g2._missing,
            mColor: mInfo && mInfo.model ? modelColor(mInfo.model) : null,
          }
        })
        // 3D 平行四边形内的分段：温度半（左半 x∈[-145,-28]）+ 功耗半（右半 x∈[-28,90]）
        const slabSeg = function (s2, fromX, toX) {
          const a = pj(fromX, s2.y, SLAB_Z), b = pj(toX, s2.y, SLAB_Z), c = pj(toX, s2.y + SLAB_H, SLAB_Z), d = pj(fromX, s2.y + SLAB_H, SLAB_Z)
          return [a, b, c, d]
        }

        // ---- 实时转速芯片（纯 2D 绝对定位） ----
        const chip = (left, top, text, ok) => {
          return <span key={"c" + left + "-" + top} style={{ ...styles.chip, left: left, top: top, ...(ok ? styles.chipOk : {}) }}>{text}</span>
        }

        // ---- 猫头鹰样式风扇（v65：Noctua NF-A12x25 造型——外框 + 4 角螺孔 + 7 叶扇弧） ----
        // f: {c:[sx,sy], r} ；sw: 描边粗细。扇叶用 7 段圆弧 path（猫头鹰经典水滴形叶）
        // v66 修复：blades 路径原先对字符串再调 .toFixed 崩溃（x0.toFixed is not a function）导致整widget空白
        const ptOn = (CX, CY, rad, ang, ell) => [CX + rad * Math.cos(ang), CY + rad * Math.sin(ang) * (ell || 1)]
        // v69 停转标红：f.stop=true 时外框/中心全红 + 中心感叹号
        // v79 压扁方向正解：noctuaFan 画正圆，压扁交给外层 rotate(θ)+scale(1,sq)——
        //   θ=squashAngle(面法线投影压缩方向)，椭圆短轴指向真实压缩方向，任何角度都是猫扇
        const noctuaFan = (f, key, sw) => {
          const CX = Number(f.c[0]), CY = Number(f.c[1])
          const r = f.r
          const sq = f.sq || 0.92
          const stopped = !!f.stop
          const strokeCol = stopped ? "#ef4444" : (f.rpm > 0 ? "#9aa8bc" : "#5a6470")
          const hub = r * 0.34
          // 7 叶：从轮毂向外弯的水滴弧（v82 弯曲加大 13→18/26→32，水滴形更明显；
          // 正圆，返回数字，最后统一 toFixed 一次）
          const blades = Array.from({ length: 7 }, function (_, bi) {
            const base = bi * 360 / 7
            const p0 = ptOn(CX, CY, hub, base * Math.PI / 180, 1)
            const pm = ptOn(CX, CY, r * 0.62, (base + 18) * Math.PI / 180, 1)
            const p1 = ptOn(CX, CY, r * 0.86, (base + 32) * Math.PI / 180, 1)
            return "M" + p0[0].toFixed(1) + " " + p0[1].toFixed(1) + " Q" + pm[0].toFixed(1) + " " + pm[1].toFixed(1) + " " + p1[0].toFixed(1) + " " + p1[1].toFixed(1)
          }).join(" ")
          const screws = [[-0.72, -0.72], [0.72, -0.72], [-0.72, 0.72], [0.72, 0.72]].map(function (sd, si) {
            return <circle key={key + "-scr" + si} cx={(CX + sd[0] * r).toFixed(1)} cy={(CY + sd[1] * r).toFixed(1)} r={Math.max(0.5, r * 0.09).toFixed(1)} fill="#04080e" stroke={stopped ? "#ef4444" : "#5a6470"} strokeWidth="0.4" />
          })
          // 压扁方向角：f.nx/ny/nz（面法线）→ θ；无法线或前面板法线（0,0,1）→ θ=0（v83 统一前面板角度）
          // transform 围绕风扇中心 (CX,CY)：translate(CX,CY) rotate scale translate(-CX,-CY)
          // （SVG transform 列表从右到左应用；scale 无围绕点语法，必须手动 translate 回原点）
          // v85 三向正解（用户反馈：顶扇立起来/前面倾斜了）：
          //   v84 顶扇 rotate(90°)+scale(1,0.92) → 椭圆 0.92 几乎正圆，在很扁的顶面上看着「立起来」；
          //   v84 壁面 rotate(θ≈-7.7°) → 猫扇整体倾斜，用户不要倾斜。
          //   正解：顶面圆真实压扁比 = sin(pitch)=0.174，壁面圆投影是「高>宽」竖椭圆（ry/rx≈1.6）→
          //   壁面扇该横向压（scale(rx,1)）而不是竖向压。
          //   实现为 f.dir 面朝向标记："top"(顶面躺平) / "wall"(壁面竖椭圆) / 其它(立面正圆)
          const isFrontNormal = (f.nx === 0 && f.ny === 0 && f.nz === 1) || typeof f.nx !== "number"
          const dir = f.dir || (isFrontNormal ? "front" : "wall")
          let tfm
          if (dir === "top") {
            // 顶面：躺平扁椭圆（sq=0.30，介于真实 0.174 与可读性之间），不旋转
            tfm = "translate(" + CX.toFixed(1) + " " + CY.toFixed(1) + ") scale(1 0.30) translate(" + (-CX).toFixed(1) + " " + (-CY).toFixed(1) + ")"
          } else if (dir === "wall") {
            // 壁面：竖椭圆（横向压 0.62，ry/rx≈1.6 跟壁面透视一致），不旋转（用户不要倾斜）
            tfm = "translate(" + CX.toFixed(1) + " " + CY.toFixed(1) + ") scale(0.62 1) translate(" + (-CX).toFixed(1) + " " + (-CY).toFixed(1) + ")"
          } else {
            // 立面（9733/前面板）：正圆微压，不旋转
            tfm = "translate(" + CX.toFixed(1) + " " + CY.toFixed(1) + ") scale(1 " + sq + ") translate(" + (-CX).toFixed(1) + " " + (-CY).toFixed(1) + ")"
          }
          return (
            <g key={key} transform={tfm}>
              {/* 停转红晕（警示光晕） */}
              {stopped ? <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={(r + 1.6).toFixed(1)} fill="none" stroke="#ef4444" strokeWidth="1.1" opacity=".9" /> : null}
              {/* 外框（正圆外圈 + 内框槽；压扁由外层 transform） */}
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={r} fill={stopped ? "#2a0f14" : "#0a0f16"} stroke={strokeCol} strokeWidth={sw} />
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={(r * 0.88).toFixed(1)} fill="none" stroke={stopped ? "#ef4444" : "#3a4450"} strokeWidth="0.5" opacity=".8" />
              {/* 7 叶扇弧（v82 加强辨识：加粗 + 亮灰对比 + 每叶高光点，猫扇特征清晰） */}
              <path d={blades} fill="none" stroke={stopped ? "#ef4444" : "#8a96a2"} strokeWidth={Math.max(1.2, r * 0.22).toFixed(1)} strokeLinecap="round" opacity={stopped ? ".95" : ".9"} />
              <path d={blades} fill="none" stroke={stopped ? "#ef4444" : "#c4d0de"} strokeWidth={Math.max(0.5, r * 0.08).toFixed(1)} strokeLinecap="round" opacity=".55" />
              {/* 轮毂（中心圆 + 高光环，猫扇标志） */}
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={hub.toFixed(1)} fill={stopped ? "#3a0f18" : "#1a2230"} stroke={stopped ? "#ef4444" : "#5a6470"} strokeWidth="0.6" />
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={(hub * 0.62).toFixed(1)} fill="none" stroke={stopped ? "#ef4444" : "#7a8696"} strokeWidth="0.5" opacity=".8" />
              {/* 停转感叹号 */}
              {stopped ? <text x={CX.toFixed(1)} y={(CY + 1.5).toFixed(1)} textAnchor="middle" fontSize={Math.max(6, r * 0.7).toFixed(1)} fontWeight="900" fill="#ff6b6b" stroke="#000" strokeWidth="0.3" paintOrder="stroke" fontFamily="Arial,Helvetica,sans-serif">!</text> : null}
              {screws}
            </g>
          )
        }

        // 涡轮扇（v90：显卡扇改涡轮/鼓风式——用户：显卡风扇是涡轮扇，不是普通猫扇。
        // 特征：大圆形轮毂 + 轮毂外一圈密排放射细叶片 + 双层同心圆外框；
        // 与猫扇(noctuaFan)完全不同，无 owl 眼睛/高光；停转红晕+感叹号保留）
        const turboFan = (f, key) => {
          const CX = Number(f.c[0]), CY = Number(f.c[1])
          const r = f.r
          const sq = f.sq || 0.85
          const stopped = !!f.stop
          const strokeCol = stopped ? "#ef4444" : (f.rpm > 0 ? "#a8b4c8" : "#5a6470")
          const hub = r * 0.32
          const inner = r * 0.48
          // 涡轮叶轮：轮毂外密排 9 条放射细叶片（轮毂缘→空心缘，涡轮扇辨识度）
          const bladePath = Array.from({ length: 9 }, function (_, bi) {
            const a0 = (bi * 360 / 9 + 3) * Math.PI / 180
            const a1 = (bi * 360 / 9 + 13) * Math.PI / 180
            const b0 = ptOn(CX, CY, hub, a0, 1)
            const b1 = ptOn(CX, CY, inner, a1, 1)
            const b2 = ptOn(CX, CY, inner, a0 + (a1 - a0) * 0.45, 1)
            return "M" + b0[0].toFixed(1) + " " + b0[1].toFixed(1) + " L" + b2[0].toFixed(1) + " " + b2[1].toFixed(1) + " L" + b1[0].toFixed(1) + " " + b1[1].toFixed(1)
          }).join(" ")
          const tfm = "translate(" + CX.toFixed(1) + " " + CY.toFixed(1) + ") scale(1 " + sq + ") translate(" + (-CX).toFixed(1) + " " + (-CY).toFixed(1) + ")"
          return (
            <g key={key} transform={tfm}>
              {stopped ? <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={(r + 1.6).toFixed(1)} fill="none" stroke="#ef4444" strokeWidth="1.1" opacity=".9" /> : null}
              {/* 外框双层同心圆（涡轮扇鼓风壳） */}
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={r} fill={stopped ? "#2a0f14" : "#0a0f16"} stroke={strokeCol} strokeWidth="0.7" />
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={(r * 0.86).toFixed(1)} fill="none" stroke={stopped ? "#ef4444" : "#5a6470"} strokeWidth="0.4" opacity=".7" />
              {/* 涡轮密排放射叶片 */}
              <path d={bladePath} fill="none" stroke={stopped ? "#ef4444" : "#8a96aa"} strokeWidth="1.0" strokeLinecap="round" opacity=".85" />
              {/* 大圆形轮毂（涡轮鼓风电机） */}
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={hub.toFixed(1)} fill={stopped ? "#3a0f18" : "#1a2230"} stroke={stopped ? "#ef4444" : "#5a6470"} strokeWidth="0.5" />
              <circle cx={CX.toFixed(1)} cy={CY.toFixed(1)} r={(hub * 0.5).toFixed(1)} fill="none" stroke={stopped ? "#ef4444" : "#8a96aa"} strokeWidth="0.3" opacity=".6" />
              {stopped ? <text x={CX.toFixed(1)} y={(CY + 1.5).toFixed(1)} textAnchor="middle" fontSize="6" fontWeight="900" fill="#ff6b6b" stroke="#000" strokeWidth="0.3" paintOrder="stroke" fontFamily="Arial,Helvetica,sans-serif">!</text> : null}
            </g>
          )
        }

        return (
          <div>
            <style>{FAN_KEYFRAMES}</style>
            <div style={styles.fanScene}>
              <div style={{ position: "relative", width: 340, height: 300, margin: "0 auto", transformOrigin: "50% 100%" }}>
                {/* v25：两座独立长方体并排（各自 正面+左外壁+顶面+底座），中间真空隙 */}
                <svg style={styles.sceneSvg} viewBox="0 0 340 300" xmlns="http://www.w3.org/2000/svg">
                  <defs>
                    <linearGradient id="faceFront" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a3850" stop-opacity=".98" /><stop offset="1" stop-color="#0a1220" stop-opacity=".99" /></linearGradient>
                    <linearGradient id="faceSide" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1a2436" stop-opacity=".97" /><stop offset="1" stop-color="#0c1420" stop-opacity=".99" /></linearGradient>
                    <linearGradient id="faceTop" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#39465c" stop-opacity=".99" /><stop offset="1" stop-color="#232f44" stop-opacity=".97" /></linearGradient>
                    <linearGradient id="glassShine" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".14" /><stop offset=".5" stop-color="#ffffff" stop-opacity=".04" /><stop offset="1" stop-color="#ffffff" stop-opacity="0" /></linearGradient>
                    <linearGradient id="slabMetal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a94a4" stop-opacity=".55" /><stop offset=".5" stop-color="#5a6474" stop-opacity=".5" /><stop offset="1" stop-color="#3a4452" stop-opacity=".55" /></linearGradient>
                    {/* v64 逼真（对照 1000D 实体图）：拉丝铝饰条 + 蜂窝网孔 + RGB 光带 + 帆标 */}
                    <linearGradient id="aluTrim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6a7686" stop-opacity=".9" /><stop offset=".45" stop-color="#3d4756" stop-opacity=".85" /><stop offset="1" stop-color="#222b36" stop-opacity=".9" /></linearGradient>
                    <radialGradient id="meshDot" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#05080e" stop-opacity=".85" /><stop offset="1" stop-color="#05080e" stop-opacity="0" /></radialGradient>
                    <linearGradient id="rgbStrip" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4e9cff" /><stop offset=".5" stop-color="#a78bfa" /><stop offset="1" stop-color="#f472b6" /></linearGradient>
                    {/* v70 后板立体面：渐变 + 网孔 + 受光层次 */}
                    <linearGradient id="faceRear" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#131b2a" stop-opacity=".99" /><stop offset=".5" stop-color="#1c2636" stop-opacity=".98" /><stop offset="1" stop-color="#0b1220" stop-opacity=".99" /></linearGradient>
                  </defs>
                  {/* v78 水平旋转：面按深度排序绘制（painter's algorithm，z1 小=远先画），
                      旋转到任何角度遮挡都正确；各面细节跟所属面一组 */}
                  {(() => {
                    const faces = []
                    // v84 深度修复：pj() 只返回 [sx,sy]（v79 起），fz 读 p[2] 全 0 → 面深度排序失效
                    // （五个面+14卡条全 0，画序退化成插入序；壁面扇单点 z1 比 SE 面更小 → 被 SE 墙盖住，
                    // 顶扇 2 个被凹槽盖住 → 「前面板扇不像猫扇/后面变普通/顶部只有一个」的总根因）。
                    // 改为手动面深度常数，保持现有视觉层级 + 风扇永远画在所属面之上：
                    //   BASE(-300) → REAR(-250) → FRONT(-200) → SE(-150) → 前G1/最下12NF(-140)
                    //   → TOP(-100) → 后扇(-60) → 卡条(-50) → 卡号(20) → 9733(15)
                    //   （v86：顶/后凹槽删除；后扇改卡条后面——卡条盖住重叠部分）
                    const fz = function (pts) {
                      let sum = 0
                      pts.forEach(function (p) { sum += (p[2] || 0) })
                      return sum / pts.length
                    }
                    // —— 底座组（BASE_T + BASE_SE + 支脚 + 收边高光） ——
                    faces.push({ z: -300, el: (
                      <g key="g-base">
                        <polygon points={poly(BOX.BASE_T)} fill="#141a24" stroke="#4a5462" strokeWidth="1" />
                        <polygon points={poly(BOX.BASE_SE)} fill="#0c1018" stroke="#3a4450" strokeWidth="1" />
                        {/* ⑥ 底座支脚（实体图四角小垫脚） */}
                        {[[-150, -50], [150, -50]].map(function (ft, fi) {
                          return <polygon key={"foot" + fi} points={poly([pj(ft[0], CH + 2, ft[1]), pj(ft[0] + 16, CH + 2, ft[1]), pj(ft[0] + 16, CH + 8, ft[1]), pj(ft[0], CH + 8, ft[1])])} fill="#1c2430" stroke="#3a4450" strokeWidth="0.7" />
                        })}
                        {/* ⑫ 底座收边高光（机箱落地接缝更立体） */}
                        <polygon points={poly([pj(-155, CH, 55), pj(155, CH, 55), pj(155, CH + 1.5, 55), pj(-155, CH + 1.5, 55)])} fill="#39465c" opacity=".5" />
                      </g>
                    ) })
                    // —— 后板组（REAR z=-55：面 + 网孔 + 棱线 + 暗角） ——
                    faces.push({ z: -250, el: (
                      <g key="g-rear">
                        <polygon points={poly(BOX.REAR)} fill="url(#faceRear)" stroke="#4a5462" strokeWidth="1" />
                        {/* 后板蜂窝网孔（8×12 全区，真实 1000D 后板网状冲孔） */}
                        {Array.from({ length: 12 }, function (_, ri) {
                          return Array.from({ length: 8 }, function (_, ci) {
                            const mx = -120 + ci * 34, my = 18 + ri * 13
                            return <circle key={"rmesh" + ri + "-" + ci} cx={pj(mx, my, -55)[0].toFixed(1)} cy={pj(mx, my, -55)[1].toFixed(1)} r="2.2" fill="url(#meshDot)" />
                          })
                        })}
                        {/* 后板左右边缘亮线（受光棱线，立体感） */}
                        <line x1={pj(-155, 0, -55)[0].toFixed(1)} y1={pj(-155, 0, -55)[1].toFixed(1)} x2={pj(-155, CH, -55)[0].toFixed(1)} y2={pj(-155, CH, -55)[1].toFixed(1)} stroke="#6a7686" strokeWidth="0.8" opacity=".5" />
                        <line x1={pj(155, 0, -55)[0].toFixed(1)} y1={pj(155, 0, -55)[1].toFixed(1)} x2={pj(155, CH, -55)[0].toFixed(1)} y2={pj(155, CH, -55)[1].toFixed(1)} stroke="#6a7686" strokeWidth="0.8" opacity=".5" />
                        {/* v73 后板立体深度：左壁深度暗角（背光侧渐暗）+ 左半面横向暗角 + 转折阴影 */}
                        <polygon points={poly([pj(-155, 0, -55), pj(-115, 0, -55), pj(-115, CH, -55), pj(-155, CH, -55)])} fill="#04070d" opacity=".55" />
                        <polygon points={poly([pj(-115, 0, -55), pj(-40, 0, -55), pj(-40, CH, -55), pj(-115, CH, -55)])} fill="#04070d" opacity=".3" />
                        <polygon points={poly([pj(-157, 0, -55), pj(-153, 0, -55), pj(-153, CH, -55), pj(-157, CH, -55)])} fill="#02050b" opacity=".8" />
                      </g>
                    ) })
                    // —— 前面板组（F z=+55：面 + 全部前面板细节） ——
                    faces.push({ z: -200, el: (
                      <g key="g-front">
                        <polygon points={poly(BOX.F)} fill="url(#faceFront)" stroke="#c2ccd8" strokeWidth="1.4" />
                        {/* v65 立体感：正面左缘暗部（背光侧渐暗，强化体积） */}
                        <polygon points={poly([pj(-155, 0, 55), pj(-135, 0, 55), pj(-135, CH, 55), pj(-155, CH, 55)])} fill="#04070d" opacity=".45" />
                        {/* ⑦ 大面板四周内嵌暗框 */}
                        <polygon points={poly([pj(-145, 6, 55), pj(145, 6, 55), pj(145, 164, 55), pj(-145, 164, 55)])} fill="none" stroke="#0a1018" strokeWidth="1.2" opacity=".8" />
                        {/* ⑧ 大面板左右竖直铝饰条 */}
                        <polygon points={poly([pj(-152, 0, 55), pj(-143, 0, 55), pj(-143, CH, 55), pj(-152, CH, 55)])} fill="url(#aluTrim)" opacity=".75" />
                        <polygon points={poly([pj(143, 0, 55), pj(152, 0, 55), pj(152, CH, 55), pj(143, CH, 55)])} fill="url(#aluTrim)" opacity=".75" />
                        {/* ⑨ 面板角铆钉 */}
                        {[[-148, 10], [148, 10], [-148, 160], [148, 160]].map(function (rk, ri) {
                          return <circle key={"riv" + ri} cx={pj(rk[0], rk[1], 55)[0].toFixed(1)} cy={pj(rk[0], rk[1], 55)[1].toFixed(1)} r="1.4" fill="#3a4450" stroke="#0a1018" strokeWidth="0.4" />
                        })}
                        {/* ③ 前面板 I/O 区 + USB */}
                        <polygon points={poly([pj(-90, 0, 46), pj(90, 0, 46), pj(90, 4, 46), pj(-90, 4, 46)])} fill="#060a12" stroke="#2a3444" strokeWidth="0.5" />
                        {[-70, -60, -50, -40, -30].map(function (bx, bi) {
                          return <rect key={"usb" + bi} x={pj(bx, 2, 46)[0].toFixed(1)} y={pj(bx, 2, 46)[1].toFixed(1)} width="3.4" height="1.6" rx="0.6" fill="#3d9bff" opacity=".8" />
                        })}
                        {/* ④ Corsair 帆标 */}
                        <text x={pj(0, 120, 55)[0].toFixed(1)} y={pj(0, 120, 55)[1].toFixed(1)} textAnchor="middle" fontSize="10" fontWeight="700" fill="#7ee2ff" opacity=".5" stroke="#0d1828" strokeWidth="0.3" paintOrder="stroke" fontFamily="'JetBrains Mono','SF Mono',monospace">⛵</text>
                        {/* ⑤ 前面板蜂窝网孔下半区 */}
                        {Array.from({ length: 7 }, function (_, ri) {
                          return Array.from({ length: 5 }, function (_, ci) {
                            const mx = 118 + ci * 9, my = 96 + ri * 9
                            return <circle key={"mesh" + ri + "-" + ci} cx={pj(mx, my, 55)[0].toFixed(1)} cy={pj(mx, my, 55)[1].toFixed(1)} r="1.7" fill="url(#meshDot)" />
                          })
                        })}
                        {/* v69 美化：⑪ 前面板上部 RGB 装饰细线 */}
                        <polygon points={poly([pj(-150, 8, 55), pj(150, 8, 55), pj(150, 9, 55), pj(-150, 9, 55)])} fill="url(#rgbStrip)" opacity=".4" />
                      </g>
                    ) })
                    // —— 右外壁组（SE x=155：面 + 高光 + 玻璃反光） ——
                    faces.push({ z: -150, el: (
                      <g key="g-se">
                        <polygon points={poly(BOX.SE)} fill="url(#faceSide)" stroke="#8a94a2" strokeWidth="1" />
                        {/* 右外壁受光高光 */}
                        <polygon points={poly([pj(155, 0, 30), pj(155, 0, 48), pj(155, CH, 48), pj(155, CH, 30)])} fill="#ffffff" opacity=".05" />
                        {/* 右外壁玻璃反光条 */}
                        <polygon points={poly([pj(155, 0, 40), pj(155, 0, 10), pj(155, CH, 10), pj(155, CH, 40)])} fill="url(#glassShine)" />
                      </g>
                    ) })
                    // —— 顶面组（T y=0：面 + 顶盖三段 + RGB 光带 + 顶面高光） ——
                    faces.push({ z: -100, el: (
                      <g key="g-top">
                        <polygon points={poly(BOX.T)} fill="url(#faceTop)" stroke="#8a94a2" strokeWidth="1" />
                        {/* ① 顶部三段式拉丝铝盖 */}
                        {[[-150, 48], [-52, 46], [46, 44]].map(function (seg, ti) {
                          return <polygon key={"lid" + ti} points={poly([pj(seg[0], 0, seg[1]), pj(seg[0] + 92, 0, seg[1]), pj(seg[0] + 92, 0, seg[1] - 10), pj(seg[0], 0, seg[1] - 10)])} fill="url(#aluTrim)" stroke="#7a8696" strokeWidth="0.6" />
                        })}
                        {/* ② 顶盖前缘 RGB 光带 */}
                        <polygon points={poly([pj(-150, 0, 52), pj(150, 0, 52), pj(150, 0, 55), pj(-150, 0, 55)])} fill="url(#rgbStrip)" opacity=".55" />
                        {/* ⑩ 顶面上方边缘高光 */}
                        <polygon points={poly([pj(-155, 0, 55), pj(155, 0, 55), pj(155, 0, -55), pj(-155, 0, -55)])} fill="url(#glassShine)" opacity=".25" />
                      </g>
                    ) })
                    // —— 显卡仓卡条（内部 z=50，按自身深度参与排序） ——
                    slabs13.forEach(function (s2, i2) {
                      // v96.5：右半功率段切一半为温度段（用户定稿）——
                      // 显存段（左半，模型色）：-110 → -110+108×memLen（最长 -2）
                      // 功率段（右半左半）：2 → 2+52×pwLen（最长 54）；功率 >=200W 黄色 #fbbf24
                      // 温度段（右半右半）：54 → 54+52×tempLen（最长 106）；温度 >=75°C 红色 #ef4444
                      // 分隔线：-2..2（显存|功率）+ 52..56（功率|温度）
                      const memLen = Math.max(0.02, Math.min(1, s2.mem / 100))
                      const pwLen = Math.max(0, Math.min(1, s2.pw / 350))
                      const tempLen = Math.max(0, Math.min(1, s2.temp / 100))
                      const loadColor = (s2.missing ? "#ef4444" : s2.hot ? "#ef4444" : (s2.mColor || (s2.idle ? "#64748b" : "#6e8cff")))
                      const pwColor = s2.pw >= 200 ? "#fbbf24" : (s2.pw > 50 ? "#6e8cff" : "#4e6bd0")
                      const tempColor = s2.temp >= HOT_TEMP ? "#ef4444" : "#7ee2a8"
                      faces.push({ z: -50, el: (
                        <g key={"sl" + i2}>
                          <polygon points={poly([s2.tl, s2.tr, s2.br, s2.bl])} fill="url(#slabMetal)" stroke="#9aa6b4" strokeWidth="0.5" />
                          <polygon points={poly(slabSeg(s2, SLAB_L, SLAB_L + 108 * memLen))} fill={loadColor} opacity={s2.mem > 0 ? ".92" : ".25"} />
                          <polygon points={poly(slabSeg(s2, 2, 2 + 52 * pwLen))} fill={pwColor} opacity={s2.pw > 0 ? ".9" : ".25"} />
                          <polygon points={poly(slabSeg(s2, 54, 54 + 52 * tempLen))} fill={tempColor} opacity={s2.temp > 0 ? ".9" : ".25"} />
                          <polygon points={poly(slabSeg(s2, -2, 2))} fill="#04080f" opacity=".9" />
                          <polygon points={poly(slabSeg(s2, 52, 56))} fill="#04080f" opacity=".9" />
                          {[-100, -85, -75, -60, -45, -30, -15, 0, 15, 28, 40, 55, 70, 88].map(function (fx, k2) {
                            return <line key={"fin" + i2 + "-" + k2} x1={pj(fx, s2.y, SLAB_Z)[0].toFixed(1)} y1={pj(fx, s2.y, SLAB_Z)[1].toFixed(1)} x2={pj(fx, s2.y + SLAB_H, SLAB_Z)[0].toFixed(1)} y2={pj(fx, s2.y + SLAB_H, SLAB_Z)[1].toFixed(1)} stroke="#0a0f16" strokeWidth="0.4" opacity=".35" />
                          })}
                        </g>
                      ) })
                    })
                    // 卡号（v84 从卡条组拆出，深度 20 排 9733 扇(15)之上——
                    // 9733 扇改画卡条上层后，扇右缘会压到卡号左缘 ~3px，卡号后画保清晰）
                    slabs13.forEach(function (s2, i2) {
                      faces.push({ z: 20, el: (
                        <text key={"cardno" + i2} x={pj(132, s2.y + 3, SLAB_Z)[0] + 8} y={pj(132, s2.y + 3, SLAB_Z)[1] + 2.5} textAnchor="start" fontSize="7" fontWeight="700" fill={s2.hot ? "#fca5a5" : "#8ba3ff"} stroke="#0d1828" strokeWidth="0.4" paintOrder="stroke" fontFamily="'JetBrains Mono','SF Mono',monospace">{s2.idx}</text>
                      ) })
                    })
                    // —— 机箱扇 + 9733（v86：顶/后凹槽块整体删除——凹槽深色填充 #03060c
                    //     比扇椭圆大，在扇周围露出黑圈（用户：又一圈黑色的去掉）；
                    //     扇直接画在所属面上，黑圈消失） ——
                    // 机箱扇（15）—— v87 手动深度：顶扇 5（顶面之上）、
                    // 前G1 双列+前NF -140（SE 墙之上）、
                    // 后G2 单列+后NF 10（v87：z=22 全清卡条右缘 → 深度 10 完全可见
                    // =跟前扇一样大，修复 v86 卡条后面被盖「显示很小」）
                    FANS3D.forEach(function (f2, i2) {
                      const dz = i2 <= 2 ? 5 : (i2 <= 9 ? -140 : 10)
                      faces.push({ z: dz, el: noctuaFan(f2, "f3d" + i2, 1.2) })
                    })
                    // 9733（14）—— 卡条前端立面猫扇，卡条之上
                    GPU_FANS13.forEach(function (f2, i2) {
                      // v88：显卡扇改普通工业扇（用户：显卡风扇是普通风扇）
                      faces.push({ z: 15, el: turboFan(f2, "gf3d" + i2) })
                    })
                    // 深度排序：z1 小（远）先画，z1 大（近）后画
                    faces.sort(function (a, b) { return a.z - b.z })
                    return faces.map(function (f) { return f.el })
                  })()}

                  {/* v84：v77 遗留椭圆槽层已删除——它在排序面块之后又画一遍顶面凹槽椭圆
                      （带 #03060c 深色填充），盖在风扇之上，是「顶扇变普通风扇」的根因之一；
                      统一正圆凹槽已在上面排序块内（深度 4/9，永远排扇之下） */}

                  {/* 顶部预留（虚线圈，顶面右后） */}
                  <ellipse cx={pj(130, 0, -25)[0].toFixed(1)} cy={pj(130, 0, -25)[1].toFixed(1)} rx="4.5" ry="4.1" fill="none" stroke="#5a6470" strokeWidth="0.8" strokeDasharray="2,2" />
                  {/* 方位标注（v72：左=后面板(G2 排风壁)，右=前面板(G1 进风壁)） */}
                  <text x={pj(-155, 0, 10)[0].toFixed(1)} y={pj(-155, 0, 10)[1].toFixed(1)} textAnchor="middle" fontSize="9" fontWeight="700" fill="#7ee2ff" stroke="#0d1828" strokeWidth="0.5" paintOrder="stroke" fontFamily="'JetBrains Mono','SF Mono','PingFang SC',monospace">后</text>
                  <text x={pj(155, 0, 10)[0].toFixed(1)} y={pj(155, 0, 10)[1].toFixed(1)} textAnchor="middle" fontSize="9" fontWeight="700" fill="#7ee2ff" stroke="#0d1828" strokeWidth="0.5" paintOrder="stroke" fontFamily="'JetBrains Mono','SF Mono','PingFang SC',monospace">前</text>
                </svg>

                {/* 叶片旋转指示（纯 2D 叠加层，对齐 3D 投影圆心；速度反比 RPM） */}
                {FANS3D.map(function (f2, i2) {
                  const pct = Math.max(0, Math.min(1, f2.rpm / 3450))
                  const spinning = pct > 0.04
                  const dur = spinning ? Math.max(0.25, 1.9 - pct * 1.5) : 0
                  const size = Math.max(6, f2.r * 0.9)
                  const col = fanKindColor[f2.kind] || "#9fc4ff"
                  const stopped = !!f2.stop
                  // v84 覆盖层跟前面板一致：不压不转（sq 已去除），旋转感由 SVG 层 7 叶水滴弧承担
                  return (
                    <span key={"sp" + i2}>
                      {spinning
                        ? <i style={{ ...styles.bladeWheel, left: f2.c[0] - size / 2, top: f2.c[1] - size / 2, width: size, height: size, animationDuration: dur + "s", background: "conic-gradient(from 0deg, rgba(255,224,138,.9) 0 30deg, transparent 30deg 90deg, rgba(255,224,138,.9) 90deg 120deg, transparent 120deg 180deg, rgba(255,224,138,.9) 180deg 210deg, transparent 210deg 270deg, rgba(255,224,138,.9) 270deg 300deg, transparent 300deg 360deg)" }} />
                        : <i style={{ ...(stopped ? styles.fanDotStop : styles.fanDot), left: f2.c[0] - size / 4, top: f2.c[1] - size / 4, width: size / 2, height: size / 2 }} />}
                      <i style={{ position: "absolute", left: f2.c[0] - 1, top: f2.c[1] - 1, width: 2, height: 2, borderRadius: 1, background: stopped ? "#ef4444" : col, opacity: spinning ? .9 : (stopped ? 1 : .45) }} />
                    </span>
                  )
                })}
                {/* 13×9733 叶轮旋转指示（每卡一颗，转速实时）；v69 停转/缺失红点标红 */}
                {GPU_FANS13.map(function (f2, i2) {
                  const pct = Math.max(0, Math.min(1, f2.rpm / 3450))
                  const spinning = pct > 0.04
                  const dur = spinning ? Math.max(0.25, 1.9 - pct * 1.5) : 0
                  const size = Math.max(5, f2.r * 0.9)
                  const stopped = !!(f2.stop || f2.miss)
                  // v84：9733 统一正圆猫扇，覆盖层不转
                  const tform = undefined
                  return (
                    <span key={"gsp" + i2}>
                      {spinning
                        ? <i style={{ ...styles.bladeWheel, left: f2.c[0] - size / 2, top: f2.c[1] - size / 2, width: size, height: size, animationDuration: dur + "s", transform: tform, background: "conic-gradient(from 0deg, rgba(139,163,255,.9) 0 30deg, transparent 30deg 90deg, rgba(139,163,255,.9) 90deg 120deg, transparent 120deg 180deg, rgba(139,163,255,.9) 180deg 210deg, transparent 210deg 270deg, rgba(139,163,255,.9) 270deg 300deg, transparent 300deg 360deg)" }} />
                        : <i style={{ ...(stopped ? styles.fanDotStop : styles.fanDot), left: f2.c[0] - size / 4, top: f2.c[1] - size / 4, width: size / 2, height: size / 2 }} />}
                    </span>
                  )
                })}

                {/* 气流动画（v90 新增：前端进风 → 经过显卡仓 → 后排 G2 排出；
                    竖向 3 条绿色虚线流 + 脉动动画示意气流）
                    前端（屏幕右，G1 进风）→ 后排（屏幕左，G2 排风） */}
                {[62, 130, 198].map(function (flowY, fi) {
                  const fEnd = FANS3D[3].c[0]   // 前 G1 顶部左下的 x
                  const rEnd = FANS3D[10].c[0]  // 后 G2 顶部的 x
                  const x0 = Math.min(fEnd, rEnd) + 4
                  const x1 = Math.max(fEnd, rEnd) - 4
                  return (
                    <span key={"af" + fi} style={{ position: "absolute", left: Math.min(x0, x1), top: flowY, width: Math.abs(x1 - x0), height: 0 }}>
                      <span style={{ display: "block", width: "100%", height: 0, borderTop: "2px dashed rgba(126,226,168,.55)", animation: "vss-airflow 2.4s ease-in-out " + (fi * 0.6) + "s infinite" }} />
                    </span>
                  )
                })}
                {/* 实时转速芯片（v58：随扇标注 + 9733 芯片挪到画布左下空白；
                    CPU/FCH 图形已删，转速并入图例行） */}
                {chip(FANS3D[0].c[0] + 10, FANS3D[0].c[1] - 4, "顶 3×12NF", true)}
                {chip(FANS3D[3].c[0] + 14, FANS3D[3].c[1] - 4, "前 6×G1", true)}
                {chip(FANS3D[9].c[0] + 12, FANS3D[9].c[1] - 4, "前NF", true)}
                {chip(FANS3D[10].c[0] - 12, FANS3D[10].c[1] - 4, "后 4×G2 " + rearRpm, rearRpm > 0)}
                {chip(FANS3D[14].c[0] - 12, FANS3D[14].c[1] + 6, "后NF", rearRpm > 0)}
                {chip(6, 204, "9733×" + (GPU_COUNT - 1) + " · " + gpuRpms13.filter(function (r) { return r > 0 }).length + "转", gpuRpms13.some(function (r) { return r > 0 }))}
                {chip(6, 222, "CPU " + cpuFanRpm + " · FCH " + fchRpm, cpuFanRpm > 0 || fchRpm > 0)}
              </div>
            </div>
          </div>
        )
      })()}


      <div style={styles.foot}>
        <span>更新 {stamp}</span>
        <span>{REFRESH_MS / 1000}s 刷新</span>
      </div>
    </div>
  )
}

// v20-separated-towers-trigger