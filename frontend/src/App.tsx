import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity, AlertTriangle, Bell, Boxes, Check, ChevronRight, CircleGauge, Clock3,
  Cpu, Database, Info, Layers3, Menu, Moon, Palette, PanelLeftClose,
  Radio, Server, Settings2, Sparkles, Sun, Thermometer, Timer, X, Zap,
  CircuitBoard, Fan, Power, ShieldCheck,
  type LucideIcon,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { bytes, compact, duration, number, timeLabel } from './format'
import { mockSnapshot } from './mock'
import type { BmcSensor, GpuItem, Point, Snapshot, VllmInstance } from './types'

type Page = 'dashboard' | 'models' | 'gpus' | 'host' | 'bmc' | 'settings'
type Range = '15m' | '1h' | '6h' | '24h' | '7d'
type Theme = 'midnight' | 'graphite' | 'light'

const nav: Array<{id:Page; label:string; hint:string; icon:LucideIcon}> = [
  {id:'dashboard',label:'Dashboard',hint:'全局态势',icon:CircleGauge},
  {id:'models',label:'模型监控',hint:'Token 与延迟',icon:Sparkles},
  {id:'gpus',label:'GPU 阵列',hint:'逐卡工作负载',icon:Boxes},
  {id:'host',label:'主机性能',hint:'CPU · 内存 · IO',icon:Cpu},
  {id:'bmc',label:'BMC 管理',hint:'功耗 · 温度 · 风扇',icon:CircuitBoard},
]

const titles: Record<Page,[string,string]> = {
  dashboard:['运行态势','模型服务与硬件集群总览'],
  models:['模型监控','推理引擎、吞吐与延迟剖析'],
  gpus:['GPU 阵列','逐卡工作负载与显存热力'],
  host:['主机性能','Linux 资源实时视图'],
  bmc:['BMC 管理','带外传感器、电源与散热状态'],
  settings:['控制台设置','外观、数据源与采集状态'],
}

function useSentinel() {
  const [snapshot,setSnapshot]=useState<Snapshot>(mockSnapshot)
  const [source,setSource]=useState<'connecting'|'live'|'demo'>('connecting')
  useEffect(()=>{
    let closed=false
    fetch('/api/state').then(r=>r.ok?r.json():Promise.reject()).then(data=>{
      if(!closed && data?.host){setSnapshot(data);setSource('live')}
    }).catch(()=>{if(!closed)setSource('demo')})
    const stream=new EventSource('/api/stream')
    stream.onmessage=(event)=>{if(!closed){setSnapshot(JSON.parse(event.data));setSource('live')}}
    stream.onerror=()=>{if(!closed)setSource(current=>current==='live'?'connecting':'demo')}
    return()=>{closed=true;stream.close()}
  },[])
  return {snapshot,source}
}

function useEnergy() {
  const [energy,setEnergy]=useState<{kwh:number;cost:number;days:number}|null>(null)
  useEffect(()=>{
    let closed=false
    const pull=()=>fetch('/api/energy').then(r=>r.ok?r.json():Promise.reject())
      .then((d: {kwh:number;cost:number;days:number})=>{if(!closed&&typeof d.cost==='number')setEnergy(d)})
      .catch(()=>{})
    pull()
    const id=setInterval(pull,60000)
    return()=>{closed=true;clearInterval(id)}
  },[])
  return energy
}

function ChartTip({active,payload,label}:{active?:boolean;payload?:Array<{name:string;value:number;color:string}>;label?:number}) {
  if(!active||!payload?.length)return null
  return <div className="chartTip"><small>{timeLabel(Number(label))}</small>{payload.map(row=><div key={row.name}><i style={{background:row.color}}/><span>{row.name}</span><b>{number(row.value,1)}</b></div>)}</div>
}

function MetricCard({label,value,unit,meta,icon:Icon,tone='blue',progress}:{label:string;value:string;unit?:string;meta:string;icon:LucideIcon;tone?:string;progress?:number}) {
  return <article className={`metricCard tone-${tone}`}>
    <div className="metricHead"><span className="iconBox"><Icon/></span><span className="metricMeta">{meta}</span></div>
    <span className="metricLabel">{label}</span>
    <strong>{value}<em>{unit}</em></strong>
    {progress!==undefined?<div className="thinTrack"><i style={{width:`${Math.min(100,progress)}%`}}/></div>:<div className="microBars">{[42,67,53,81,60,91,73,96].map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}</div>}
  </article>
}

function Panel({title,subtitle,action,children,className=''}:{title:string;subtitle?:string;action?:ReactNode;children:ReactNode;className?:string}) {
  return <section className={`panel ${className}`}><div className="panelHead"><div><h3>{title}</h3>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>{children}</section>
}

function RangePicker({value,onChange}:{value:Range;onChange:(value:Range)=>void}) {
  return <div className="rangePicker">{(['15m','1h','6h','24h','7d'] as Range[]).map(item=><button className={value===item?'active':''} onClick={()=>onChange(item)} key={item}>{item}</button>)}</div>
}

function ProgressRing({value,label,size=86,tone='accent'}:{value:number;label?:string;size?:number;tone?:string}) {
  const safe=Math.max(0,Math.min(100,value)); const radius=36; const circumference=2*Math.PI*radius
  return <div className={`ring tone-${tone}`} style={{width:size,height:size}}><svg viewBox="0 0 86 86"><circle className="ringBg" cx="43" cy="43" r={radius}/><circle className="ringValue" cx="43" cy="43" r={radius} strokeDasharray={circumference} strokeDashoffset={circumference*(1-safe/100)}/></svg><div><b>{number(safe,0)}%</b>{label&&<small>{label}</small>}</div></div>
}

