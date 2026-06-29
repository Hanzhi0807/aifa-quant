import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

interface ShapRow {
  feature: string
  mean_abs_shap: number
  model_date: string
}

export function ShapView() {
  const [data, setData] = useState<ShapRow[]>([])
  const [loading, setLoading] = useState(true)
  const [modelDate, setModelDate] = useState('')

  useEffect(() => {
    loadShap()
  }, [])

  const loadShap = async () => {
    setLoading(true)
    const { data: latest } = await supabase
      .from('shap_summary')
      .select('model_date')
      .order('model_date', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (!latest) {
      setData([])
      setLoading(false)
      return
    }

    const { data: rows } = await supabase
      .from('shap_summary')
      .select('feature, mean_abs_shap, model_date')
      .eq('model_date', latest.model_date)
      .order('mean_abs_shap', { ascending: false })
      .limit(20)

    setData(rows ?? [])
    setModelDate(latest.model_date)
    setLoading(false)
  }

  if (loading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-10 text-center space-y-3">
        <svg className="w-12 h-12 mx-auto text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p className="text-[var(--text-secondary)]">暂无 SHAP 数据</p>
        <p className="text-xs text-[var(--text-muted)]">
          运行{' '}
          <code className="px-1.5 py-0.5 bg-white/5 rounded text-[var(--cyan)]">
            aifa explain
          </code>{' '}
          生成模型可解释性分析
        </p>
      </div>
    )
  }

  const maxVal = data[0]?.mean_abs_shap || 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">SHAP 特征重要性</h2>
          <p className="text-sm text-[var(--text-muted)] mt-0.5">
            Top 20 特征的平均 |SHAP value|，数值越大对模型预测影响越大
          </p>
        </div>
        <span className="text-xs text-[var(--text-muted)]">模型日期：{modelDate}</span>
      </div>

      <div className="glass-card rounded-2xl p-5 space-y-2">
        {data.map((row) => {
          const pct = (row.mean_abs_shap / maxVal) * 100
          return (
            <div key={row.feature} className="flex items-center gap-3">
              <span className="text-xs text-[var(--text-secondary)] w-[180px] truncate text-right flex-shrink-0">
                {row.feature}
              </span>
              <div className="flex-1 h-5 bg-white/[0.03] rounded overflow-hidden">
                <div
                  className="h-full rounded"
                  style={{
                    width: `${pct}%`,
                    background: 'linear-gradient(90deg, #a855f7, #7c3aed)',
                  }}
                />
              </div>
              <span className="text-xs font-mono text-[var(--text-muted)] w-[60px] text-right flex-shrink-0">
                {row.mean_abs_shap.toFixed(4)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
