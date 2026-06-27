import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { trpc } from "@/providers/trpc";
import GlassCard from "../layout/GlassCard";

interface TooltipPayloadItem {
  value: number;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="text-xs text-[var(--text-muted)] mb-1">{label}</p>
      <p className="text-sm font-semibold text-white">
        {(payload[0].value * 100).toFixed(2)}%
      </p>
    </div>
  );
}

export default function MiniEquityChart() {
  const { data: equityData, isLoading } =
    trpc.equityCurve.getByBacktestId.useQuery({ backtestId: 1 });

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  return (
    <GlassCard title="近期走势" subtitle="模拟盘累计净值">
      <div className="h-[180px]">
        {isLoading ? (
          <div className="h-full bg-white/5 rounded-xl animate-pulse" />
        ) : !equityData || equityData.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <p className="text-sm text-[var(--text-muted)]">暂无净值数据</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={equityData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--cyan)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--cyan)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="tradeDate"
                tickFormatter={formatDate}
                tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                minTickGap={30}
              />
              <YAxis
                tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                domain={["auto", "auto"]}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="normalizedValue"
                stroke="var(--cyan)"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorValue)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </GlassCard>
  );
}
