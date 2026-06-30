import { useState } from 'react'
import { nextMonday } from '../lib/freshness'

const STEPS = [
  {
    title: '选择适合你的投资风格',
    body: '5 个策略 profile：激进 / 均衡 / 稳健 / 成长 / 价值。可在顶部切换，每个 profile 持仓与风控独立。',
  },
  {
    title: '查看 AI 每日推荐操作',
    body: '首页操作台显示今日该买什么、卖什么、为什么。委托单可导出 CSV。',
  },
  {
    title: '了解模型为何这样选',
    body: '点击持仓行进入个股详情，查看 SHAP 瀑布图与人话解释。模型通常每周一更新。',
  },
]

/** 3-step onboarding overlay; shown once (localStorage flag). */
export function Onboarding(): React.JSX.Element | null {
  const [done, setDone] = useState(() => localStorage.getItem('onboarding_done') === '1')
  const [step, setStep] = useState(0)

  if (done) return null

  const next = (): void => {
    if (step < STEPS.length - 1) {
      setStep(step + 1)
    } else {
      localStorage.setItem('onboarding_done', '1')
      setDone(true)
    }
  }

  const skip = (): void => {
    localStorage.setItem('onboarding_done', '1')
    setDone(true)
  }

  const s = STEPS[step]
  return (
    <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="glass-card p-6 max-w-md w-full">
        <div className="flex justify-between items-center mb-4">
          <span className="text-xs text-[var(--text-muted)]">{step + 1} / {STEPS.length}</span>
          <button onClick={skip} className="text-xs text-[var(--text-muted)] hover:text-white">跳过</button>
        </div>
        <div className="text-xl font-bold text-white mb-2">{s.title}</div>
        <div className="text-sm text-[var(--text-muted)] mb-6 leading-relaxed">{s.body}</div>
        <div className="text-xs text-[var(--text-muted)] mb-4">下次更新预计：{nextMonday()}</div>
        <button
          onClick={next}
          className="w-full py-2.5 bg-[var(--cyan)] text-black rounded-lg text-sm font-medium hover:opacity-90"
        >
          {step < STEPS.length - 1 ? '下一步' : '开始使用'}
        </button>
      </div>
    </div>
  )
}
