export const compact = (value:number, digits=1) => new Intl.NumberFormat('zh-CN',{notation:'compact',maximumFractionDigits:digits}).format(value || 0)
export const number = (value:number, digits=1) => new Intl.NumberFormat('zh-CN',{maximumFractionDigits:digits}).format(value || 0)
export const bytes = (value:number) => {
  if (!value) return '0 B'
  const units = ['B','KB','MB','GB','TB']
  const index = Math.min(units.length-1, Math.floor(Math.log(value)/Math.log(1024)))
  return `${number(value/1024**index,index > 2 ? 2 : 1)} ${units[index]}`
}
export const duration = (seconds:number) => {
  const days=Math.floor(seconds/86400), hours=Math.floor(seconds%86400/3600), mins=Math.floor(seconds%3600/60)
  return days ? `${days}天 ${hours}小时` : hours ? `${hours}小时 ${mins}分` : `${mins}分钟`
}
export const timeLabel = (ts:number) => new Date(ts*1000).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})
