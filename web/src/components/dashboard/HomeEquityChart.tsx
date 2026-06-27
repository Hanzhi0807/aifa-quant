import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import GlassCard from "../layout/GlassCard";

interface EquityPoint {
  tradeDate: string;
  normalizedValue: number;
  benchmarkNormalized?: number;
}

interface Props {
  profile: string;
  equityData: EquityPoint[];
}

function CustomTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { value: number; dataKey: string; color: string }[];
  label?: string;
}) {
  if (!active || !payload) return null;
  return (
    <div className="chart-tooltip">
      <p className="text-xs text-[var(--text-muted)] mb-2">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 mb-1">
          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-xs text-[var(--text-secondary)]">
            {entry.dataKey === "normalizedValue" ? "组合" : "基准"}:
          </span>
          <span className="text-xs font-semibold text-white">
            {(entry.value * 100).toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  );
}

export default function HomeEquityChart({ profile, equityData }: Props) {
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
  };

  const dateRange =
    equityData.length >= 2
      ? `${equityData[0].tradeDate.slice(0, 7)} ~ ${equityData[equityData.length - 1].tradeDate}`
      : "";

  return (
    <GlassCard title="" subtitle={dateRange || "暂无数据"}>
      <div className="h-[220px]">
        {equityData.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <p className="text-sm text-[var(--text-muted)]">暂无净值数据</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart key={profile} data={equityData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="homeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00e5a0" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#00e5a0" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="tradeDate" tickFormatter={formatDate}
                tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                axisLine={false} tickLine={false} minTickGap={40} />
              <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                axisLine={false} tickLine={false} domain={["auto", "auto"]} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="normalizedValue" stroke="#00e5a0"
                strokeWidth={2} fill="url(#homeGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </GlassCard>
  );
}
