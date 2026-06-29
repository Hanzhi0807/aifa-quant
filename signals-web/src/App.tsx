import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import { Auth } from './components/Auth'
import { Dashboard } from './components/Dashboard'
import { ShapView } from './components/ShapView'
import { ReportsView } from './components/ReportsView'
import type { User } from '@supabase/supabase-js'
import './index.css'

type Page = 'dashboard' | 'shap' | 'reports'

const NAV_ITEMS: { key: Page; label: string }[] = [
  { key: 'dashboard', label: 'AI 选股' },
  { key: 'shap', label: '模型解释' },
  { key: 'reports', label: '选股报告' },
]

function AppShell({ user }: { user: User }) {
  const [page, setPage] = useState<Page>('dashboard')

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  return (
    <div className="min-h-screen">
      {/* Top navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[#0a0e1a]/80 border-b border-white/5">
        <div className="max-w-[1200px] mx-auto px-4 md:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="text-white font-bold text-lg tracking-wide">AifaQuant</span>
            <div className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setPage(item.key)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
                    page === item.key
                      ? 'bg-white/10 text-[var(--cyan)]'
                      : 'text-white/50 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[var(--text-muted)] text-xs hidden md:inline">{user.email}</span>
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs transition border border-white/10"
            >
              退出
            </button>
          </div>
        </div>
      </nav>

      {/* Page content */}
      <main className="max-w-[1200px] mx-auto px-4 md:px-8 py-8">
        {page === 'dashboard' && <Dashboard user={user} />}
        {page === 'shap' && <ShapView />}
        {page === 'reports' && <ReportsView />}
      </main>
    </div>
  )
}

function App() {
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

  return user ? <AppShell user={user} /> : <Auth />
}

export default App
