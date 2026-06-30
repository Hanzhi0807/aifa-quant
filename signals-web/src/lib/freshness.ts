/** Data freshness utilities. */

export interface FreshnessInfo {
  dataDate: string | null
  daysStale: number
  level: 'fresh' | 'warning' | 'expired'
  label: string
}

/** Compute freshness from a data date string (YYYY-MM-DD). */
export function computeFreshness(dataDate: string | null): FreshnessInfo {
  if (!dataDate) {
    return { dataDate: null, daysStale: Infinity, level: 'expired', label: '无数据' }
  }
  const date = new Date(dataDate)
  const now = new Date()
  const daysStale = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  let level: FreshnessInfo['level'] = 'fresh'
  let label = `${daysStale} 天前更新`
  if (daysStale > 7) {
    level = 'expired'
    label = `数据已过期 (${daysStale} 天)`
  } else if (daysStale > 3) {
    level = 'warning'
    label = `${daysStale} 天前更新`
  }
  return { dataDate, daysStale, level, label }
}

/** Next Monday from now, as a localized string. */
export function nextMonday(): string {
  const now = new Date()
  const day = now.getDay()
  const daysUntilMonday = (8 - day) % 7 || 7
  const monday = new Date(now)
  monday.setDate(now.getDate() + daysUntilMonday)
  return monday.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
}
