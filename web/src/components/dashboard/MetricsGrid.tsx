import { trpc } from "@/providers/trpc";
import GlassCard from "../layout/GlassCard";

interface MetricItem {
  name: string;
  key: string;
  format: "percent" | "number" | "ratio";
}

const metricsList: MetricItem[] = [
  { name: "总收益率", key: "totalReturn", format: "percent" },
  { name: "年化收益率", key: "annualReturn", format: "percent" },
  { name: "夏普比率", key: "sharpeRatio", format: "ratio" },
  { name: "最大回撤", key: "maxDrawdown", format: "percent" },
  { name: "年化波动率", key: "volatility", format: "percent" },
  { name: "日胜率", key: "winRate", format: "percent" },
  { name: "盈亏比", key: "profitFactor", format: "ratio" },
  { name: "基准收益", key: "benchmarkTotalReturn", format: "percent" },
  { name: "超额收益", key: "excessReturn", format: "percent" },
  { name: "信息比率", key: "informationRatio", format: "ratio" },
  { name: "卡玛比率", key: "calmarRatio", format: "ratio" },
  { name: "索提诺比率", key: "sortinoRatio", format: "ratio" },
];

function formatValue(value: number, format: string): string {
  if (format === "percent") {
    return `${(value >= 0 ? "+" : "")}${(value * 100).toFixed(2)}%`;
  }
  if (format === "ratio") {
    return value.toFixed(2);
  }
  return String(value);
}

export default function MetricsGrid() {
  const { data: metrics, isLoading } = trpc.metrics.latest.useQuery();

  if (isLoading) {
    return (
      <GlassCard title="绩效指标">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="h-16 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
      </GlassCard>
    );
  }

  const metricValues = metrics || {};

  // Calculate max absolute value for bar scaling
  const numericValues = metricsList
    .map((m) => Math.abs(Number(metricValues[m.key as keyof typeof metricValues]) || 0))
    .filter((v) => !isNaN(v));
  const maxVal = numericValues.length > 0 ? Math.max(...numericValues) : 1;

  return (
    <GlassCard title="绩效指标">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {metricsList.map((metric) => {
          const val = Number(
            metricValues[metric.key as keyof typeof metricValues]
          ) || 0;
          const barWidth = maxVal > 0 ? (Math.abs(val) / maxVal) * 100 : 0;
          const isNegative = val < 0;
          const isPositive = val > 0 && metric.key !== "maxDrawdown";

          return (
            <div
              key={metric.key}
              className="bg-white/[0.03] rounded-xl p-4 hover:bg-white/[0.05] transition-all duration-300"
            >
              <p className="text-xs text-[var(--text-muted)] mb-1.5">
                {metric.name}
              </p>
              <p
                className={`text-lg font-bold mb-2 ${
                  isNegative
                    ? "text-[var(--red)]"
                    : isPositive
                    ? "text-[var(--green)]"
                    : "text-white"
                }`}
              >
                {formatValue(val, metric.format)}
              </p>
              <div className="metric-bar">
                <div
                  className="metric-bar-fill transition-all duration-500"
                  style={{
                    width: `${Math.min(barWidth, 100)}%`,
                    background: isNegative
                      ? "linear-gradient(90deg, #ff4d4d, #ff8c42)"
                      : undefined,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
