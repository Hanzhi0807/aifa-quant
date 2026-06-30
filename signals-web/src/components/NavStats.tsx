export interface NavStat {
  cumulative_return: number
  annual_return: number
  max_drawdown: number
  sharpe: number
}

/** 4-stat panel for cumulative / annual / drawdown / Sharpe. */
export function NavStats(props: { stat: NavStat | null }): React.JSX.Element {
  const s = props.stat
  const cards = [
    { label: '累计收益', value: s ? `${(s.cumulative_return * 100).toFixed(1)}%` : '-', positive: (s?.cumulative_return ?? 0) >= 0 },
    { label: '年化收益', value: s ? `${(s.annual_return * 100).toFixed(1)}%` : '-', positive: (s?.annual_return ?? 0) >= 0 },
    { label: '最大回撤', value: s ? `${(s.max_drawdown * 100).toFixed(1)}%` : '-', positive: false },
    { label: 'Sharpe', value: s ? s.sharpe.toFixed(2) : '-', positive: (s?.sharpe ?? 0) >= 0 },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((c) => (
        <div key={c.label} className="glass-card p-3 text-center">
          <div className="text-xs text-[var(--text-muted)] mb-1">{c.label}</div>
          <div className={c.label === '最大回撤' ? 'text-red-400 text-lg font-medium' : c.positive ? 'text-green-400 text-lg font-medium' : 'text-red-400 text-lg font-medium'}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  )
}
