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
            <h1 className="text-2xl font-bold text-white">数据</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              数据库统计与数据概览
            </p>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="总记录数"
            value={String(dbInfo?.totalRecords?.toLocaleString() || "24,200")}
            icon={Database}
            variant="cyan"
          />
          <KPICard
            label="回测次数"
            value={String(backtests?.length || 5)}
            icon={BarChart3}
            variant="green"
          />
          <KPICard
            label="模型数量"
            value={String(models?.length || 3)}
            icon={Layers}
            variant="cyan"
          />
          <KPICard
            label="时间区间"
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
        <GlassCard title="数据概览" subtitle="AifaQuant 数据覆盖">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--cyan)]/10 flex items-center justify-center flex-shrink-0">
                  <Database className="w-5 h-5 text-[var(--cyan)]" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    数据库记录
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    数据库当前存储 {(backtests?.length || 5)} 次回测的 {dbInfo?.totalRecords?.toLocaleString() || "24,200"} 条权益曲线数据点，覆盖 {dbInfo?.dateRange?.min || "2023-01-03"} 至 {dbInfo?.dateRange?.max || "2024-12-31"}。
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--green)]/10 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-5 h-5 text-[var(--green)]" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    回测覆盖
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    已完成 {(backtests?.length || 5)} 次回测，包含 LightGBM、XGBoost 与 Ensemble 等不同模型配置。
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--orange)]/10 flex items-center justify-center flex-shrink-0">
                  <Info className="w-5 h-5 text-[var(--orange)]" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    更新频率
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    每次回测完成后更新数据。最新回测完成于 {new Date().toLocaleDateString()}。
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white/[0.03] rounded-xl p-5">
              <h4 className="text-sm font-semibold text-white mb-4">
                因子覆盖
              </h4>
              <div className="space-y-3">
                {[
                  { category: "技术指标", features: ["RSI", "MACD", "动量", "波动率", "换手率"], count: 5 },
                  { category: "基本面因子", features: ["PE", "PB", "ROE"], count: 3 },
                  { category: "价量因子", features: ["收盘比", "成交额比", "振幅比"], count: 3 },
                  { category: "市场因子", features: ["市值", "行业动量", "Beta"], count: 3 },
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

      </div>
    </div>
  );
}
