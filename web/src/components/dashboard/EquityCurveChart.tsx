import { useState, useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { trpc } from "@/providers/trpc";
import GlassCard from "../layout/GlassCard";

const dateRanges = [
  { label: "1月", days: 30 },
  { label: "3月", days: 90 },
  { label: "6月", days: 180 },
  { label: "1年", days: 365 },
  { label: "全部", days: 0 },
];

interface EquityPoint {
  tradeDate: string;
  normalizedValue: number;
  benchmarkNormalized?: number;
}

interface TooltipPayloadItem {
  value: number;
  dataKey: string;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload) return null;
  return (
    <div className="chart-tooltip">
      <p className="text-xs text-[var(--text-muted)] mb-2">{label}</p>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 mb-1">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-xs text-[var(--text-secondary)]">
            {entry.dataKey === "normalizedValue" ? "组合" : "沪深 300 基准"}:
          </span>
          <span className="text-xs font-semibold text-white">
            {(entry.value * 100).toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  );
}

export default function EquityCurveChart() {
  const [range, setRange] = useState("ALL");

  const { data: equityData, isLoading } = trpc.equityCurve.latest.useQuery();

  const filteredData = useMemo(() => {
    if (!equityData) return [];
    const rangeConfig = dateRanges.find((r) => r.label === range);
    if (!rangeConfig || rangeConfig.days === 0) return equityData;

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - rangeConfig.days);
    return equityData.filter((d) => new Date(d.tradeDate) >= cutoff);
  }, [equityData, range]);

  const hasBenchmark = useMemo(() => {
    return filteredData.some((d) => d.benchmarkNormalized != null);
  }, [filteredData]);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
  };

  return (
    <GlassCard
      title="权益曲线"
      subtitle={hasBenchmark ? "组合净值 vs 沪深 300 基准" : "组合净值"}
      action={
        <div className="flex gap-1">
          {dateRanges.map((r) => (
            <button
              key={r.label}
              onClick={() => setRange(r.label)}
              className={`pill-btn-outline px-3 py-1 text-xs ${
                range === r.label ? "active" : ""
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      }
    >
      {isLoading ? (
        <div className="h-[320px] flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filteredData.length === 0 ? (
        <div className="h-[320px] flex items-center justify-center text-sm text-[var(--text-muted)]">
          暂无权益曲线数据
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart
            data={filteredData as EquityPoint[]}
            margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
          >
            <defs>
              <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00e5a0" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#00e5a0" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="benchmarkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.03)"
            />
            <XAxis
              dataKey="tradeDate"
              tickFormatter={formatDate}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              domain={["auto", "auto"]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: "16px" }}
              formatter={(value: string) => (
                <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "12px" }}>
                  {value === "normalizedValue" ? "组合" : "沪深 300 基准"}
                </span>
              )}
            />
            <Area
              type="monotone"
              dataKey="normalizedValue"
              stroke="#00e5a0"
              strokeWidth={2}
              fill="url(#portfolioGrad)"
              dot={false}
              activeDot={{ r: 4, fill: "#00e5a0", stroke: "#fff", strokeWidth: 2 }}
            />
            {hasBenchmark && (
              <Area
                type="monotone"
                dataKey="benchmarkNormalized"
                stroke="#00d4ff"
                strokeWidth={2}
                strokeDasharray="5 5"
                fill="url(#benchmarkGrad)"
                dot={false}
                activeDot={{ r: 4, fill: "#00d4ff", stroke: "#fff", strokeWidth: 2 }}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </GlassCard>
  );
}
