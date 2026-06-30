import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { supabase } from './lib/supabase'
import { Auth } from './components/Auth'
import { Dashboard } from './components/Dashboard'
import { ShapView } from './components/ShapView'
import { ReportsView } from './components/ReportsView'
import { StockDetail } from './components/StockDetail'
import { ProfileCompare } from './components/ProfileCompare'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Onboarding } from './components/Onboarding'
import { useQuery } from './lib/useQuery'
import type { User } from '@supabase/supabase-js'
import './index.css'

const NAV_ITEMS = [
  { path: '/dashboard', label: 'AI 选股' },
  { path: '/compare', label: '策略对比' },
  { path: '/explain', label: '模型解释' },
  { path: '/reports', label: '选股报告' },
]

function AppShell({ user }: { user: User }): React.JSX.Element {
  const location = useLocation()
  const profile = useQuery().get('profile') ?? 'balanced'

  return (
    <div className="min-h-screen">
      <Onboarding />
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[#0a0e1a]/80 border-b border-white/5">
        <div className="max-w-[1200px] mx-auto px-4 md:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="text-white font-bold text-lg tracking-wide">AifaQuant</span>
            <div className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path + (item.path === '/dashboard' ? `?profile=${profile}` : '')}
                  className={({ isActive }) =>
                    `px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-white/10 text-[var(--cyan)]'
                        : 'text-white/50 hover:text-white hover:bg-white/5'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[var(--text-muted)] text-xs hidden md:inline">{user.email}</span>
            <button
              onClick={() => supabase.auth.signOut()}
              className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs transition border border-white/10"
            >
              退出
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-[1200px] mx-auto px-4 md:px-8 py-8">
        <ErrorBoundary key={location.pathname}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard user={user} />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/explain" element={<ShapView />} />
            <Route path="/reports" element={<ReportsView />} />
            <Route path="/reports/:date" element={<ReportsView />} />
            <Route path="/compare" element={<ProfileCompare />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

function App(): React.JSX.Element {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })
    return () => subscription.unsubscribe()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    )
  }

  if (!user) return <Auth />

  return (
    <BrowserRouter>
      <AppShell user={user} />
    </BrowserRouter>
  )
}

export default App
