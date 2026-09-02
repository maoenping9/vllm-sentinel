import type { Snapshot } from './types'

const now = Date.now() / 1000
const wave = (index:number, base:number, spread:number) => Math.max(0, base + Math.sin(index/5)*spread + Math.cos(index/11)*spread*.4)
const points = Array.from({length: 120}, (_, index) => ({
  ts: now - (119-index)*2,
  prompt_tps: wave(index, 3480, 640), generation_tps: wave(index+7, 186, 42),
  ttft_p95: wave(index+4, 812, 140), tpot_p95: wave(index, 10.8, 1.8),
  running: Math.round(wave(index, 9, 3)), waiting: Math.max(0, Math.round(wave(index+8, 2, 2))),
  kv_cache: wave(index, 67, 5), gpu: wave(index+2, 82, 9), gpu_memory: wave(index, 73, 1),
  cpu: wave(index+10, 36, 8), memory: wave(index, 10.4, .2), power: wave(index, 941, 80), bmc_power: wave(index, 1180, 110),
}))

const instance = {
  name:'Primary', url:'http://127.0.0.1:9003', online:true, error:'', models:['DeepSeek-V4-Flash-0731'],
  running:11, waiting:2, swapped:0, kv_cache_percent:68.4,
  prompt_tokens_total:98654211, generation_tokens_total:6384728, requests_total:48291,
  prompt_tokens_per_second:3675.7, generation_tokens_per_second:193.4, requests_per_second:2.8,
  prefix_cache_hit_percent:91.6, spec_accept_percent:36.8,
  ttft_p50_ms:318, ttft_p95_ms:847, ttft_p99_ms:1418,
  tpot_p50_ms:8.9, tpot_p95_ms:11.7, tpot_p99_ms:16.2, e2e_p95_ms:4980, queue_p95_ms:124,
}

export const mockSnapshot: Snapshot = {
  status:'demo', timestamp:now, sample_interval:2,
  host:{hostname:'zakk',os:'Ubuntu 22.04.5 LTS',uptime:142081,
    cpu:{model:'Intel Xeon E5-2690 v4 · Dual Socket',cores:28,threads:56,usage:38.6,per_core:Array.from({length:56},(_,i)=>wave(i,36,24)),frequency_mhz:2794,load:[7.21,6.84,6.09]},
    memory:{total:134923419648,used:14388140442,available:120535279206,percent:10.7,swap_total:8589934592,swap_used:1048576},
    disk:{total:242311675904,used:76829310976,percent:31.7,read_bps:8243021,write_bps:1940212},
    network:{rx_bps:12784123,tx_bps:3892431}},
  gpu:{count:8,utilization:82.3,memory_total_mb:524288,memory_used_mb:383104,memory_percent:73.1,power_w:941,max_temperature:67,
    items:Array.from({length:8},(_,i)=>({index:i,uuid:`GPU-${i}`,name:'NVIDIA CMP 170HX',utilization:Math.min(99,72+i*3+(i%2)*5),memory_utilization:55+i*2,memory_total_mb:65536,memory_used_mb:47400+i*190,memory_free_mb:18136-i*190,memory_percent:72.3+i*.3,temperature:58+i,power_w:108+i*3,power_limit_w:250,fan_percent:42+i*2,clock_sm_mhz:1185+i*15,clock_memory_mhz:1593,pstate:'P0',processes:[{pid:21843,name:'VLLM::Worker',memory_mb:46832+i*190}]}))},
  bmc:{online:true,stale:false,timestamp:now,error:'',info:{manufacturer_name:'Supermicro',firmware_revision:'3.86',ipmi_version:'2.0',device_available:'yes'},power:{instant_w:1180,minimum_w:12,maximum_w:1628,average_w:1153,sampling_seconds:167195,state:'activated'},
    temperatures:[['CPU1 Temp',42],['CPU2 Temp',39],['PCH Temp',48],['System Temp',39],['Peripheral Temp',36],['Vcpu1VRM Temp',44],['Vcpu2VRM Temp',43],['VmemABVRM Temp',39],['VmemCDVRM Temp',41],['P1-DIMMA1 Temp',34],['P2-DIMME1 Temp',35]].map(([name,value])=>({name:String(name),value:Number(value),units:'degrees C',status:'ok',upper_warning:80,upper_critical:85})),
    fans:Array.from({length:8},(_,i)=>({name:`FAN${i+1}`,value:i%3===1?4700:4600,units:'RPM',status:'ok',lower_critical:500,upper_critical:25400})),
    voltages:[['12V',11.937],['5VCC',5.13],['3.3VCC',3.401],['VBAT',3.045],['Vcpu1',1.809],['Vcpu2',1.809]].map(([name,value])=>({name:String(name),value:Number(value),units:'Volts',status:'ok'})),
    discrete:[],psus:[{name:'PS3 Status',status:'ok',detail:'Presence detected'},{name:'PS4 Status',status:'ok',detail:'Presence detected'}]},
  vllm:{instances:[instance],aggregate:{...instance,online_instances:1,total_instances:1}},
  alerts:[], realtime:points,
}
