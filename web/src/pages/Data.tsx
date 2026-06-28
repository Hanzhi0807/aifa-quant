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
  const { data: backtests } = trpc.backtest.list.useQuery();

  const hasRange = dbInfo?.dateRange?.min && dbInfo?.dateRange?.max;
  const dateRangeText = hasRange
    ? `${dbInfo!.dateRange.min!.slice(0, 4)}-${dbInfo!.dateRange.max!.slice(0, 4)}`
    : "-";

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
            value={dbInfo?.totalRecords?.toLocaleString() ?? "-"}
            icon={Database}
            variant="cyan"
          />
          <KPICard
            label="回测次数"
            value={backtests?.length?.toString() ?? "-"}
            icon={BarChart3}
            variant="green"
          />
          <KPICard
            label="模型数量"
            value={models?.length?.toString() ?? "-"}
            icon={Layers}
            variant="cyan"
          />
          <KPICard
            label="时间区间"
            value={dateRangeText}
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
                    当前数据库共 {(dbInfo?.symbols ?? 0).toLocaleString()} 只股票、{" "}
                    {(dbInfo?.totalRecords ?? 0).toLocaleString()} 条日线行情，时间区间为{" "}
                    {dbInfo?.dateRange?.min || "-"} 至 {dbInfo?.dateRange?.max || "-"}。
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
                    已生成 {(backtests?.length || 0).toString()} 次回测报告，保存在{" "}
                    <code className="text-[var(--cyan)]">data_store/reports/</code>。
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
                    每个工作日收盘后自动运行数据刷新与模拟交易；盘中不调整持仓。
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
