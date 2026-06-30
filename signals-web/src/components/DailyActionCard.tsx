import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { computeFreshness } from '../lib/freshness'

export interface ActionRow {
  symbol: string
  name: string
  action: 'buy' | 'sell' | 'hold'
  target_weight: number
  current_weight: number
  model_score: number
  executable: boolean
  block_reason: string | null
  reason: string
}

interface Props {
  tradeDate: string
  lastPush: string | null
  modelVersion: string | null
  profile: string
  marketState: string | null
  nav: number
  dailyChange: number
  cumChange: number
  rows: ActionRow[]
}

/** Top-of-dashboard action card: "what to buy / sell / hold today". */
export function DailyActionCard(props: Props): React.JSX.Element {
  const fresh = computeFreshness(props.tradeDate)
  const buyCount = props.rows.filter((r) => r.action === 'buy').length
  const sellCount = props.rows.filter((r) => r.action === 'sell').length
  const holdCount = props.rows.filter((r) => r.action === 'hold').length

  const executableRows = props.rows.filter((r) => r.executable)
  const blockedRows = props.rows.filter((r) => !r.executable)
  const targetTurnover = props.rows.reduce((s, r) => s + Math.abs(r.target_weight - r.current_weight), 0) / 2
  const execTurnover = executableRows.reduce((s, r) => s + Math.abs(r.target_weight - r.current_weight), 0) / 2

  const downloadCSV = (): void => {
    const header = 'symbol,name,action,target_weight,current_weight,model_score,executable,block_reason\n'
    const body = props.rows.map((r) =>
      [r.symbol, r.name, r.action, r.target_weight.toFixed(4), r.current_weight.toFixed(4),
       r.model_score.toFixed(4), r.executable, r.block_reason ?? ''].join(',')
    ).join('\n')
    const blob = new Blob([header + body], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `orders_${props.profile}_${props.tradeDate}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const freshColor = fresh.level === 'fresh' ? 'var(--cyan)' : fresh.level === 'warning' ? '#fbbf24' : '#ef4444'

  return (
    <div className="glass-card p-5 mb-6">
      {/* Status bar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-muted)] mb-4">
        <span>信号日期 <span className="text-white">{props.tradeDate}</span></span>
        <span style={{ color: freshColor }}>● {fresh.label}</span>
        {props.modelVersion && <span>模型 <span className="text-white">{props.modelVersion}</span></span>}
        <span>当前 profile <span className="text-[var(--cyan)]">{props.profile}</span></span>
        {props.marketState && <span>市场状态 <span className="text-white">{props.marketState}</span></span>}
      </div>

      {/* NAV + action badges */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-4">
        <div>
          <div className="text-3xl font-bold text-white">
            {props.nav.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
          </div>
          <div className="text-sm mt-1">
            <span className={props.dailyChange >= 0 ? 'text-green-400' : 'text-red-400'}>
              {props.dailyChange >= 0 ? '+' : ''}{(props.dailyChange * 100).toFixed(2)}%
            </span>
            <span className="text-[var(--text-muted)] mx-2">当日</span>
            <span className={props.cumChange >= 0 ? 'text-green-400' : 'text-red-400'}>
              {props.cumChange >= 0 ? '+' : ''}{(props.cumChange * 100).toFixed(2)}%
            </span>
            <span className="text-[var(--text-muted)] mx-2">累计</span>
          </div>
        </div>
        <div className="flex gap-2 text-sm">
          <span className="px-3 py-1 rounded-full bg-green-500/15 text-green-400">🟢 买入 {buyCount}</span>
          <span className="px-3 py-1 rounded-full bg-red-500/15 text-red-400">🔴 卖出 {sellCount}</span>
          <span className="px-3 py-1 rounded-full bg-white/10 text-white/70">⚪ 持有 {holdCount}</span>
        </div>
      </div>

      {/* Turnover summary */}
      <div className="text-xs text-[var(--text-muted)] mb-3">
        今日目标换手 {(targetTurnover * 100).toFixed(1)}% · 可执行换手 {(execTurnover * 100).toFixed(1)}%
        {blockedRows.length > 0 && (
          <span className="text-yellow-400 ml-2">（{blockedRows.length} 只受限）</span>
        )}
      </div>

      {/* Action table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[var(--text-muted)] text-xs border-b border-white/5">
              <th className="text-left py-2 px-2">动作</th>
              <th className="text-left py-2 px-2">代码/名称</th>
              <th className="text-right py-2 px-2">目标权重</th>
              <th className="text-right py-2 px-2">当前权重</th>
              <th className="text-right py-2 px-2">模型分</th>
              <th className="text-center py-2 px-2">可执行</th>
              <th className="text-left py-2 px-2">原因</th>
            </tr>
          </thead>
          <tbody>
            {props.rows.slice(0, 10).map((r) => (
              <tr key={r.symbol} className="border-b border-white/5 hover:bg-white/5">
                <td className="py-2 px-2">
                  <span className={
                    r.action === 'buy' ? 'text-green-400' : r.action === 'sell' ? 'text-red-400' : 'text-white/50'
                  }>{r.action === 'buy' ? '买' : r.action === 'sell' ? '卖' : '持'}</span>
                </td>
                <td className="py-2 px-2">
                  <Link to={`/stock/${r.symbol}`} className="text-white hover:text-[var(--cyan)]">
                    {r.symbol}
                  </Link>
                  <span className="text-[var(--text-muted)] ml-2 text-xs">{r.name}</span>
                </td>
                <td className="text-right py-2 px-2 text-white">{(r.target_weight * 100).toFixed(1)}%</td>
                <td className="text-right py-2 px-2 text-[var(--text-muted)]">{(r.current_weight * 100).toFixed(1)}%</td>
                <td className="text-right py-2 px-2 text-white">{r.model_score.toFixed(3)}</td>
                <td className="text-center py-2 px-2">
                  {r.executable ? (
                    <span className="text-green-400">✅</span>
                  ) : (
                    <span className="text-yellow-400" title={r.block_reason ?? ''}>⚠️</span>
                  )}
                </td>
                <td className="py-2 px-2 text-[var(--text-muted)] text-xs">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center mt-4">
        <Link to="/compare" className="text-xs text-[var(--cyan)] hover:underline">查看完整持仓 →</Link>
        <button
          onClick={downloadCSV}
          className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs border border-white/10"
        >
          下载委托单 CSV
        </button>
      </div>
    </div>
  )
}
