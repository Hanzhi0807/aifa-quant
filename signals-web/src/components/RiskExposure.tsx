import { useMemo } from 'react'

export interface RiskMetrics {
  industry_concentration: Record<string, number>  // industry -> weight
  market_cap_quantile: { small: number; mid: number; large: number }
  beta: number
  style_exposures: { momentum: number; value: number; quality: number; low_vol: number }
  industry_cap_breach: boolean
  industry_cap_threshold: number
}

/** Portfolio risk attribution panel. */
export function RiskExposure(props: { metrics: RiskMetrics | null }): React.JSX.Element {
  const m = props.metrics
  if (!m) {
    return (
      <div className="glass-card p-5">
        <div className="text-white font-medium mb-1">组合风险归因</div>
        <div className="text-[var(--text-muted)] text-sm">风险数据生成中，通常每周一更新。</div>
      </div>
    )
  }

  const industries = Object.entries(m.industry_concentration).sort((a, b) => b[1] - a[1])
  const maxInd = industries[0]?.[1] ?? 0
  const styleAxes = [
    { key: 'momentum', label: '动量', value: m.style_exposures.momentum },
    { key: 'value', label: '价值', value: m.style_exposures.value },
    { key: 'quality', label: '质量', value: m.style_exposures.quality },
    { key: 'low_vol', label: '低波', value: m.style_exposures.low_vol },
  ] as const

  return (
    <div className="glass-card p-5">
      <div className="flex justify-between items-center mb-4">
        <div className="text-white font-medium">组合风险归因</div>
        <span className={
          m.industry_cap_breach ? 'text-red-400 text-xs' : 'text-green-400 text-xs'
        }>
          {m.industry_cap_breach ? '● 行业超限' : '● 风险可控'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Industry concentration */}
        <div>
          <div className="text-xs text-[var(--text-muted)] mb-2">行业集中度 (上限 {(m.industry_cap_threshold * 100).toFixed(0)}%)</div>
          <div className="space-y-1">
            {industries.slice(0, 6).map(([ind, w]) => (
              <div key={ind} className="flex items-center gap-2 text-xs">
                <span className="w-16 text-[var(--text-muted)] truncate">{ind}</span>
                <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className={w > m.industry_cap_threshold ? 'h-full bg-red-400' : 'h-full bg-[var(--cyan)]'}
                    style={{ width: `${Math.min(w * 100, 100)}%` }}
                  />
                </div>
                <span className="w-10 text-right text-white">{(w * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Market cap + beta */}
        <div>
          <div className="text-xs text-[var(--text-muted)] mb-2">市值分布 / Beta</div>
          <div className="flex gap-2 mb-3 text-xs">
            <div className="flex-1 p-2 bg-white/5 rounded text-center">
              <div className="text-[var(--text-muted)]">小盘</div>
              <div className="text-white">{(m.market_cap_quantile.small * 100).toFixed(0)}%</div>
            </div>
            <div className="flex-1 p-2 bg-white/5 rounded text-center">
              <div className="text-[var(--text-muted)]">中盘</div>
              <div className="text-white">{(m.market_cap_quantile.mid * 100).toFixed(0)}%</div>
            </div>
            <div className="flex-1 p-2 bg-white/5 rounded text-center">
              <div className="text-[var(--text-muted)]">大盘</div>
              <div className="text-white">{(m.market_cap_quantile.large * 100).toFixed(0)}%</div>
            </div>
            <div className="flex-1 p-2 bg-white/5 rounded text-center">
              <div className="text-[var(--text-muted)]">Beta</div>
              <div className="text-white">{m.beta.toFixed(2)}</div>
            </div>
          </div>
          {/* Style radar (simplified as bars) */}
          <div className="text-xs text-[var(--text-muted)] mb-1">风格暴露</div>
          <div className="space-y-1">
            {styleAxes.map((a) => (
              <div key={a.key} className="flex items-center gap-2 text-xs">
                <span className="w-10 text-[var(--text-muted)]">{a.label}</span>
                <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden relative">
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/20" />
                  <div
                    className={a.value >= 0 ? 'h-full bg-[var(--cyan)]' : 'h-full bg-yellow-400'}
                    style={{
                      width: `${Math.min(Math.abs(a.value) * 50, 50)}%`,
                      marginLeft: a.value >= 0 ? '50%' : `${50 - Math.min(Math.abs(a.value) * 50, 50)}%`,
                    }}
                  />
                </div>
                <span className="w-10 text-right text-white">{a.value.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
