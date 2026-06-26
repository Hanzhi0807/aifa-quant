import { Link } from "react-router";
import { ArrowLeft, Play, Search, Calendar, Hash, RefreshCw } from "lucide-react";
import { useState } from "react";
import { trpc } from "@/providers/trpc";
import GlassCard from "@/components/layout/GlassCard";

interface BacktestRun {
  id: number;
  name: string;
  startDate: string;
  endDate: string;
  topK: number;
  rebalanceFreq: number;
  rolling: boolean;
  benchmark: string;
  status: string;
  metrics: {
    totalReturn?: number;
    annualReturn?: number;
    sharpeRatio?: number;
    maxDrawdown?: number;
  } | null;
  createdAt: Date | string;
}

function StatusBadge({ status }: { status: string }) {
  const statusMap: Record<string, string> = {
    completed: "已完成",
    running: "运行中",
    failed: "失败",
    pending: "待运行",
  };
  const classes =
    status === "completed"
      ? "status-completed"
      : status === "running"
      ? "status-running animate-pulse-cyan"
      : "status-failed";
  return <span className={classes}>{statusMap[status] || status}</span>;
}

export default function Backtest() {
  const { data: backtests, isLoading } = trpc.backtest.list.useQuery({});
  const [search, setSearch] = useState("");

  const runs = (backtests || []) as BacktestRun[];

  const filtered = runs.filter((r) =>
    r.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-[var(--text-secondary)]" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-white">回测</h1>
              <p className="text-sm text-[var(--text-secondary)]">
                运行与管理量化回测
              </p>
            </div>
          </div>
        </div>

        {/* Configuration Panel */}
        <GlassCard title="回测配置" subtitle="第二阶段 — 即将上线">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider block mb-2">
                时间区间
              </label>
              <div className="flex items-center gap-2 bg-white/5 rounded-xl px-4 py-2.5 border border-white/5">
                <Calendar className="w-4 h-4 text-[var(--text-muted)]" />
                <span className="text-sm text-[var(--text-secondary)]">
                  2023-01-03 ~ 2024-12-31
                </span>
              </div>
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider block mb-2">
                持仓数量 Top-K
              </label>
              <div className="flex items-center gap-2 bg-white/5 rounded-xl px-4 py-2.5 border border-white/5">
                <Hash className="w-4 h-4 text-[var(--text-muted)]" />
                <span className="text-sm text-[var(--text-secondary)]">10</span>
              </div>
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider block mb-2">
                调仓频率
              </label>
              <div className="flex items-center gap-2 bg-white/5 rounded-xl px-4 py-2.5 border border-white/5">
                <RefreshCw className="w-4 h-4 text-[var(--text-muted)]" />
                <span className="text-sm text-[var(--text-secondary)]">
                  5 天
                </span>
              </div>
            </div>
            <div className="flex items-end">
              <button className="pill-btn-primary w-full flex items-center justify-center gap-2 opacity-50 cursor-not-allowed">
                <Play className="w-4 h-4" />
                运行回测
              </button>
            </div>
          </div>
        </GlassCard>

        {/* Backtest History */}
        <GlassCard
          title="回测历史"
          action={
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="搜索回测..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="bg-white/5 border border-white/5 rounded-full pl-9 pr-4 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--cyan)]/30 w-56"
              />
            </div>
          }
        >
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-14 bg-white/5 rounded-xl animate-pulse"
                />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      名称
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      时间区间
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      Top-K
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      调仓频率
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      滚动训练
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      收益率
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      夏普
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3">
                      状态
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((run) => (
                    <tr
                      key={run.id}
                      className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors duration-200"
                    >
                      <td className="py-3.5 pr-4">
                        <span className="text-sm font-medium text-white">
                          {run.name}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className="text-xs text-[var(--text-secondary)]">
                          {run.startDate} ~ {run.endDate}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className="text-sm text-[var(--text-secondary)]">
                          {run.topK}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className="text-sm text-[var(--text-secondary)]">
                          {run.rebalanceFreq}d
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span
                          className={`text-xs font-medium ${
                            run.rolling
                              ? "text-[var(--green)]"
                              : "text-[var(--text-muted)]"
                          }`}
                        >
                          {run.rolling ? "是" : "否"}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span
                          className={`text-sm font-medium ${
                            (run.metrics?.totalReturn || 0) >= 0
                              ? "text-[var(--green)]"
                              : "text-[var(--red)]"
                          }`}
                        >
                          {run.metrics?.totalReturn
                            ? `${(run.metrics.totalReturn * 100).toFixed(2)}%`
                            : "-"}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className="text-sm text-[var(--cyan)]">
                          {run.metrics?.sharpeRatio?.toFixed(2) || "-"}
                        </span>
                      </td>
                      <td className="py-3.5">
                        <StatusBadge status={run.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div className="text-center py-12">
                  <p className="text-sm text-[var(--text-muted)]">
                    暂无回测记录
                  </p>
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
