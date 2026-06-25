import { trpc } from "@/providers/trpc";
import GlassCard from "../layout/GlassCard";

interface MetricItem {
  name: string;
  key: string;
  format: "percent" | "number" | "ratio";
}

const metricsList: MetricItem[] = [
  { name: "Total Return", key: "totalReturn", format: "percent" },
  { name: "Annual Return", key: "annualReturn", format: "percent" },
  { name: "Sharpe Ratio", key: "sharpeRatio", format: "ratio" },
  { name: "Max Drawdown", key: "maxDrawdown", format: "percent" },
  { name: "Volatility", key: "volatility", format: "percent" },
  { name: "Win Rate", key: "winRate", format: "percent" },
  { name: "Profit Factor", key: "profitFactor", format: "ratio" },
  { name: "Benchmark Return", key: "benchmarkTotalReturn", format: "percent" },
  { name: "Excess Return", key: "excessReturn", format: "percent" },
  { name: "Information Ratio", key: "informationRatio", format: "ratio" },
  { name: "Calmar Ratio", key: "calmarRatio", format: "ratio" },
  { name: "Sortino Ratio", key: "sortinoRatio", format: "ratio" },
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
  const { data: metrics, isLoading } =
    trpc.metrics.getByBacktestId.useQuery({ backtestId: 1 });

  if (isLoading) {
    return (
      <GlassCard title="Performance Metrics">
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
    <GlassCard title="Performance Metrics">
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
