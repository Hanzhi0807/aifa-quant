import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { trpc } from "@/providers/trpc";
import GlassCard from "../layout/GlassCard";

interface TooltipPayloadItem {
  value: number;
  payload: {
    factorName: string;
    importance: number;
  };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p className="text-xs text-[var(--text-muted)] mb-1">{data.factorName}</p>
      <p className="text-sm font-semibold text-white">
        {(data.importance * 100).toFixed(3)}%
      </p>
    </div>
  );
}

export default function FactorChart() {
  const { data: factors, isLoading } = trpc.factor.getByModelId.useQuery({
    modelId: 1,
    limit: 10,
  });

  // Sort by importance descending
  const sortedFactors = (factors || [])
    .slice()
    .sort((a, b) => b.importance - a.importance);

  const maxImportance = sortedFactors[0]?.importance || 1;

  return (
    <GlassCard title="Top Factor Importances" subtitle="LightGBM Rolling Model">
      {isLoading ? (
        <div className="h-[280px] flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={sortedFactors}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.03)"
              horizontal={false}
            />
            <XAxis
              type="number"
              tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="factorName"
              tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={75}
            />
            <Tooltip content={<CustomTooltip />} cursor={false} />
            <Bar dataKey="importance" radius={[0, 4, 4, 0]} barSize={20}>
              {sortedFactors.map((entry, index) => {
                const opacity = 0.4 + (entry.importance / maxImportance) * 0.6;
                return (
                  <Cell
                    key={index}
                    fill={`rgba(0, 229, 160, ${opacity})`}
                  />
                );
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </GlassCard>
  );
}
