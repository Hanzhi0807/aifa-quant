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
  { id: 'aggressive', label: '激进型', desc: '高收益高波动', topK: 5, risk: '2.5%', stopLoss: '2.0×', takeProfit: '4.0×' },
  { id: 'balanced', label: '均衡型', desc: '攻守兼备', topK: 8, risk: '2.0%', stopLoss: '2.5×', takeProfit: '5.0×' },
  { id: 'conservative', label: '稳健型', desc: '低回撤分散', topK: 12, risk: '1.5%', stopLoss: '3.0×', takeProfit: '6.0×' },
  { id: 'growth', label: '成长型', desc: '高成长潜力', topK: 6, risk: '2.0%', stopLoss: '2.0×', takeProfit: '4.5×' },
  { id: 'value', label: '价值型', desc: '低估值优先', topK: 8, risk: '1.8%', stopLoss: '2.5×', takeProfit: '5.0×' },
]

const FAQ = [
  {
    q: '不同策略有什么区别？',
    a: '激进型集中持有 5 只股票追求高收益；均衡型持有 8 只兼顾收益与风险；稳健型分散持有 12 只严格控制回撤；成长型聚焦高 ROE 成长股；价值型偏好低估值股票。',
  },
  {
    q: '多久调仓一次？',
    a: '所有策略每天收盘后审视一次持仓：盘中不做调整，盘后使用当日收盘价计算信号和风控，生成次日开盘可执行的目标持仓。',
  },
  {
    q: 'AI 是怎么选股的？',
    a: '模型综合技术面趋势、动量、波动率、基本面估值等上百个因子，使用 LightGBM 对约 1800 只股票打分，再按 profile 偏好加权，选出上涨概率最高的股票。',
  },
  {
    q: '这个策略靠谱吗？',
    a: '策略基于上百个量化因子和机器学习模型，在历史回测中表现优异。但历史表现不代表未来收益，股市有风险，投资需谨慎。',
  },
]

type Tab = 'holdings' | 'orders' | 'about'

