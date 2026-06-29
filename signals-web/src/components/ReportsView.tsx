import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

interface ReportMeta {
  id: number
  filename: string
  report_date: string
  title: string
}

interface ReportFull extends ReportMeta {
  content: string
}

function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split('\n')
  const elements: React.JSX.Element[] = []

  let inTable = false
  let tableRows: string[][] = []

  const flushTable = () => {
    if (tableRows.length < 2) return
    const headers = tableRows[0]
    const dataRows = tableRows.slice(1).filter(
      (r) => !r.every((cell) => /^[-|: ]+$/.test(cell))
    )
    elements.push(
      <div key={`table-${elements.length}`} className="overflow-x-auto my-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {headers.map((h, i) => (
                <th
                  key={i}
                  className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-2 pr-4"
                >
                  {h.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, ri) => (
              <tr key={ri} className="border-b border-white/[0.03]">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="py-2 pr-4 text-sm text-[var(--text-secondary)]"
                  >
                    {cell.trim()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
    tableRows = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.startsWith('|')) {
      inTable = true
      const cells = line.split('|').slice(1, -1)
      tableRows.push(cells)
      continue
    }

    if (inTable) {
      flushTable()
      inTable = false
    }

    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={i} className="text-xl font-bold text-white mt-4 mb-2">
          {line.slice(2)}
        </h1>
      )
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={i} className="text-lg font-semibold text-white mt-6 mb-2">
          {line.slice(3)}
        </h2>
      )
    } else if (line.startsWith('### ')) {
      elements.push(
        <h3 key={i} className="text-base font-semibold text-white mt-4 mb-1">
          {line.slice(4)}
        </h3>
      )
    } else if (line.startsWith('**') && line.endsWith('**')) {
      elements.push(
        <p key={i} className="text-sm font-semibold text-white my-1">
          {line.replace(/\*\*/g, '')}
        </p>
      )
    } else if (line.startsWith('- ')) {
      elements.push(
        <li key={i} className="text-sm text-[var(--text-secondary)] ml-4 list-disc">
          {line.slice(2)}
        </li>
      )
    } else if (line.trim() === '') {
      continue
    } else {
      elements.push(
        <p key={i} className="text-sm text-[var(--text-secondary)] my-1">
          {line}
        </p>
      )
    }
  }

  if (inTable) flushTable()

  return <div className="space-y-1">{elements}</div>
}

export function ReportsView() {
  const [reports, setReports] = useState<ReportMeta[]>([])
  const [selected, setSelected] = useState<ReportFull | null>(null)
  const [loading, setLoading] = useState(true)
  const [contentLoading, setContentLoading] = useState(false)

  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    setLoading(true)
    const { data } = await supabase
      .from('weekly_reports')
      .select('id, filename, report_date, title')
      .order('report_date', { ascending: false })

    setReports(data ?? [])
    setLoading(false)
  }

  const loadContent = async (report: ReportMeta) => {
    setContentLoading(true)
    const { data } = await supabase
      .from('weekly_reports')
      .select('*')
      .eq('id', report.id)
      .single()

    if (data) {
      setSelected(data as ReportFull)
    }
    setContentLoading(false)
  }

  if (loading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (reports.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-10 text-center space-y-3">
        <svg className="w-12 h-12 mx-auto text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-[var(--text-secondary)]">暂无选股报告</p>
        <p className="text-xs text-[var(--text-muted)]">
          运行{' '}
          <code className="px-1.5 py-0.5 bg-white/5 rounded text-[var(--cyan)]">
            aifa weekly-report
          </code>{' '}
          生成 AI 选股报告
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-white">AI 选股报告</h2>
        <p className="text-sm text-[var(--text-muted)] mt-0.5">
          每周自动生成的 AI 选股推理报告
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Report list */}
        <div className="glass-card rounded-2xl p-4 lg:col-span-1">
          <h3 className="text-sm font-semibold text-white mb-3">历史报告</h3>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {reports.map((r) => (
              <button
                key={r.id}
                onClick={() => loadContent(r)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                  selected?.id === r.id
                    ? 'bg-[var(--cyan)]/10 border border-[var(--cyan)]/30'
                    : 'hover:bg-white/5 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-[var(--text-muted)] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <span className="text-sm text-white">{r.report_date}</span>
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-0.5 ml-6 truncate">
                  {r.title}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Report content */}
        <div className="glass-card rounded-2xl p-5 lg:col-span-3">
          {!selected ? (
            <div className="h-[400px] flex flex-col items-center justify-center gap-3">
              <svg className="w-12 h-12 text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-sm text-[var(--text-secondary)]">从左侧选择一份报告查看</p>
            </div>
          ) : contentLoading ? (
            <div className="h-[400px] flex items-center justify-center">
              <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div>
              <h3 className="text-base font-semibold text-white mb-4">{selected.title}</h3>
              <MarkdownRenderer content={selected.content} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
