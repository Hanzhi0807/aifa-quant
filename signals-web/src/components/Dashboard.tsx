import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import type { User } from '@supabase/supabase-js'

interface Signal {
  symbol: string
  name: string
  score: number
  rank: number
  trade_date: string
  profile: string
}

interface Position {
  symbol: string
  name: string
  action: string
  weight: number
  reason: string
  trade_date: string
  profile: string
}

const PROFILES = [
  { id: 'aggressive', name: '激进型', desc: 'Top5 追动量' },
  { id: 'balanced', name: '均衡型', desc: 'Top8 纯模型' },
  { id: 'conservative', name: '稳健型', desc: 'Top12 低波动' },
  { id: 'value', name: '价值型', desc: 'Top8 低估值' },
  { id: 'growth', name: '成长型', desc: 'Top6 高成长' },
]

export function Dashboard({ user }: { user: User }) {
  const [signals, setSignals] = useState<Signal[]>([])
  const [portfolio, setPortfolio] = useState<Position[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [signalDate, setSignalDate] = useState('')
  const [activeProfile, setActiveProfile] = useState('balanced')

  useEffect(() => {
    loadData(activeProfile)
  }, [activeProfile])

  const loadData = async (profile: string) => {
    setLoading(true)
    setError('')

    const latestRes = await supabase
      .from('daily_signals')
      .select('trade_date')
      .eq('profile', profile)
      .order('trade_date', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (latestRes.error) {
      setError(latestRes.error.message)
      setSignals([])
      setPortfolio([])
      setSignalDate('')
      setLoading(false)
      return
    }

    const latestDate = latestRes.data?.trade_date
    if (!latestDate) {
      setSignals([])
      setPortfolio([])
      setSignalDate('')
      setLoading(false)
      return
    }

    const [signalsRes, portfolioRes] = await Promise.all([
      supabase
        .from('daily_signals')
        .select('*')
        .eq('profile', profile)
        .eq('trade_date', latestDate)
        .order('rank', { ascending: true })
        .limit(50),
      supabase
        .from('portfolio')
        .select('*')
        .eq('profile', profile)
        .eq('trade_date', latestDate)
        .order('weight', { ascending: false })
        .limit(20),
    ])

    if (signalsRes.error || portfolioRes.error) {
      setError(signalsRes.error?.message || portfolioRes.error?.message || '加载失败')
      setSignals([])
      setPortfolio([])
      setSignalDate(latestDate)
      setLoading(false)
      return
    }

    setSignals(signalsRes.data ?? [])
    setPortfolio(portfolioRes.data ?? [])
    setSignalDate(latestDate)
    setLoading(false)
  }
  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold">AIFA Quant</h1>
          <p className="text-slate-400 text-sm">信号日期: {signalDate || '暂无数据'}</p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-slate-400 text-sm">{user.email}</span>
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm transition"
          >
            退出
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Profile Selector */}
      <div className="mb-6 flex flex-wrap gap-2">
        {PROFILES.map((p) => (
          <button
            key={p.id}
            onClick={() => setActiveProfile(p.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeProfile === p.id
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
            }`}
            title={p.desc}
          >
            {p.name}
          </button>
        ))}
      </div>

      {/* Portfolio Section */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-green-400 rounded-full"></span>
          今日持仓推荐
        </h2>
        {portfolio.length === 0 ? (
          <div className="bg-slate-800 rounded-xl p-8 text-center text-slate-400">
            暂无持仓推荐数据，请等待每日信号更新
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {portfolio.map((p) => (
              <div key={p.symbol} className="bg-slate-800 rounded-xl p-4 border border-slate-700">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-mono font-bold text-lg">{p.symbol}</span>
                    {p.name && <span className="text-slate-400 text-sm ml-2">{p.name}</span>}
                  </div>
                  <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs font-medium">
                    {p.action.toUpperCase()}
                  </span>
                </div>
                <div className="text-slate-400 text-sm">
                  <span>权重: {(p.weight * 100).toFixed(1)}%</span>
                  {p.reason && <p className="mt-1 text-xs">{p.reason}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Signals Table */}
      <section>
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-blue-400 rounded-full"></span>
          当前持仓信号排名
        </h2>
        {signals.length === 0 ? (
          <div className="bg-slate-800 rounded-xl p-8 text-center text-slate-400">
            暂无信号数据
          </div>
        ) : (
          <div className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-sm">
                  <th className="px-4 py-3 text-left">排名</th>
                  <th className="px-4 py-3 text-left">代码</th>
                  <th className="px-4 py-3 text-left">名称</th>
                  <th className="px-4 py-3 text-right">市值得分</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s) => (
                  <tr key={s.symbol} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex w-7 h-7 items-center justify-center rounded-full text-sm font-medium ${
                          s.rank <= 5
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-slate-700 text-slate-300'
                        }`}
                      >
                        {s.rank}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono">{s.symbol}</td>
                    <td className="px-4 py-3 text-slate-300">{s.name || '-'}</td>
                    <td className="px-4 py-3 text-right font-mono text-green-400">
                      {s.score.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
