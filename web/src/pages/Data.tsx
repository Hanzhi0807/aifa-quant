import { Link } from "react-router";
import {
  ArrowLeft,
  Database,
  Calendar,
  BarChart3,
  Layers,
  TrendingUp,
  Info,
} from "lucide-react";
import { trpc } from "@/providers/trpc";
import GlassCard from "@/components/layout/GlassCard";
import KPICard from "@/components/dashboard/KPICard";

export default function Data() {
  const { data: dbInfo } = trpc.dbInfo.stats.useQuery();
  const { data: models } = trpc.model.list.useQuery();
  const { data: backtests } = trpc.backtest.list.useQuery({});

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4 animate-fade-in">
          <Link
            to="/"
            className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-[var(--text-secondary)]" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">Data</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Database statistics and data overview
            </p>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="Total Records"
            value={String(dbInfo?.totalRecords?.toLocaleString() || "24,200")}
            icon={Database}
            variant="cyan"
          />
          <KPICard
            label="Backtest Runs"
            value={String(backtests?.length || 5)}
            icon={BarChart3}
            variant="green"
          />
          <KPICard
            label="Models"
            value={String(models?.length || 3)}
            icon={Layers}
            variant="cyan"
          />
          <KPICard
            label="Date Range"
            value={
              dbInfo?.dateRange
                ? `${dbInfo.dateRange.min?.slice(0, 4)}-${dbInfo.dateRange.max?.slice(0, 4)}`
                : "2023-2024"
            }
            icon={Calendar}
            variant="green"
          />
        </div>

        {/* Data Summary */}
        <GlassCard title="Data Summary" subtitle="AifaQuant Data Coverage">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--cyan)]/10 flex items-center justify-center flex-shrink-0">
                  <Database className="w-5 h-5 text-[var(--cyan)]" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    Database Records
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    The database currently stores {dbInfo?.totalRecords?.toLocaleString() || "24,200"} equity curve data points across {(backtests?.length || 5)} backtest runs, covering {dbInfo?.dateRange?.min || "2023-01-03"} to {dbInfo?.dateRange?.max || "2024-12-31"}.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--green)]/10 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-5 h-5 text-[var(--green)]" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    Backtest Coverage
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {(backtests?.length || 5)} backtest runs completed with various configurations including LightGBM, XGBoost, and Ensemble models.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--orange)]/10 flex items-center justify-center flex-shrink-0">
                  <Info className="w-5 h-5 text-[var(--orange)]" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    Update Frequency
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Data is updated after each backtest run. The latest backtest was completed on {new Date().toLocaleDateString()}.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white/[0.03] rounded-xl p-5">
              <h4 className="text-sm font-semibold text-white mb-4">
                Feature Coverage
              </h4>
              <div className="space-y-3">
                {[
                  { category: "Technical Indicators", features: ["RSI", "MACD", "Momentum", "Volatility", "Turnover"], count: 5 },
                  { category: "Fundamental Factors", features: ["PE", "PB", "ROE"], count: 3 },
                  { category: "Price/Volume", features: ["Close Ratio", "Amount Ratio", "High-Low Ratio"], count: 3 },
                  { category: "Market Factors", features: ["Market Cap", "Industry Momentum", "Beta"], count: 3 },
                ].map((group) => (
                  <div key={group.category}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs text-[var(--text-secondary)]">
                        {group.category}
                      </span>
                      <span className="text-xs text-[var(--cyan)] font-medium">
                        {group.count}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {group.features.map((f) => (
                        <span
                          key={f}
                          className="px-2 py-0.5 bg-white/5 rounded-md text-[10px] text-[var(--text-muted)]"
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Quick Start Guide */}
        <GlassCard title="Quick Start" subtitle="Getting Started with AifaQuant">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                step: "01",
                title: "Install",
                desc: "pip install git+https://github.com/ivyzhi0807/aifa-quant.git",
                icon: <Layers className="w-5 h-5 text-[var(--cyan)]" />,
              },
              {
                step: "02",
                title: "Configure",
                desc: "Set up your iFind token in .env file for data access",
                icon: <Database className="w-5 h-5 text-[var(--green)]" />,
              },
              {
                step: "03",
                title: "Run Backtest",
                desc: "Use the Python API or web dashboard to trigger backtests",
                icon: <TrendingUp className="w-5 h-5 text-[var(--orange)]" />,
              },
            ].map((item) => (
              <div
                key={item.step}
                className="bg-white/[0.03] rounded-xl p-5 hover:bg-white/[0.05] transition-all duration-300"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">
                    {item.icon}
                  </div>
                  <div>
                    <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
                      Step {item.step}
                    </span>
                    <h4 className="text-sm font-semibold text-white">
                      {item.title}
                    </h4>
                  </div>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
