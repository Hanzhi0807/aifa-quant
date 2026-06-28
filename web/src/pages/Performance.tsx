import {
  TrendingUp,
  BarChart3,
  AlertTriangle,
  Activity,
} from "lucide-react";
import { trpc } from "@/providers/trpc";
import KPICard from "@/components/dashboard/KPICard";
import EquityCurveChart from "@/components/dashboard/EquityCurveChart";
import MetricsGrid from "@/components/dashboard/MetricsGrid";
import BacktestTable from "@/components/dashboard/BacktestTable";
import FactorChart from "@/components/dashboard/FactorChart";

export default function Performance() {
  const { data: metrics, isLoading } = trpc.metrics.latest.useQuery();

  const m = metrics || {};
  const hasData = Object.keys(m).length > 0;

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        <div className="animate-fade-in">
          <h1 className="text-2xl font-bold text-white mb-1">策略原理与绩效</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            回测结果、净值曲线、因子重要性等技术细节
          </p>
        </div>

        {!hasData && !isLoading && (
          <div className="glass-card rounded-2xl p-6 text-center">
            <p className="text-sm text-[var(--text-muted)] mb-2">暂无回测数据</p>
            <code className="text-xs text-[var(--cyan)] font-mono bg-black/30 px-3 py-2 rounded-lg">
              python -m aifa_quant.cli.main backtest --start 20250101 --end &lt;今天日期&gt; --rolling --benchmark 000300.SH --top-k 5 --freq 5 --no-sentiment --cache-only
            </code>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="总收益率"
            value={`${((m.totalReturn || 0) * 100).toFixed(2)}%`}
            trend="up"
            trendValue={`+${(((m.excessReturn || m.totalReturn || 0)) * 100).toFixed(2)}% 相对基准`}
            icon={TrendingUp}
            variant="green"
          />
          <KPICard
            label="年化收益率"
            value={`${((m.annualReturn || 0) * 100).toFixed(2)}%`}
            trend="up"
            icon={BarChart3}
            variant="green"
          />
          <KPICard
            label="夏普比率"
            value={(m.sharpeRatio || 0).toFixed(2)}
            icon={Activity}
            variant="cyan"
          />
          <KPICard
            label="最大回撤"
            value={`${((m.maxDrawdown || 0) * 100).toFixed(2)}%`}
            trend="down"
            icon={AlertTriangle}
            variant="orange"
          />
        </div>

        <EquityCurveChart />
        <MetricsGrid />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BacktestTable />
          <FactorChart />
        </div>

        <footer className="text-center py-6 border-t border-white/5">
          <p className="text-xs text-[var(--text-muted)]">
            AifaQuant — 本页数据仅供技术研究，不构成投资建议。
          </p>
        </footer>
      </div>
    </div>
  );
}
