export interface Point {
  ts: number
  prompt_tps: number
  generation_tps: number
  ttft_p95: number
  tpot_p95: number
  running: number
  waiting: number
  kv_cache: number
  gpu: number
  gpu_memory: number
  cpu: number
  memory: number
  power: number
  bmc_power: number
  disk: number
  net: number
}

export interface BmcSensor {
  name: string
  value: number | null
  units: string
  status: string
  lower_non_recoverable?: number | null
  lower_critical?: number | null
  lower_warning?: number | null
  upper_warning?: number | null
  upper_critical?: number | null
  upper_non_recoverable?: number | null
}

export interface BmcState {
  online: boolean
  stale: boolean
  timestamp: number
  error: string
  info: Record<string,string>
  power: {instant_w:number; minimum_w:number; maximum_w:number; average_w:number; sampling_seconds:number; state:string}
  temperatures: BmcSensor[]
  fans: BmcSensor[]
  voltages: BmcSensor[]
  discrete: BmcSensor[]
  psus: Array<{name:string; status:string; detail:string}>
}

export interface GpuItem {
  index: number
  uuid: string
  name: string
  service?: string
  utilization: number
  memory_utilization: number
  memory_total_mb: number
  memory_used_mb: number
  memory_free_mb: number
  memory_percent: number
  temperature: number
  power_w: number
  power_limit_w: number
  fan_percent: number
  fan_pwm?: number
  fan_rpm?: number
  clock_sm_mhz: number
  clock_memory_mhz: number
  pstate: string
  processes: Array<{pid:number; name:string; memory_mb:number}>
}

export interface VllmInstance {
  name: string
  url: string
  online: boolean
  error: string
  models: string[]
  gpus?: number[]
  running: number
  waiting: number
  swapped: number
  kv_cache_percent: number
  prompt_tokens_total: number
  generation_tokens_total: number
  requests_total: number
  prompt_tokens_per_second: number
  generation_tokens_per_second: number
  requests_per_second: number
  prefix_cache_hit_percent: number
  spec_accept_percent: number
  ttft_p50_ms: number
  ttft_p95_ms: number
  ttft_p99_ms: number
  tpot_p50_ms: number
  tpot_p95_ms: number
  tpot_p99_ms: number
  e2e_p95_ms: number
  queue_p95_ms: number
}

export interface Snapshot {
  status: string
  timestamp: number
  sample_interval: number
  host: {
    hostname: string
    os: string
    uptime: number
    cpu: {model:string; cores:number; threads:number; usage:number; per_core:number[]; frequency_mhz:number; load:number[]}
    memory: {total:number; used:number; available:number; percent:number; swap_total:number; swap_used:number}
    disk: {total:number; used:number; percent:number; read_bps:number; write_bps:number}
    network: {rx_bps:number; tx_bps:number}
  }
  gpu: {count:number; items:GpuItem[]; utilization:number; memory_total_mb:number; memory_used_mb:number; memory_percent:number; power_w:number; max_temperature:number}
  gpu_map?: Array<{service:string; gpus:number[]; port?:number}>
  small_models?: Array<{name:string; port?:number}>
  bmc: BmcState
  vllm: {
    instances: VllmInstance[]
    aggregate: VllmInstance & {online_instances:number; total_instances:number}
  }
  alerts: Array<{severity:'warning'|'critical'|'info'; title:string; detail:string}>
  realtime: Point[]
}
