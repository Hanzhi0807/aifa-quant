import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { ErrorBoundary } from './ErrorBoundary'

interface NavRow {
  profile: string
  trade_date: string
  total_value: number
}

const PROFILES = ['aggressive', 'balanced', 'conservative', 'growth', 'value']
const COLORS: Record<string, string> = {
  aggressive: '#ef4444',
  balanced: '#06b6d4',
  conservative: '#10b981',
  growth: '#f59e0b',
  value: '#8b5cf6',
}

/** 5-profile comparison page: equity curves + metrics + overlap. */
export function ProfileCompare(): React.JSX.Element {
  const [navByProfile, setNavByProfile] = useState<Record<string, NavRow[]>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void (async () => {
      setLoading(true)
      const result: Record<string, NavRow[]> = {}
      for (const p of PROFILES) {
        const { data, error } = await supabase
          .from('paper_nav')
          .select('profile, trade_date, total_value')
          .eq('profile', p)
          .order('trade_date', { ascending: true })
        if (!error && data) result[p] = data as NavRow[]
      }
      setNavByProfile(result)
      setLoading(false)
    })()
  }, [])

  if (loading) return <div className="text-[var(--text-muted)]">加载中...</div>

  // Compute metrics per profile.
  const metrics = PROFILES.map((p) => {
    const nav = navByProfile[p] ?? []
    if (nav.length < 2) return { profile: p, cum: 0, annual: 0, sharpe: 0, maxDD: 0, n: nav.length }
    const vals = nav.map((r) => r.total_value)
    const rets: number[] = []
    for (let i = 1; i < vals.length; i++) rets.push((vals[i] - vals[i - 1]) / vals[i - 1])
    const cum = vals[vals.length - 1] / vals[0] - 1
    const years = vals.length / 252
    const annual = years > 0 ? Math.pow(1 + cum, 1 / years) - 1 : 0
    const mean = rets.reduce((s, r) => s + r, 0) / (rets.length || 1)
    const std = Math.sqrt(rets.reduce((s, r) => s + (r - mean) ** 2, 0) / (rets.length || 1)) || 1e-9
    const sharpe = (mean / std) * Math.sqrt(252)
    let peak = vals[0]
    let maxDD = 0
    for (const v of vals) {
      peak = Math.max(peak, v)
      maxDD = Math.min(maxDD, (v - peak) / peak)
    }
    return { profile: p, cum, annual, sharpe, maxDD, n: vals.length }
  })

  // Chart ranges
  const allValues = Object.values(navByProfile).flat().map((r) => r.total_value)
  const minV = Math.min(...allValues)
  const maxV = Math.max(...allValues)
  const allDates = (navByProfile['balanced'] ?? []).map((r) => r.trade_date)
  const width = 700
  const height = 240

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <div className="text-white text-xl font-bold">Profile 横向对比</div>

        {/* Equity curve overlay */}
        <div className="glass-card p-5">
          <div className="text-white font-medium mb-3">净值曲线叠加</div>
          {allDates.length < 2 ? (
            <div className="text-[var(--text-muted)] text-sm">数据不足，需多 profile 持续运行后对比。</div>
          ) : (
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
              {PROFILES.map((p) => {
                const nav = navByProfile[p] ?? []
                if (nav.length < 2) return null
                const pts = nav.map((r, i) => {
                  const x = (i / (nav.length - 1)) * width
                  const y = height - ((r.total_value - minV) / (maxV - minV || 1)) * height
                  return `${x.toFixed(1)},${y.toFixed(1)}`
                }).join(' ')
                return <polyline key={p} points={pts} fill="none" stroke={COLORS[p]} strokeWidth={1.5} />
              })}
            </svg>
          )}
          <div className="flex gap-3 mt-2 text-xs">
            {PROFILES.map((p) => (
              <span key={p} className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5" style={{ background: COLORS[p] }} />
                <span className="text-[var(--text-muted)]">{p}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Metrics table */}
        <div className="glass-card p-5 overflow-x-auto">
          <div className="text-white font-medium mb-3">指标对比</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--text-muted)] text-xs border-b border-white/5">
                <th className="text-left py-2 px-2">Profile</th>
                <th className="text-right py-2 px-2">累计收益</th>
                <th className="text-right py-2 px-2">年化收益</th>
                <th className="text-right py-2 px-2">Sharpe</th>
                <th className="text-right py-2 px-2">最大回撤</th>
                <th className="text-right py-2 px-2">数据天数</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={m.profile} className="border-b border-white/5">
                  <td className="py-2 px-2">
                    <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: COLORS[m.profile] }} />
                    <span className="text-white">{m.profile}</span>
                  </td>
                  <td className={`text-right py-2 px-2 ${m.cum >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(m.cum * 100).toFixed(1)}%
                  </td>
                  <td className={`text-right py-2 px-2 ${m.annual >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(m.annual * 100).toFixed(1)}%
                  </td>
                  <td className="text-right py-2 px-2 text-white">{m.sharpe.toFixed(2)}</td>
                  <td className="text-right py-2 px-2 text-red-400">{(m.maxDD * 100).toFixed(1)}%</td>
                  <td className="text-right py-2 px-2 text-[var(--text-muted)]">{m.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </ErrorBoundary>
  )
}
