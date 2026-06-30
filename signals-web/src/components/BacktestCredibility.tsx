export interface CredibilityMetrics {
  backtest_method: 'rolling' | 'non-rolling'
  train_test_overlap_days: number
  pbo: number | null           // Probability of Backtest Overfitting
  oos_rank_ic: number | null   // out-of-sample RankIC
}

/** Credibility tag for the equity curve. */
export function BacktestCredibility(props: { metrics: CredibilityMetrics | null }): React.JSX.Element | null {
  const m = props.metrics
  if (!m) return null

  let level: 'green' | 'yellow' | 'red'
  let label: string
  let detail: string

  const pboBad = m.pbo !== null && m.pbo > 0.5
  const pboWarn = m.pbo !== null && m.pbo > 0.3
  const icBad = m.oos_rank_ic !== null && m.oos_rank_ic < 0.02
  const overlapBad = m.train_test_overlap_days > 0
  const nonRolling = m.backtest_method === 'non-rolling'

  if (pboBad || icBad) {
    level = 'red'
    label = '可信度低'
  } else if (pboWarn || overlapBad || nonRolling) {
    level = 'yellow'
    label = '可信度中等'
  } else {
    level = 'green'
    label = '可信度高'
  }

  detail = [
    `方法: ${m.backtest_method}`,
    m.pbo !== null ? `PBO: ${(m.pbo * 100).toFixed(0)}%` : null,
    m.oos_rank_ic !== null ? `OOS RankIC: ${m.oos_rank_ic.toFixed(4)}` : null,
    `训练/测试重叠: ${m.train_test_overlap_days} 天`,
  ].filter(Boolean).join(' · ')

  const color = level === 'green' ? 'text-green-400' : level === 'yellow' ? 'text-yellow-400' : 'text-red-400'
  const dot = level === 'green' ? '🟢' : level === 'yellow' ? '🟡' : '🔴'

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs ${color} px-2 py-1 rounded-full bg-white/5 cursor-help`}
      title={detail}
    >
      {dot} {label}
    </span>
  )
}
