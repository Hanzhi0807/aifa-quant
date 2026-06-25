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

export default function Home() {
  const { data: metrics } = trpc.metrics.getByBacktestId.useQuery({
    backtestId: 1,
  });

  const m = metrics || {};

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        {/* Hero Section */}
        <div className="animate-fade-in">
          <h1 className="text-2xl font-bold text-white mb-1">
            AifaQuant Dashboard
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            A-Share Quantitative Research Framework — Backtest Results &
            Analytics
          </p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="Total Return"
            value={`${((m.totalReturn || 0) * 100).toFixed(2)}%`}
            trend="up"
            trendValue="+11.87% vs Benchmark"
            icon={TrendingUp}
            variant="green"
          />
          <KPICard
            label="Annual Return"
            value={`${((m.annualReturn || 0) * 100).toFixed(2)}%`}
            trend="up"
            icon={BarChart3}
            variant="green"
          />
          <KPICard
            label="Sharpe Ratio"
            value={(m.sharpeRatio || 0).toFixed(2)}
            icon={Activity}
            variant="cyan"
          />
          <KPICard
            label="Max Drawdown"
            value={`${((m.maxDrawdown || 0) * 100).toFixed(2)}%`}
            trend="down"
            icon={AlertTriangle}
            variant="orange"
          />
        </div>

        {/* Equity Curve Chart */}
        <EquityCurveChart />

        {/* Performance Metrics Grid */}
        <MetricsGrid />

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BacktestTable />
          <FactorChart />
        </div>

        {/* Footer */}
        <footer className="text-center py-6 border-t border-white/5">
          <p className="text-xs text-[var(--text-muted)]">
            AifaQuant v0.2.0 — A-Share Quantitative Research Framework
          </p>
        </footer>
      </div>
    </div>
  );
}