export function Dashboard({ user }: { user: User }) {
  const [signals, setSignals] = useState<Signal[]>([])
  const [portfolio, setPortfolio] = useState<Position[]>([])
  const [loading, setLoading] = useState(true)
  const [signalDate, setSignalDate] = useState('')
  const [activeProfile, setActiveProfile] = useState('balanced')
  const [activeTab, setActiveTab] = useState<Tab>('holdings')
  const [profileCounts, setProfileCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    loadProfileCounts()
  }, [])

  useEffect(() => {
    loadData(activeProfile)
  }, [activeProfile])

  const loadProfileCounts = async () => {
    const counts: Record<string, number> = {}
    for (const p of PROFILES) {
      const { data } = await supabase
        .from('portfolio')
        .select('trade_date')
        .eq('profile', p.id)
        .order('trade_date', { ascending: false })
        .limit(1)

      if (data && data.length > 0) {
        const latestDate = data[0].trade_date
        const { count: c } = await supabase
          .from('portfolio')
          .select('*', { count: 'exact', head: true })
          .eq('profile', p.id)
          .eq('trade_date', latestDate)
        counts[p.id] = c || 0
      } else {
        counts[p.id] = 0
      }
    }
    setProfileCounts(counts)
  }

  const loadData = async (profile: string) => {
    setLoading(true)

    const [signalsRes, portfolioRes] = await Promise.all([
      supabase
        .from('daily_signals')
        .select('*')
        .eq('profile', profile)
        .order('trade_date', { ascending: false })
        .order('rank')
        .limit(50),
      supabase
        .from('portfolio')
        .select('*')
        .eq('profile', profile)
        .order('trade_date', { ascending: false })
        .limit(20),
    ])

    if (signalsRes.data?.length) {
      setSignals(signalsRes.data)
      setSignalDate(signalsRes.data[0].trade_date)
    } else {
      setSignals([])
      setSignalDate('')
    }
    setPortfolio(portfolioRes.data || [])
    setLoading(false)
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  const currentProfile = PROFILES.find((p) => p.id === activeProfile)!

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-[var(--text-muted)]">加载中...</div>
      </div>
    )
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'holdings', label: '当前持仓' },
    { key: 'orders', label: '信号排名' },
    { key: 'about', label: '策略说明' },
  ]

  return (
    <div className="min-h-screen pt-8 pb-12 px-4 md:px-8">
      <div className="max-w-[1200px] mx-auto space-y-8">
        {/* Header */}
        <header className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white">AI 智能选股</h1>
            <p className="text-[var(--text-secondary)] text-sm mt-1">
              选择适合你的策略风格，查看 AI 推荐的精选股票
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[var(--text-muted)] text-sm hidden md:inline">{user.email}</span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition border border-white/10"
            >
              退出
            </button>
          </div>
        </header>

        {/* Profile selector */}
        <section>
          <div className="flex flex-wrap items-center gap-2">
            {PROFILES.map((p) => (
              <button
                key={p.id}
                onClick={() => setActiveProfile(p.id)}
                className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  activeProfile === p.id
                    ? 'bg-[var(--cyan)]/15 text-[var(--cyan)] border border-[var(--cyan)]/20'
                    : 'bg-white/5 text-[var(--text-muted)] hover:text-white hover:bg-white/10 border border-transparent'
                }`}
              >
                <span>{p.label}</span>
                <span className="ml-1.5 text-[10px] opacity-60">{p.desc}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4 text-xs text-[var(--text-muted)] mt-3">
            <span>信号日期：{signalDate || '暂无数据'}</span>
          </div>
        </section>

        {/* Strategy comparison cards */}
        <section>
          <h2 className="text-lg font-bold text-white mb-3">策略对比</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {PROFILES.map((p) => (
              <button
                key={p.id}
                onClick={() => setActiveProfile(p.id)}
                className={`rounded-xl p-4 text-center transition-all cursor-pointer ${
                  activeProfile === p.id
                    ? 'bg-[var(--cyan)]/10 border border-[var(--cyan)]/20'
                    : 'glass-card hover:bg-white/[0.05]'
                }`}
              >
                <p className="text-xs font-medium text-white mb-1">{p.label}</p>
                <p className="text-2xl font-bold text-[var(--cyan)]">
                  {profileCounts[p.id] || 0}
                </p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1">
                  {profileCounts[p.id] || 0} 只持仓
                </p>
              </button>
            ))}
          </div>
        </section>

        {/* Risk disclaimer */}
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] px-1">
          <svg className="w-3.5 h-3.5 text-[var(--orange)] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          以下为 AI 模型分析结果，仅供学习参考，不构成投资建议。
        </div>

        {/* Tabs */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-white">
              {currentProfile.label}
              <span className="text-sm font-normal text-[var(--text-muted)] ml-2">
                {currentProfile.desc}
              </span>
            </h2>
            <div className="flex items-center gap-1 bg-white/5 p-1 rounded-lg">
              {tabs.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    activeTab === t.key
                      ? 'bg-[var(--cyan)]/15 text-[var(--cyan)]'
                      : 'text-[var(--text-muted)] hover:text-white'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tab: Holdings */}
          {activeTab === 'holdings' && (
            portfolio.length === 0 ? (
              <div className="glass-card rounded-2xl p-10 text-center text-[var(--text-muted)]">
                暂无持仓推荐数据，请等待每日信号更新
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {portfolio.map((pos, idx) => (
                  <div key={pos.symbol} className="stock-card">
                    <div className="flex items-start justify-between mb-3">
                      <div
                        className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold ${
                          idx < 3
                            ? 'bg-[var(--cyan)]/15 text-[var(--cyan)]'
                            : 'bg-white/5 text-[var(--text-muted)]'
                        }`}
                      >
                        {idx + 1}
                      </div>
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--green)]/10 text-[var(--green)]">
                        {pos.action === 'hold' ? '持有' : pos.action.toUpperCase()}
                      </span>
                    </div>

                    <h3 className="text-base font-semibold text-white mb-0.5">
                      {pos.name || pos.symbol}
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] mb-3">{pos.symbol}</p>

                    {/* Weight bar */}
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] text-[var(--text-muted)]">持仓占比</span>
                        <span className="text-xs font-medium text-white">
                          {(pos.weight * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(pos.weight * 100, 100)}%`,
                            background: 'linear-gradient(90deg, var(--cyan), var(--green))',
                          }}
                        />
                      </div>
                    </div>

                    {pos.reason && (
                      <p className="text-[10px] text-[var(--text-muted)] mt-2">{pos.reason}</p>
                    )}
                  </div>
                ))}
              </div>
            )
          )}

          {/* Tab: Signal Rankings */}
          {activeTab === 'orders' && (
            signals.length === 0 ? (
              <div className="glass-card rounded-2xl p-10 text-center text-[var(--text-muted)]">
                暂无信号数据
              </div>
            ) : (
              <div className="glass-card rounded-2xl overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/5 text-[var(--text-muted)] text-xs">
                      <th className="px-4 py-3 text-left">排名</th>
                      <th className="px-4 py-3 text-left">代码</th>
                      <th className="px-4 py-3 text-left">名称</th>
                      <th className="px-4 py-3 text-right">AI 得分</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.map((s) => (
                      <tr key={s.symbol} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex w-7 h-7 items-center justify-center rounded-full text-xs font-medium ${
                              s.rank <= 3
                                ? 'bg-[var(--cyan)]/15 text-[var(--cyan)]'
                                : 'bg-white/5 text-[var(--text-muted)]'
                            }`}
                          >
                            {s.rank}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-sm">{s.symbol}</td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">{s.name || '-'}</td>
                        <td className="px-4 py-3 text-right font-mono text-[var(--green)]">
                          {s.score.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}

          {/* Tab: About */}
          {activeTab === 'about' && (
            <div className="glass-card rounded-2xl p-6 space-y-5">
              <div>
                <h3 className="text-white font-semibold mb-1">{currentProfile.label}</h3>
                <p className="text-sm text-[var(--text-secondary)]">{currentProfile.desc}</p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">目标持仓数</p>
                  <p className="text-white font-medium">{currentProfile.topK} 只</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">单仓风险预算</p>
                  <p className="text-white font-medium">{currentProfile.risk}</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">止损 ATR 倍数</p>
                  <p className="text-white font-medium">{currentProfile.stopLoss}</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">止盈 ATR 倍数</p>
                  <p className="text-white font-medium">{currentProfile.takeProfit}</p>
                </div>
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                最终分数 = 0.7 × 模型分 + 0.3 × profile 因子偏好分。因此不同 profile 会从同一批股票中选出不同标的。
              </p>
            </div>
          )}
        </section>

        {/* FAQ */}
        <section>
          <h2 className="text-lg font-bold text-white mb-3">常见问题</h2>
          <div className="space-y-3">
            {FAQ.map((item) => (
              <details key={item.q} className="glass-card rounded-xl group">
                <summary className="px-5 py-4 cursor-pointer text-sm font-medium text-white list-none flex items-center justify-between">
                  {item.q}
                  <svg className="w-4 h-4 text-[var(--text-muted)] group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <p className="px-5 pb-4 text-sm text-[var(--text-secondary)] leading-relaxed">
                  {item.a}
                </p>
              </details>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className="text-center pt-6 border-t border-white/5">
          <p className="text-xs text-[var(--text-muted)]">
            AifaQuant — AI 驱动的 A 股量化策略平台。历史表现不代表未来收益。
          </p>
        </footer>
      </div>
    </div>
  )
}
