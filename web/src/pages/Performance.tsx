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
  const { data: metrics } = trpc.metrics.getByBacktestId.useQuery({
    backtestId: 1,
  });

  const m = metrics || {};

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        <div className="animate-fade-in">
          <h1 className="text-2xl font-bold text-white mb-1">策略原理与绩效</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            回测结果、净值曲线、因子有效性等技术细节
          </p>
        </div>

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