function ThroughputChart({points}:{points:Point[]}) {
  return <div className="chartLarge"><ResponsiveContainer width="100%" height="100%"><AreaChart data={points} margin={{top:8,right:6,left:-18,bottom:0}}>
    <defs><linearGradient id="generationFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--accent)" stopOpacity=".42"/><stop offset="1" stopColor="var(--accent)" stopOpacity="0"/></linearGradient><linearGradient id="promptFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--cyan)" stopOpacity=".22"/><stop offset="1" stopColor="var(--cyan)" stopOpacity="0"/></linearGradient></defs>
    <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="ts" tickFormatter={timeLabel} minTickGap={60} tick={{fill:'var(--text-muted)',fontSize:11}} axisLine={false} tickLine={false}/><YAxis tickFormatter={value=>compact(value)} tick={{fill:'var(--text-muted)',fontSize:11}} axisLine={false} tickLine={false}/><Tooltip content={<ChartTip/>}/>
    <Area type="monotone" dataKey="prompt_tps" name="预填充 tok/s" stroke="var(--cyan)" fill="url(#promptFill)" strokeWidth={1.7}/><Area type="monotone" dataKey="generation_tps" name="生成 tok/s" stroke="var(--accent)" fill="url(#generationFill)" strokeWidth={2.2}/>
  </AreaChart></ResponsiveContainer></div>
}

