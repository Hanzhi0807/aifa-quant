import { Link } from "react-router";
import { ArrowLeft, Cpu, FileCode } from "lucide-react";
import { trpc } from "@/providers/trpc";
import GlassCard from "@/components/layout/GlassCard";
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
import { useState } from "react";

interface Model {
  id: number;
  name: string;
  path: string;
  featureColumns: string[];
  trainStart: string | null;
  trainEnd: string | null;
  createdAt: Date | string;
}

interface FactorItem {
  id: number;
  modelId: number;
  factorName: string;
  importance: number;
  rank: number;
}

function FactorTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: FactorItem }> }) {
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

export default function Models() {
  const { data: models, isLoading: modelsLoading } = trpc.model.list.useQuery();
  const [selectedModel, setSelectedModel] = useState<number>(1);

  const { data: factors, isLoading: factorsLoading } =
    trpc.factor.getByModelId.useQuery({ modelId: selectedModel, limit: 20 });

  const modelList = (models || []) as Model[];
  const factorList = (factors || []) as FactorItem[];
  const sortedFactors = factorList.slice().sort((a, b) => b.importance - a.importance);
  const maxImportance = sortedFactors[0]?.importance || 1;

  const selectedModelData = modelList.find((m) => m.id === selectedModel);

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
            <h1 className="text-2xl font-bold text-white">模型</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              模型注册表与因子重要性分析
            </p>
          </div>
        </div>

        {/* Model Registry Table */}
        <GlassCard title="模型注册表">
          {modelsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-16 bg-white/5 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      名称
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      路径
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      特征数
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                      训练区间
                    </th>
                    <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3">
                      创建时间
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {modelList.map((model) => (
                    <tr
                      key={model.id}
                      onClick={() => setSelectedModel(model.id)}
                      className={`border-b border-white/[0.03] cursor-pointer transition-all duration-200 ${
                        selectedModel === model.id
                          ? "bg-[var(--cyan)]/5"
                          : "hover:bg-white/[0.02]"
                      }`}
                    >
                      <td className="py-3.5 pr-4">
                        <div className="flex items-center gap-2">
                          <Cpu className="w-4 h-4 text-[var(--cyan)]" />
                          <span className="text-sm font-medium text-white">
                            {model.name}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 pr-4">
                        <div className="flex items-center gap-2">
                          <FileCode className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                          <span className="text-xs text-[var(--text-secondary)] font-mono">
                            {model.path}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className="text-sm text-[var(--text-secondary)]">
                          {model.featureColumns?.length || 0} 个特征
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className="text-xs text-[var(--text-secondary)]">
                          {model.trainStart && model.trainEnd
                            ? `${model.trainStart} ~ ${model.trainEnd}`
                            : "-"}
                        </span>
                      </td>
                      <td className="py-3.5">
                        <span className="text-xs text-[var(--text-muted)]">
                          {new Date(model.createdAt).toLocaleDateString()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>

        {/* Feature Importance Detail */}
        {selectedModelData && (
          <GlassCard
            title="因子重要性"
            subtitle={`${selectedModelData.name} — ${selectedModelData.featureColumns?.length || 0} 个特征`}
          >
            {factorsLoading ? (
              <div className="h-[400px] flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart
                    data={sortedFactors}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.03)"
                      horizontal={false}
                    />
                    <XAxis
                      type="number"
                      tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
                      tick={{
                        fill: "rgba(255,255,255,0.4)",
                        fontSize: 11,
                      }}
                      axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="factorName"
                      tick={{
                        fill: "rgba(255,255,255,0.6)",
                        fontSize: 11,
                      }}
                      axisLine={false}
                      tickLine={false}
                      width={95}
                    />
                    <Tooltip content={<FactorTooltip />} cursor={false} />
                    <Bar
                      dataKey="importance"
                      radius={[0, 4, 4, 0]}
                      barSize={16}
                    >
                      {sortedFactors.map((entry, index) => {
                        const opacity =
                          0.4 + (entry.importance / maxImportance) * 0.6;
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

                {/* Feature List */}
                <div className="max-h-[400px] overflow-y-auto">
                  <h4 className="text-sm font-semibold text-white mb-3">
                    因子详情
                  </h4>
                  <div className="space-y-2">
                    {sortedFactors.map((factor, index) => (
                      <div
                        key={factor.id}
                        className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/[0.03] transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                              index < 3
                                ? "bg-[var(--green)]/20 text-[var(--green)]"
                                : "bg-white/5 text-[var(--text-muted)]"
                            }`}
                          >
                            {factor.rank}
                          </span>
                          <span className="text-sm text-[var(--text-secondary)]">
                            {factor.factorName}
                          </span>
                        </div>
                        <span className="text-sm font-mono text-white">
                          {(factor.importance * 100).toFixed(3)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </GlassCard>
        )}
      </div>
    </div>
  );
}
