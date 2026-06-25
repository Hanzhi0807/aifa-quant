import { Link } from "react-router";
import { ArrowUpRight } from "lucide-react";
import { trpc } from "@/providers/trpc";
import GlassCard from "../layout/GlassCard";

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
    sharpeRatio?: number;
  } | null;
  createdAt: Date | string;
}

function StatusBadge({ status }: { status: string }) {
  const classes =
    status === "completed"
      ? "status-completed"
      : status === "running"
      ? "status-running animate-pulse-cyan"
      : "status-failed";
  return <span className={classes}>{status}</span>;
}

export default function BacktestTable() {
  const { data: backtests, isLoading } = trpc.backtest.list.useQuery({});

  const runs = (backtests || []) as BacktestRun[];

  return (
    <GlassCard
      title="Recent Backtest Runs"
      action={
        <Link
          to="/backtest"
          className="text-xs text-[var(--cyan)] hover:underline flex items-center gap-1"
        >
          View All
          <ArrowUpRight className="w-3 h-3" />
        </Link>
      }
    >
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-12 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Name
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Date Range
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Top-K
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Rebalance
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Rolling
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Return
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                  Sharpe
                </th>
                <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 5).map((run, index) => (
                <tr
                  key={run.id}
                  className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors duration-200"
                  style={{ animationDelay: `${index * 0.05}s` }}
                >
                  <td className="py-3 pr-4">
                    <span className="text-sm font-medium text-white">
                      {run.name}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className="text-xs text-[var(--text-secondary)]">
                      {run.startDate} ~ {run.endDate}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className="text-sm text-[var(--text-secondary)]">
                      {run.topK}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className="text-sm text-[var(--text-secondary)]">
                      {run.rebalanceFreq}d
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className={`text-xs font-medium ${
                        run.rolling
                          ? "text-[var(--green)]"
                          : "text-[var(--text-muted)]"
                      }`}
                    >
                      {run.rolling ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
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
                  <td className="py-3 pr-4">
                    <span className="text-sm text-[var(--cyan)]">
                      {run.metrics?.sharpeRatio?.toFixed(2) || "-"}
                    </span>
                  </td>
                  <td className="py-3">
                    <StatusBadge status={run.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </GlassCard>
  );
}