function MiniArea({points,dataKey,color='var(--accent)',height=100}:{points:Point[];dataKey:keyof Point;color?:string;height?:number}) {
  return <div style={{height}}><ResponsiveContainer width="100%" height="100%"><AreaChart data={points} margin={{top:5,right:0,left:0,bottom:0}}><defs><linearGradient id={`mini-${String(dataKey)}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".3"/><stop offset="1" stopColor={color} stopOpacity="0"/></linearGradient></defs><Area type="monotone" dataKey={dataKey} stroke={color} fill={`url(#mini-${String(dataKey)})`} strokeWidth={1.8}/></AreaChart></ResponsiveContainer></div>
}

function fleetSummary(items:GpuItem[]):string {
  const counts=new Map<string,number>()
  for (const g of items) counts.set(g.name,(counts.get(g.name)||0)+1)
  return [...counts.entries()].map(([name,c])=>`${c} × ${name.replace(/^NVIDIA /,'').replace(/^GeForce /,'')}`).join(' + ')
}

// ===== 桌面组件同款：模型归一 + 固定唯一配色 + 分时电费（与 Mac Übersicht 组件一致） =====
const CANON_MODEL=(raw:string):string=>{
  const r=raw||''
  // 2026-09-29 与桌面组件 v96.8/v96.9 对齐：
  // ① Qwen3.8 家族按体量区分（INT8 全量 / Flash-Next 精简 / 其余 W4A16）——旧规则把所有
  //    qwen3.8 一律归成 Qwen3.8-27B-W4A16，导致三卡的 Flash-Next 在页面上被叫成 "Qwen3.8"；
  // ② DeepSeek V4.1 用裸名上报，旧规则只认 DSV4* → 落到兜底 → 标签被截成 "DeepSeek"。
  // 精确匹配必须排在通用前缀之前（对象/正则顺序即优先级）。
  if(/^qwen3\.8-27b-int8/i.test(r))return'Qwen3.8-27B-INT8'
  if(/^qwen3\.8-flash[\s_-]?next/i.test(r))return'Qwen3.8-Flash-Next'
  if(/^(qwen3\.8)/i.test(r))return'Qwen3.8-27B-W4A16'
  if(/^DeepSeek[-_ ]?V4\.1/i.test(r))return'DeepSeek-V4.1-Flash'
  if(/^DSV4/i.test(r))return'DeepSeek-V4-Flash-Exp'
  if(/^DeepSeek[-_ ]?V4/i.test(r))return'DeepSeek-V4-Flash-Exp'
  if(/^GLM/i.test(r))return'GLM-5.3-Flash'
  if(/^WeMM/i.test(r))return'WeMM-Embedding-9B'
  if(/^MiniMax/i.test(r))return'MiniMax-H3'
  if(/^Unlimited[-_ ]?OCR/i.test(r))return'Unlimited-OCR'
  return r
}
const MODEL_COLOR_MAP:Record<string,string>={
  'DeepSeek-V4-Flash-Exp':'#4e9cff','GLM-5.3-Flash':'#34d399','Qwen3.8-27B-W4A16':'#f59e0b',
  'WeMM-Embedding-9B':'#a78bfa','Meeting-ASR':'#f472b6','MiniMax-H3':'#22d3ee',
  'WeMM-Embedding-9B-CPU':'#facc15','Qwen3-Embedding-0.6B':'#60a5fa','CosyVoice-TTS':'#fb923c',
  'FishSpeech-TTS':'#4ade80','GPT-SoVITS-TTS':'#c084fc','Whisper-ASR':'#2dd4bf','Unlimited-OCR':'#e879f9',
  // 与组件同色（组件这几个名字走哈希回退，实测结果固定为下列值；写死避免两端口径漂移）
  'DeepSeek-V4.1-Flash':'#4e9cff','Qwen3.8-Flash-Next':'#f59e0b','Qwen3.8-27B-INT8':'#a78bfa',
}
const FALLBACK_COLORS=['#4e9cff','#34d399','#f59e0b','#a78bfa','#f472b6','#22d3ee']
const __modelColorAssigned:Record<string,string>={}
const modelColor=(name:string):string=>{
  if(MODEL_COLOR_MAP[name])return MODEL_COLOR_MAP[name]
  // v92：新模型颜色防撞——动态分配器（模块级状态持久化，同一模型颜色稳定）；
  // 新名字出现时从 FALLBACK_COLORS 里挑一个未被当前活跃模型占用的颜色，
  // 保证新模型与现有模型颜色都不同；活跃模型 >6 色时才循环复用
  if(__modelColorAssigned[name])return __modelColorAssigned[name]
  let h=0;const s=name||''
  for(let i=0;i<s.length;i++)h=(h+s.charCodeAt(i)*(i+7))%997
  const used=new Set<string>([...Object.values(__modelColorAssigned),...Object.values(MODEL_COLOR_MAP)])
  const free=FALLBACK_COLORS.filter(c=>!used.has(c))
  const pick=free.length?free[h%free.length]:FALLBACK_COLORS[h%FALLBACK_COLORS.length]
  __modelColorAssigned[name]=pick
  return pick
}
const SHORT_NAMES:Record<string,string>={
  'GLM-5.3-Flash':'GLM-5.3','DeepSeek-V4-Flash-Exp':'DSV4-V','Qwen3.8-27B-W4A16':'Qwen3.8',
  // 与组件 v96.8/v96.9 短名对齐（GPU 瓦片标签用；不补这几条会被 slice 截成 "DeepSeek"/"Qwen3.8-"）
  'DeepSeek-V4.1-Flash':'DSV4.1','Qwen3.8-Flash-Next':'Qwen3.8-Next','Qwen3.8-27B-INT8':'Qwen3.8-INT8',
  'WeMM-Embedding-9B':'EB-9B','Meeting-ASR':'Meet-ASR','WeMM-Embedding-9B-CPU':'EB-CPU',
  'Qwen3-Embedding-0.6B':'Emb-0.6B','CosyVoice-TTS':'CosyTTS','FishSpeech-TTS':'FishTTS',
  'GPT-SoVITS-TTS':'SoVITS','Whisper-ASR':'Whisper','Unlimited-OCR':'OCR',
}
const PRICE_FLAT=0.736945, PRICE_PEAK=1.133475, PRICE_VALLEY=0.457041
const touPrice=(date:Date):{price:number;tier:string;label:string}=>{
  const hm=date.getHours()*60+date.getMinutes()
  const summer=[0,6,7,11].includes(date.getMonth())
  if(hm<420||(hm>=660&&hm<840))return{price:PRICE_VALLEY,tier:'谷',label:'低谷 0:00-7:00 · 11:00-14:00'}
  if(summer&&hm>=1080&&hm<1320)return{price:PRICE_PEAK,tier:'尖',label:'尖峰 18:00-22:00（夏冬季）'}
  if((hm>=420&&hm<660)||(hm>=840&&hm<960)||hm>=1380)return{price:PRICE_FLAT,tier:'平',label:'平段 7:00-11:00 · 14:00-16:00 · 23:00-24:00'}
  return{price:PRICE_PEAK,tier:'峰',label:summer?'高峰 16:00-18:00 · 22:00-23:00':'高峰 16:00-23:00'}
}

interface ModelRow{name:string;online:boolean;tok:number;kv:number;gpus:number[];kind:'vllm'|'gpu'|'cpu'}
function modelRowsOf(data:Snapshot):ModelRow[]{
  const byCanon=new Map<string,{row:ModelRow;kvN:number}>()
  for(const inst of data.vllm.instances||[]){
    const canon=CANON_MODEL(inst.models?.[0]||inst.name)
    const entry=byCanon.get(canon)||{row:{name:canon,online:false,tok:0,kv:0,gpus:[],kind:'vllm'},kvN:0}
    const r=entry.row
    if(inst.online){r.online=true;r.tok+=Number(inst.generation_tokens_per_second)||0;entry.kvN++;r.kv+=Number(inst.kv_cache_percent)||0}
    for(const gi of inst.gpus||[])if(!r.gpus.includes(gi))r.gpus.push(gi)
    byCanon.set(canon,entry)
  }
  const rows=[...byCanon.values()].map(({row,kvN})=>({...row,kv:kvN?row.kv/kvN:0}))
  for(const gm of data.gpu_map||[]){
    const canon=CANON_MODEL(gm.service)
    if(byCanon.has(canon))continue
    rows.push({name:canon,online:true,tok:0,kv:0,gpus:[...(gm.gpus||[])].sort((a,b)=>a-b),kind:'gpu'})
  }
  for(const sm of data.small_models||[]){
    const canon=CANON_MODEL(sm.name)
    if(byCanon.has(canon))continue
    rows.push({name:canon,online:true,tok:0,kv:0,gpus:[],kind:'cpu'})
  }
  rows.sort((x,y)=>(Number(y.online)-Number(x.online))||x.name.localeCompare(y.name))
  return rows
}

function ModelServicePanel({data}:{data:Snapshot}){
  const rows=modelRowsOf(data)
  const online=rows.filter(r=>r.online).length
  return <Panel title="模型服务" subtitle="所有在跑模型（vLLM 大模型 + GPU/CPU 小模型）· 与桌面组件一致" action={<span className="onlineTag"><i/>{online}/{rows.length} 在线</span>}>
    <div className="modelServiceList">
      {rows.map(m=>{
        const color=modelColor(m.name)
        const label=SHORT_NAMES[m.name]||m.name.slice(0,10)
        const val=m.kind==='cpu'?'CPU · 进程在跑'
          :m.kind==='gpu'?`GPU ${m.gpus.join(',')} · 显存`
          :m.online?`GPU ${m.gpus.join(',')||'-'} · ${number(m.tok,1)}t/s · K${number(m.kv,0)}%`:'--'
        return <div className="modelServiceRow" key={m.name}>
          <i className="modelDot" style={{background:color}}/>
          <b style={{color}}>{label}</b>
          <em>{m.kind==='vllm'?'vLLM':m.kind==='gpu'?'GPU 服务':'CPU 服务'}</em>
          <span>{val}</span>
        </div>
      })}
    </div>
  </Panel>
}

function EnergyPanel({data,energy}:{data:Snapshot;energy:{kwh:number;cost:number;days:number;cost_month?:number;cost_year?:number;cost_month_est?:number}|null}){
  const tou=touPrice(new Date())
  const totalW=data.gpu.power_w+200
  return <Panel title="实时电费" subtitle={`浙江滨江商业用电（单一制不满1千伏）· ${tou.label}`}>
    <div className="energyGrid">
      <div><span>当前段位</span><b>{tou.tier}段 {tou.price.toFixed(4)} 元/度</b></div>
      <div><span>实时电费</span><b>{number(totalW/1000*tou.price,2)} 元/时</b></div>
      <div><span>整机功耗</span><b>{number(totalW,1)} W（GPU实时+200W固定）</b></div>
      <div><span>本月电费（预估）/ 本年电费总额</span><b>{energy?`${number(energy.cost_month_est ?? energy.cost_month ?? energy.cost,2)} 元 / ${number(energy.cost_year ?? energy.cost,2)} 元（本月${energy.days}天）`:'--'}</b></div>
    </div>
  </Panel>
}

function GpuTile({gpu,selected,onClick,rank}:{gpu:GpuItem;selected?:boolean;onClick?:()=>void;rank?:number}) {
  const hot=gpu.temperature>=78
  const svc=gpu.service?CANON_MODEL(gpu.service):''
  const svcColor=svc?modelColor(svc):undefined
  const svcLabel=svc?(SHORT_NAMES[svc]||svc.slice(0,8)):''
  return <button className={`gpuTile ${selected?'selected':''}`} onClick={onClick}>
    <div className="gpuTileHead"><span>{rank!==undefined&&<em className="gpuRank">#{rank}</em>}<i className={hot?'hot':''}/><b>GPU {gpu.index}</b>{svcLabel&&<em className="gpuSvc" style={svcColor?{color:svcColor}:{}}>{svcLabel}</em>}</span><em>{gpu.pstate}</em></div>
    <strong>{number(gpu.utilization,0)}<small>%</small></strong>
    <div className="segmented">{Array.from({length:12},(_,i)=><i className={i<Math.round(gpu.utilization/8.34)?'on':''} key={i}/>)}</div>
    <div className="gpuTileFoot"><span>{number(gpu.memory_used_mb/1024,1)} / {number(gpu.memory_total_mb/1024,0)} GB</span><span className={hot?'hotText':''}>{number(gpu.temperature,0)}°C</span></div>
  </button>
}

function Dashboard({data,points,range,setRange,energy}:{data:Snapshot;points:Point[];range:Range;setRange:(r:Range)=>void;energy:{kwh:number;cost:number;days:number;cost_month?:number;cost_year?:number;cost_month_est?:number}|null}) {
  const a=data.vllm.aggregate
  return <>
    <div className="kpiGrid six">
      <MetricCard label="生成吞吐" value={number(a.generation_tokens_per_second,1)} unit="tok/s" meta="实时 decode" icon={Zap} tone="violet"/>
      <MetricCard label="预填充吞吐" value={number(a.prompt_tokens_per_second,0)} unit="tok/s" meta="实时 prefill" icon={Activity} tone="cyan"/>
      <MetricCard label="P95 首 Token" value={number(a.ttft_p95_ms,0)} unit="ms" meta={`P50 ${number(a.ttft_p50_ms,0)} ms`} icon={Timer} tone="blue"/>
      <MetricCard label="P95 每 Token" value={number(a.tpot_p95_ms,1)} unit="ms" meta={`P99 ${number(a.tpot_p99_ms,1)} ms`} icon={Clock3} tone="green"/>
      <MetricCard label="活跃请求" value={number(a.running,0)} unit="running" meta={`${number(a.waiting,0)} queued`} icon={Layers3} tone="amber"/>
      <MetricCard label="KV Cache" value={number(a.kv_cache_percent,1)} unit="%" meta="块使用率" icon={Database} tone="green" progress={a.kv_cache_percent}/>
    </div>
    <div className="dashboardGrid">
      <Panel title="Token 实时流" subtitle="预填充与生成吞吐趋势" action={<RangePicker value={range} onChange={setRange}/>} className="throughputPanel"><ThroughputChart points={points}/><div className="chartLegend"><span><i className="cyan"/>预填充 {number(a.prompt_tokens_per_second,1)} tok/s</span><span><i/>生成 {number(a.generation_tokens_per_second,1)} tok/s</span><b>总计 {compact(a.prompt_tokens_total+a.generation_tokens_total)} tokens</b></div></Panel>
      <Panel title="集群压力" subtitle="推理与硬件实时负载" className="pressurePanel"><div className="ringRow"><ProgressRing value={data.gpu.utilization} label="GPU"/><ProgressRing value={data.gpu.memory_percent} label="显存" tone="cyan"/><ProgressRing value={data.host.cpu.usage} label="CPU" tone="green"/></div><div className="pressureList"><div><span>总功耗</span><b>{number(data.gpu.power_w,0)} W</b></div><div><span>主机内存</span><b>{number(data.host.memory.percent,1)}%</b></div><div><span>最高温度</span><b>{number(data.gpu.max_temperature,0)}°C</b></div></div></Panel>
      <Panel title="GPU 工作负载矩阵" subtitle={`${data.gpu.count} 卡 · 实时排序 负载×0.7 + 温度×0.3`} action={<span className="onlineTag"><i/>实时排序</span>} className="gpuMatrix"><div className="gpuTileGrid">{[...data.gpu.items].sort((a,b)=>(b.utilization*0.7+b.temperature*0.3)-(a.utilization*0.7+a.temperature*0.3)).map((gpu,idx)=><GpuTile gpu={gpu} rank={idx+1} key={gpu.uuid}/>)}</div></Panel>
      <Panel title="并发与排队" subtitle="正在执行、等待与 KV Cache" className="concurrencyPanel"><div className="queueNumbers"><div><b>{number(a.running,0)}</b><span>Running</span></div><div><b>{number(a.waiting,0)}</b><span>Queued</span></div><div><b>{number(a.swapped,0)}</b><span>Swapped</span></div></div><div className="queueChart"><ResponsiveContainer width="100%" height="100%"><LineChart data={points}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="ts" hide/><YAxis hide/><Tooltip content={<ChartTip/>}/><Line type="monotone" name="运行中" dataKey="running" stroke="var(--green)" dot={false} strokeWidth={2}/><Line type="monotone" name="排队" dataKey="waiting" stroke="var(--amber)" dot={false} strokeWidth={2}/></LineChart></ResponsiveContainer></div></Panel>
      <ModelServicePanel data={data}/>
      <EnergyPanel data={data} energy={energy}/>
    </div>
  </>
}

function InstanceCard({item}:{item:VllmInstance}) {
  return <article className="instanceCard"><div className="instanceTop"><div className="instanceIcon"><Sparkles/></div><div><span className="statusLine"><i className={item.online?'':'offline'}/>{item.online?'在线':'离线'}</span><h3>{item.models[0]||item.name}</h3><p>{item.name} · {item.url.replace(/^https?:\/\//,'')}</p></div><ChevronRight/></div><div className="instanceStats"><div><span>生成 TPS</span><b>{number(item.generation_tokens_per_second,1)}</b></div><div><span>运行 / 排队</span><b>{number(item.running,0)} / {number(item.waiting,0)}</b></div><div><span>KV Cache</span><b>{number(item.kv_cache_percent,1)}%</b></div><div><span>Prefix Cache 命中</span><b>{number(item.prefix_cache_hit_percent,1)}%</b></div><div><span>请求总量</span><b>{compact(item.requests_total)}</b></div></div></article>
}

function ModelsPage({data,points}:{data:Snapshot;points:Point[]}) {
  const a=data.vllm.aggregate
  const latency=[{name:'P50',TTFT:a.ttft_p50_ms,TPOT:a.tpot_p50_ms*20},{name:'P95',TTFT:a.ttft_p95_ms,TPOT:a.tpot_p95_ms*20},{name:'P99',TTFT:a.ttft_p99_ms,TPOT:a.tpot_p99_ms*20}]
  return <>
    <div className="modelHero"><div><span className="sectionEyebrow">ACTIVE MODEL</span><h2>{a.models?.[0] || '等待模型指标'}</h2><p>{a.online_instances} / {a.total_instances} 实例在线 · 累计处理 {compact(a.prompt_tokens_total+a.generation_tokens_total)} tokens</p></div><div className="modelHeroMetrics"><div><span>Prefix Cache 命中</span><b>{number(a.prefix_cache_hit_percent,1)}%</b></div><div><span>Spec Decode 接受率</span><b>{number(a.spec_accept_percent,1)}%</b></div><div><span>请求速率</span><b>{number(a.requests_per_second,2)}<small>/s</small></b></div></div></div>
    <div className="modelGrid">
      <Panel title="延迟分位" subtitle="TTFT 与 TPOT（TPOT ×20 便于对比）"><div className="barChart"><ResponsiveContainer width="100%" height="100%"><BarChart data={latency} barGap={4}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill:'var(--text-muted)'}}/><YAxis axisLine={false} tickLine={false} tick={{fill:'var(--text-muted)',fontSize:11}}/><Tooltip/><Bar dataKey="TTFT" name="TTFT ms" fill="var(--accent)" radius={[5,5,0,0]}/><Bar dataKey="TPOT" name="TPOT × 20" fill="var(--cyan)" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></Panel>
      <Panel title="延迟健康度" subtitle="关键 SLO 观测"><div className="latencyList"><div><span>端到端 P95</span><b>{number(a.e2e_p95_ms/1000,2)} s</b><i><u style={{width:`${Math.min(100,a.e2e_p95_ms/80)}%`}}/></i></div><div><span>排队 P95</span><b>{number(a.queue_p95_ms,0)} ms</b><i><u className="cyan" style={{width:`${Math.min(100,a.queue_p95_ms/5)}%`}}/></i></div><div><span>TTFT P99</span><b>{number(a.ttft_p99_ms,0)} ms</b><i><u className="amber" style={{width:`${Math.min(100,a.ttft_p99_ms/20)}%`}}/></i></div></div></Panel>
      <Panel title="生成吞吐稳定性" subtitle="实时 token 生成速率" className="wide"><MiniArea points={points} dataKey="generation_tps" height={175}/><div className="inlineStats"><div><span>当前</span><b>{number(a.generation_tokens_per_second,1)} tok/s</b></div><div><span>累计输出</span><b>{compact(a.generation_tokens_total)} tokens</b></div><div><span>累计输入</span><b>{compact(a.prompt_tokens_total)} tokens</b></div></div></Panel>
    </div>
    <h2 className="sectionTitle">服务实例</h2><div className="instancesGrid">{data.vllm.instances.map(item=><InstanceCard item={item} key={item.name}/>)}</div>
  </>
}

function GpusPage({data,points}:{data:Snapshot;points:Point[]}) {
  const [selected,setSelected]=useState(0)
  const gpu=data.gpu.items[selected]||data.gpu.items[0]
  return <>
    <div className="gpuSummary"><div><span>GPU FABRIC</span><h2>{fleetSummary(data.gpu.items)}</h2><p>{number(data.gpu.memory_total_mb/1024,0)} GB 显存池 · {number(data.gpu.power_w,0)} W 实时功耗 · 最高 {number(data.gpu.max_temperature,0)}°C</p></div><div className="summaryRings"><ProgressRing value={data.gpu.utilization} label="计算" size={96}/><ProgressRing value={data.gpu.memory_percent} label="显存" size={96} tone="cyan"/></div></div>
    <div className="gpuPageGrid"><div className="gpuSelectGrid">{[...data.gpu.items].sort((a,b)=>(b.utilization*0.7+b.temperature*0.3)-(a.utilization*0.7+a.temperature*0.3)).map((item,idx)=><GpuTile key={item.uuid} gpu={item} rank={idx+1} selected={item.index===selected} onClick={()=>setSelected(item.index)}/>)}</div>
    {gpu&&<Panel title={`GPU ${gpu.index} · ${gpu.name}`} subtitle={`${gpu.uuid} · ${gpu.pstate}`} action={<span className="tempBadge"><Thermometer/> {number(gpu.temperature,0)}°C</span>} className="gpuDetail"><div className="selectedGpuTop"><ProgressRing value={gpu.utilization} label="GPU" size={112}/><div className="detailMetrics"><div><span>显存</span><b>{number(gpu.memory_used_mb/1024,2)} / {number(gpu.memory_total_mb/1024,0)} GB</b></div><div><span>功耗</span><b>{number(gpu.power_w,0)} / {number(gpu.power_limit_w,0)} W</b></div><div><span>核心频率</span><b>{number(gpu.clock_sm_mhz,0)} MHz</b></div><div><span>显存频率</span><b>{number(gpu.clock_memory_mhz,0)} MHz</b></div></div></div><MiniArea points={points} dataKey="gpu" color="var(--green)" height={105}/><div className="processList"><span>GPU 进程</span>{gpu.processes.length?gpu.processes.map(process=><div key={process.pid}><i/><b>{process.name}</b><small>PID {process.pid}</small><em>{number(process.memory_mb/1024,2)} GB</em></div>):<p>当前没有计算进程</p>}</div></Panel>}</div>
  </>
}

function PerfPanel({label,value,unit,sub,color,dataKey,points,children}:{label:string;value:string;unit?:string;sub:string;color:string;dataKey:keyof Point;points:Point[];children?:ReactNode}) {
  return <Panel title={label} subtitle={sub} className="perfPanel" action={<strong className="perfValue">{value}<small>{unit}</small></strong>}><MiniArea points={points} dataKey={dataKey} color={color} height={150}/>{children}</Panel>
}

function HostPage({data,points}:{data:Snapshot;points:Point[]}) {
  const h=data.host
  return <div className="hostLayout">
    <Panel title="CPU" subtitle={h.cpu.model} action={<div className="cpuHeadline"><b>{number(h.cpu.usage,0)}%</b><span>{number(h.cpu.frequency_mhz/1000,2)} GHz</span></div>} className="cpuPanel"><div className="cpuChart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={points}><defs><linearGradient id="cpuFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--accent)" stopOpacity=".35"/><stop offset="1" stopColor="var(--accent)" stopOpacity=".02"/></linearGradient></defs><CartesianGrid stroke="var(--chart-grid)"/><XAxis dataKey="ts" hide/><YAxis domain={[0,100]} hide/><Tooltip content={<ChartTip/>}/><Area type="monotone" dataKey="cpu" name="CPU %" stroke="var(--accent)" fill="url(#cpuFill)" strokeWidth={2}/></AreaChart></ResponsiveContainer></div><div className="logicalGrid">{h.cpu.per_core.map((value,index)=><div key={index} title={`逻辑处理器 ${index}: ${number(value,1)}%`}><i style={{height:`${Math.max(2,value)}%`}}/></div>)}</div><div className="cpuDetails"><div><span>插槽</span><b>{h.cpu.cores <= 16 ? 1 : 2}</b></div><div><span>核心</span><b>{h.cpu.cores}</b></div><div><span>逻辑处理器</span><b>{h.cpu.threads}</b></div><div><span>负载 1m / 5m / 15m</span><b>{h.cpu.load.map(v=>number(v,2)).join(' / ')}</b></div><div><span>运行时间</span><b>{duration(h.uptime)}</b></div></div></Panel>
    <div className="perfGrid"><PerfPanel label="内存" value={bytes(h.memory.used)} sub={`${bytes(h.memory.total)} DDR4 · ${number(h.memory.percent,1)}% 已用`} color="var(--violet)" dataKey="memory" points={points}><div className="memoryComposition"><i style={{width:`${h.memory.percent}%`}}/><span>可用 {bytes(h.memory.available)}</span></div></PerfPanel><PerfPanel label="GPU 显存" value={number(data.gpu.memory_used_mb/1024,1)} unit="GB" sub={`${number(data.gpu.memory_total_mb/1024,0)} GB 总量`} color="var(--cyan)" dataKey="gpu_memory" points={points}/><PerfPanel label="磁盘" value={number(h.disk.percent,1)} unit="%" sub={`${bytes(h.disk.used)} / ${bytes(h.disk.total)}`} color="var(--green)" dataKey="disk" points={points}><div className="ioRow"><span>读取 <b>{bytes(h.disk.read_bps)}/s</b></span><span>写入 <b>{bytes(h.disk.write_bps)}/s</b></span></div></PerfPanel><PerfPanel label="网络" value={bytes(h.network.rx_bps)} unit="/s" sub="主机总吞吐" color="var(--amber)" dataKey="net" points={points}><div className="ioRow"><span>接收 <b>{bytes(h.network.rx_bps)}/s</b></span><span>发送 <b>{bytes(h.network.tx_bps)}/s</b></span></div></PerfPanel></div>
  </div>
}

function SensorStatus({sensor}:{sensor:BmcSensor}) {
  const value=sensor.value??0
  const warning=sensor.upper_warning??sensor.upper_critical??80
  const ratio=sensor.units==='RPM'?Math.min(100,value/80):Math.min(100,value/warning*75)
  const tone=sensor.status!=='ok'?'critical':sensor.units==='degrees C'&&value>=warning?'warning':'ok'
  return <article className={`sensorCard ${tone}`}><div><span>{sensor.name}</span><em><i/>{sensor.status.toUpperCase()}</em></div><strong>{number(value,sensor.units==='Volts'?3:0)}<small>{sensor.units==='degrees C'?'°C':sensor.units}</small></strong><div className="sensorTrack"><i style={{width:`${ratio}%`}}/></div>{sensor.upper_warning!=null&&<p>警告阈值 {number(sensor.upper_warning,0)}{sensor.units==='degrees C'?'°C':` ${sensor.units}`}</p>}</article>
}

function BmcPage({data,points}:{data:Snapshot;points:Point[]}) {
  const b=data.bmc
  const power=b.power||{instant_w:0,minimum_w:0,maximum_w:0,average_w:0,sampling_seconds:0,state:'unknown'}
  const majorNames=['CPU1 Temp','CPU2 Temp','PCH Temp','System Temp','Peripheral Temp','Vcpu1VRM Temp','Vcpu2VRM Temp']
  const major=b.temperatures.filter(sensor=>majorNames.includes(sensor.name))
  const maxTemp=Math.max(0,...b.temperatures.map(sensor=>sensor.value||0))
  const avgFan=b.fans.length?b.fans.reduce((sum,sensor)=>sum+(sensor.value||0),0)/b.fans.length:0
  return <>
    <div className={`bmcHero ${b.online?'online':'offline'}`}><div className="bmcIdentity"><span className="bmcIcon"><CircuitBoard/></span><div><span className="sectionEyebrow">OUT-OF-BAND MANAGEMENT</span><h2>{b.info.manufacturer_name||'BMC Controller'}</h2><p>IPMI {b.info.ipmi_version||'—'} · 固件 {b.info.firmware_revision||'—'} · {b.online?'传感器实时在线':'采集器离线'}</p></div></div><div className="bmcHeroStats"><div><Power/><span>整机功耗<b>{number(data.gpu.power_w+200,0)} W</b></span></div><div><Thermometer/><span>最高温度<b>{number(maxTemp,0)}°C</b></span></div><div><Fan/><span>平均风扇<b>{number(avgFan,0)} RPM</b></span></div><em><i/>{b.online?'BMC ONLINE':'OFFLINE'}</em></div></div>
    <div className="bmcGrid">
      <Panel title="整机电源功耗" subtitle="估算 = GPU 总功耗 + 其他 ~200W · 电源额定 2600W + 2200W" action={<span className="powerState"><i/>估算</span>} className="bmcPower"><div className="powerHeadline"><strong>{number(data.gpu.power_w+200,0)}<small>W</small></strong><div><span>GPU 占比</span><b>{data.gpu.power_w?number(data.gpu.power_w/(data.gpu.power_w+200)*100,1):0}%</b></div></div><MiniArea points={points} dataKey="power" color="var(--amber)" height={145}/><div className="powerStats"><div><span>GPU + 其他</span><b>{number(data.gpu.power_w,0)} + 200 W</b></div><div><span>电源额定</span><b>2600 + 2200 W</b></div></div></Panel>
      <Panel title="电源模块" subtitle="冗余 PSU 在线与健康状态" className="psuPanel"><div className="psuGrid">{b.psus.map((psu,index)=><article className={psu.status==='ok'?'ok':'bad'} key={psu.name}><div><span><Power/></span><em><i/>{psu.status.toUpperCase()}</em></div><h3>PSU {index+1}</h3><p>{psu.name}</p><b><ShieldCheck/>{psu.detail}</b></article>)}</div><div className="bmcInfo"><div><span>设备可用</span><b>{b.info.device_available||'—'}</b></div><div><span>固件版本</span><b>{b.info.firmware_revision||'—'}</b></div><div><span>IPMI 版本</span><b>{b.info.ipmi_version||'—'}</b></div><div><span>最后采样</span><b>{b.timestamp?timeLabel(b.timestamp):'—'}</b></div></div></Panel>
      <Panel title="关键温度传感器" subtitle={`${b.temperatures.length} 个有效温度探头`} action={<span className="tempBadge"><Thermometer/>{number(maxTemp,0)}°C max</span>} className="bmcTemps"><div className="sensorGrid">{major.map(sensor=><SensorStatus sensor={sensor} key={sensor.name}/>)}</div></Panel>
      <Panel title="风扇阵列" subtitle={`${b.fans.length} 个系统风扇 · GPU 风扇 PWM×3450 RPM`} action={<span className="onlineTag"><i/>实时</span>} className="bmcFans"><div className="fanGrid">{[...b.fans, ...data.gpu.items.map(g=>({name:`GPU ${g.index} 风扇`, units:'RPM', status:'ok', value:g.fan_rpm||0}))].map(sensor=><article key={`fan-${sensor.name}`}><div className="fanVisual"><Fan/><i style={{animationDuration:`${Math.max(.35,8000/(sensor.value||1))}s`}}/></div><div><span>{sensor.name}<small style={{display:'block',opacity:.7}}>PWM {number((sensor.value||0)/3450*100,0)}%</small></span><b>{number(sensor.value||0,0)}<small>RPM</small></b><em><i/>{sensor.status}</em></div></article>)}</div></Panel>
      <Panel title="全部传感器" subtitle="温度、电压和离散状态的原始 BMC 读数" className="bmcSensors"><div className="sensorTable"><div className="sensorTableHead"><span>传感器</span><span>读数</span><span>状态</span><span>警告 / 临界阈值</span></div>{[...b.temperatures,...b.voltages].map(sensor=><div className="sensorTableRow" key={sensor.name}><b>{sensor.name}</b><code>{number(sensor.value||0,sensor.units==='Volts'?3:0)} {sensor.units==='degrees C'?'°C':sensor.units}</code><em className={sensor.status==='ok'?'ok':'bad'}><i/>{sensor.status}</em><span>{sensor.upper_warning!=null?`${number(sensor.upper_warning,1)} / ${number(sensor.upper_critical||0,1)}`:'—'}</span></div>)}</div></Panel>
    </div>
  </>
}

function SettingsPage({data,theme,setTheme,hue,setHue}:{data:Snapshot;theme:Theme;setTheme:(t:Theme)=>void;hue:number;setHue:(v:number)=>void}) {
  return <div className="settingsGrid"><Panel title="界面主题" subtitle="仅保存在当前浏览器"><div className="themeOptions">{([{id:'midnight',name:'深海蓝',colors:['#08111d','#111f31','#6e8cff']},{id:'graphite',name:'石墨黑',colors:['#0c0d0f','#181b20','#a38bff']},{id:'light',name:'月光白',colors:['#f3f6fa','#ffffff','#5674ed']}] as Array<{id:Theme;name:string;colors:string[]}>).map(item=><button className={theme===item.id?'active':''} onClick={()=>setTheme(item.id)} key={item.id}><span>{item.colors.map(color=><i style={{background:color}} key={color}/>)}</span><b>{item.name}</b>{theme===item.id&&<Check/>}</button>)}</div><label className="hueControl"><span><Palette/>强调色 <b>{hue}°</b></span><input type="range" min="180" max="320" value={hue} onChange={e=>setHue(Number(e.target.value))}/></label></Panel><Panel title="数据采集" subtitle="只读采集，不会修改 vLLM"><div className="configList"><div><span><Radio/>采样间隔</span><b>{data.sample_interval} 秒</b></div><div><span><Database/>历史保留</span><b>7 天</b></div><div><span><Server/>主机</span><b>{data.host.hostname}</b></div><div><span><Boxes/>GPU</span><b>{data.gpu.count} 张已识别</b></div><div><span><CircuitBoard/>BMC / IPMI</span><b>{data.bmc.online?'在线':'离线'}</b></div></div></Panel><Panel title="vLLM 数据源" subtitle="Prometheus /metrics 端点" className="wide"><div className="sourceTable"><div className="sourceHead"><span>实例</span><span>端点</span><span>模型</span><span>状态</span></div>{data.vllm.instances.map(item=><div className="sourceRow" key={item.name}><b>{item.name}</b><code>{item.url}/metrics</code><span>{item.models[0]||'—'}</span><em className={item.online?'online':'offline'}><i/>{item.online?'在线':'离线'}</em></div>)}</div></Panel><Panel title="关于" subtitle="Production Observability Console"><div className="aboutBox"><span className="bigLogo"><Activity/></span><div><h3>vLLM Sentinel <small>v1.1.0</small></h3><p>为高密度 GPU 推理服务器打造的实时可观测控制台。</p></div></div></Panel></div>
}

function Alerts({alerts,open,onClose}:{alerts:Snapshot['alerts'];open:boolean;onClose:()=>void}) {
  return <><div className={`drawerBackdrop ${open?'show':''}`} onClick={onClose}/><aside className={`alertDrawer ${open?'show':''}`}><div className="drawerHead"><div><span>事件中心</span><b>{alerts.length} 个活动事件</b></div><button onClick={onClose}><X/></button></div>{alerts.length?<div className="alertList">{alerts.map((alert,index)=><article className={alert.severity} key={index}><span>{alert.severity==='critical'?<AlertTriangle/>:<Info/>}</span><div><b>{alert.title}</b><p>{alert.detail}</p><small>刚刚</small></div></article>)}</div>:<div className="allClear"><span><Check/></span><h3>系统运行正常</h3><p>没有需要处理的告警，所有指标均在阈值范围内。</p></div>}</aside></>
}

export default function App() {
  const {snapshot,source}=useSentinel()
  const energy=useEnergy()
  const [page,setPage]=useState<Page>('dashboard')
  const [range,setRange]=useState<Range>('15m')
  const [history,setHistory]=useState<Point[]>([])
  const [theme,setThemeState]=useState<Theme>(()=>(localStorage.getItem('sentinel-theme') as Theme)||'midnight')
  const [hue,setHueState]=useState(()=>Number(localStorage.getItem('sentinel-hue')||228))
  const [collapsed,setCollapsed]=useState(false)
  const [menu,setMenu]=useState(false)
  const [alertsOpen,setAlertsOpen]=useState(false)
  const [clock,setClock]=useState(new Date())
  useEffect(()=>{const id=setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(id)},[])
  useEffect(()=>{document.documentElement.dataset.theme=theme;document.documentElement.style.setProperty('--hue',String(hue));localStorage.setItem('sentinel-theme',theme);localStorage.setItem('sentinel-hue',String(hue))},[theme,hue])
  useEffect(()=>{if(range==='15m'){setHistory([]);return}fetch(`/api/history?range=${range}`).then(r=>r.ok?r.json():Promise.reject()).then(body=>setHistory(body.points||[])).catch(()=>setHistory([]))},[range])
  const points=useMemo(()=>history.length?history:snapshot.realtime,[history,snapshot.realtime])
  const setTheme=(value:Theme)=>setThemeState(value), setHue=(value:number)=>setHueState(value)
  const [title,subtitle]=titles[page]
  const content=page==='dashboard'?<Dashboard data={snapshot} points={points} range={range} setRange={setRange} energy={energy}/>:page==='models'?<ModelsPage data={snapshot} points={points}/>:page==='gpus'?<GpusPage data={snapshot} points={points}/>:page==='host'?<HostPage data={snapshot} points={points}/>:page==='bmc'?<BmcPage data={snapshot} points={points}/>:<SettingsPage data={snapshot} theme={theme} setTheme={setTheme} hue={hue} setHue={setHue}/>
  return <div className={`app ${collapsed?'collapsed':''}`}>
    <aside className={`sidebar ${menu?'mobileOpen':''}`}><div className="brand"><span><Activity/></span><div>vLLM <b>Sentinel</b><small>COMMAND CENTER</small></div></div><nav>{nav.map(item=><button key={item.id} className={page===item.id?'active':''} onClick={()=>{setPage(item.id);setMenu(false)}} title={collapsed?item.label:undefined}><item.icon/><span><b>{item.label}</b><small>{item.hint}</small></span>{page===item.id&&<i/>}</button>)}</nav><div className="sideBottom"><button className={page==='settings'?'active':''} onClick={()=>setPage('settings')}><Settings2/><span><b>设置</b><small>主题与数据源</small></span></button><div className="nodeStatus"><i className={source==='live'?'':'demo'}/><span><b>{snapshot.host.hostname}</b><small>{source==='live'?'实时连接':'预览数据'}</small></span><em>{snapshot.gpu.count} GPU</em></div></div></aside>
    <main className="main"><header className="topbar"><button className="mobileMenu" onClick={()=>setMenu(!menu)}><Menu/></button><button className="collapseButton" onClick={()=>setCollapsed(!collapsed)}><PanelLeftClose/></button><div className="pageTitle"><span className="sectionEyebrow">{page==='dashboard'?'INFERENCE COMMAND CENTER':'VLLM SENTINEL'}</span><h1>{title}</h1><p>{subtitle}</p></div><div className="topActions"><div className="clock"><Clock3/><span><b>{clock.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</b><small>{clock.toLocaleDateString('zh-CN',{month:'short',day:'numeric',weekday:'short'})}</small></span></div><button className="iconButton" onClick={()=>setTheme(theme==='light'?'midnight':'light')} title="切换明暗主题">{theme==='light'?<Moon/>:<Sun/>}</button><button className="iconButton alertButton" onClick={()=>setAlertsOpen(true)} title="查看告警"><Bell/>{snapshot.alerts.length>0&&<i>{snapshot.alerts.length}</i>}</button><div className={`connection ${source}`}><i/><span><b>{source==='live'?'Live':'Preview'}</b><small>{source==='live'?`${snapshot.sample_interval}s 刷新`:'等待采集器'}</small></span></div></div></header>
    <div className="content">{content}<footer><span>vLLM Sentinel · read-only observability</span><span>Last sample {timeLabel(snapshot.timestamp)}</span></footer></div></main>
    <Alerts alerts={snapshot.alerts} open={alertsOpen} onClose={()=>setAlertsOpen(false)}/>
  </div>
}
