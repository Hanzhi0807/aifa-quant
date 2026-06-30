import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { featureLabel, featureDesc } from '../lib/feature_names'
import { ErrorBoundary } from './ErrorBoundary'

interface ShapRow {
  feature: string
  shap_value: number
}

interface StockInfo {
  symbol: string
  name: string
  close: number
  model_score: number
  held: boolean
  industry: string | null
  avg_amount_20d: number | null
}

/** Individual stock detail page with SHAP waterfall + plain-language summary. */
export function StockDetail(): React.JSX.Element {
  const { symbol = '' } = useParams()
  const [info, setInfo] = useState<StockInfo | null>(null)
  const [shap, setShap] = useState<ShapRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    void (async () => {
      setLoading(true)
      setError('')
      try {
        const [infoRes, shapRes] = await Promise.all([
          supabase.from('daily_signals').select('symbol, name, score, trade_date').eq('symbol', symbol).order('trade_date', { ascending: false }).limit(1).maybeSingle(),
          supabase.from('stock_shap').select('feature, shap_value').eq('symbol', symbol).order('shap_value', { ascending: false }),
        ])
        if (infoRes.error) throw new Error(infoRes.error.message)
        if (infoRes.data) {
          setInfo({
            symbol: infoRes.data.symbol,
            name: infoRes.data.name,
            close: 0, // filled by quotes if available
            model_score: infoRes.data.score ?? 0,
            held: false,
            industry: null,
            avg_amount_20d: null,
          })
        }
        if (shapRes.error) throw new Error(shapRes.error.message)
        setShap((shapRes.data ?? []) as ShapRow[])
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败')
      } finally {
        setLoading(false)
      }
    })()
  }, [symbol])

  if (loading) return <div className="text-[var(--text-muted)]">加载中...</div>
  if (error) return <div className="glass-card p-6 text-red-400">加载失败：{error}</div>

  const top = shap.slice(0, 8)
  const posTop = top.filter((r) => r.shap_value > 0).slice(0, 3)
  const negTop = top.filter((r) => r.shap_value < 0).slice(0, 2)

  // Plain-language summary
  const summaryParts: string[] = []
  if (posTop.length) {
    summaryParts.push('入选主因：' + posTop.map((r) => `${featureLabel(r.feature)}(${r.shap_value >= 0 ? '+' : ''}${r.shap_value.toFixed(2)})`).join('、'))
  }
  if (negTop.length) {
    summaryParts.push('潜在风险：' + negTop.map((r) => `${featureLabel(r.feature)}(${r.shap_value.toFixed(2)})`).join('、'))
  }
  const summary = summaryParts.join('；') || '暂无解释数据'

  // Waterfall: base value → cumulative
  const baseValue = 0.5
  const cumValues: number[] = []
  let acc = baseValue
  for (const r of top) {
    acc += r.shap_value
    cumValues.push(acc)
  }

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="text-[var(--text-muted)] hover:text-white text-sm">← 返回</Link>
        </div>

        {/* Header card */}
        <div className="glass-card p-5">
          <div className="flex justify-between items-start">
            <div>
              <div className="text-2xl font-bold text-white">{symbol}</div>
              <div className="text-[var(--text-muted)] text-sm">{info?.name ?? ''}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-[var(--text-muted)]">模型评分</div>
              <div className="text-xl text-[var(--cyan)]">{info?.model_score.toFixed(3) ?? '-'}</div>
            </div>
          </div>
          <div className="flex gap-4 mt-3 text-xs text-[var(--text-muted)]">
            <span>行业：{info?.industry ?? '-'}</span>
            <span>20日均成交：{info?.avg_amount_20d ? `${(info.avg_amount_20d / 1e4).toFixed(0)} 万` : '-'}</span>
            <span>持仓状态：{info?.held ? '已持有' : '未持有'}</span>
          </div>
        </div>

        {/* SHAP waterfall + summary */}
        <div className="glass-card p-5">
          <div className="text-white font-medium mb-1">模型解释 (SHAP 瀑布图)</div>
          <div className="text-sm text-[var(--text-muted)] mb-4">{summary}</div>

          {top.length === 0 ? (
            <div className="text-[var(--text-muted)] text-sm">该股暂无 SHAP 数据，模型数据通常每周一更新。</div>
          ) : (
            <div className="space-y-1.5">
              {/* Base value */}
              <div className="flex items-center gap-2 text-xs">
                <span className="w-32 text-[var(--text-muted)]">基准值</span>
                <div className="flex-1 h-4 bg-white/5 rounded relative">
                  <div className="absolute left-0 top-0 h-full bg-white/20 rounded" style={{ width: `${baseValue * 100}%` }} />
                </div>
                <span className="w-14 text-right text-white">{baseValue.toFixed(2)}</span>
              </div>
              {top.map((r, i) => {
                const prev = i === 0 ? baseValue : cumValues[i - 1]
                const cur = cumValues[i]
                const lo = Math.min(prev, cur)
                const hi = Math.max(prev, cur)
                const positive = r.shap_value > 0
                return (
                  <div key={r.feature} className="flex items-center gap-2 text-xs">
                    <span className="w-32 text-[var(--text-muted)] truncate" title={featureDesc(r.feature)}>
                      {featureLabel(r.feature)}
                    </span>
                    <div className="flex-1 h-4 bg-white/5 rounded relative">
                      <div
                        className={positive ? 'absolute h-full bg-red-400/70' : 'absolute h-full bg-green-400/70'}
                        style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }}
                      />
                    </div>
                    <span className={`w-14 text-right ${positive ? 'text-red-400' : 'text-green-400'}`}>
                      {r.shap_value >= 0 ? '+' : ''}{r.shap_value.toFixed(2)}
                    </span>
                  </div>
                )
              })}
              {/* Final prediction */}
              <div className="flex items-center gap-2 text-xs pt-1">
                <span className="w-32 text-white font-medium">最终预测</span>
                <div className="flex-1 h-4 bg-white/5 rounded relative">
                  <div className="absolute left-0 top-0 h-full bg-[var(--cyan)] rounded" style={{ width: `${Math.min(cumValues[cumValues.length - 1] * 100, 100)}%` }} />
                </div>
                <span className="w-14 text-right text-white font-medium">
                  {cumValues[cumValues.length - 1].toFixed(2)}
                </span>
              </div>
            </div>
          )}
          <div className="text-xs text-[var(--text-muted)] mt-3">
            红色 = 正贡献（推高预测），绿色 = 负贡献（压低预测）
          </div>
        </div>
      </div>
    </ErrorBoundary>
  )
}
