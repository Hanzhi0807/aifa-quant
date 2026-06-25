import { Link } from "react-router";
import { ArrowLeft, BookOpen } from "lucide-react";
import GlassCard from "@/components/layout/GlassCard";

interface MetricRow {
  name: string;
  meaning: string;
  formula: string;
  reference: string;
  note: string;
}

interface Dimension {
  title: string;
  metrics: MetricRow[];
}

const dimensions: Dimension[] = [
  {
    title: "收益能力",
    metrics: [
      {
        name: "年化收益率",
        meaning: "策略在一年内的平均收益率",
        formula: "(1 + 总收益率)^(252/交易日数) - 1",
        reference: "> 10% 可接受，> 20% 优秀",
        note: "只看收益不看风险，容易误导",
      },
      {
        name: "Alpha",
        meaning: "剔除市场（Beta）影响后的超额收益",
        formula: "策略收益 - Beta × 基准收益",
        reference: "> 0 为正超额，> 10% 优秀",
        note: "Alpha 越高，真实选股/择时能力越强",
      },
    ],
  },
  {
    title: "风险控制",
    metrics: [
      {
        name: "最大回撤",
        meaning: "从高点到低点的最大亏损幅度",
        formula: "权益曲线峰值后最低点的跌幅",
        reference: "< -20% 较稳健，< -30% 可接受，> -40% 风险较高",
        note: "决定持有体验和爆仓风险",
      },
      {
        name: "波动率",
        meaning: "收益率的波动程度，即风险",
        formula: "日收益率标准差 × √252",
        reference: "< 15% 低波动，15%-25% 中等，> 30% 高波动",
        note: "高波动意味着净值起伏大",
      },
    ],
  },
  {
    title: "风险收益比",
    metrics: [
      {
        name: "夏普比率",
        meaning: "单位总风险带来的超额收益",
        formula: "(年化收益 - 无风险利率) / 年化波动率",
        reference: "> 1.0 合格，> 1.5 良好，> 2.0 优秀",
        note: "最常用综合指标，惩罚所有波动",
      },
      {
        name: "索提诺比率",
        meaning: "只惩罚下行波动的风险收益比",
        formula: "(年化收益 - 无风险利率) / 下行波动率",
        reference: "> 1.5 良好，> 2.0 优秀",
        note: "比夏普更关注“亏钱”的风险",
      },
      {
        name: "卡玛比率",
        meaning: "收益与最大回撤的比值",
        formula: "年化收益 / |最大回撤|",
        reference: "> 1.0 良好，> 2.0 优秀",
        note: "特别关注回撤控制",
      },
    ],
  },
  {
    title: "交易质量",
    metrics: [
      {
        name: "胜率",
        meaning: "盈利交易日 / 总交易日",
        formula: "日收益 > 0 的天数占比",
        reference: "> 50% 正向优势，> 55% 较好",
        note: "高胜率不代表最终盈利",
      },
      {
        name: "盈亏比",
        meaning: "总盈利 / 总亏损",
        formula: "盈利日收益之和 / |亏损日收益之和|",
        reference: "> 1.5 良好，> 2.0 优秀",
        note: "赚一次能否覆盖多次亏损",
      },
    ],
  },
  {
    title: "相对基准",
    metrics: [
      {
        name: "信息比率",
        meaning: "单位跟踪误差带来的超额收益",
        formula: "超额收益均值 / 超额收益标准差 × √252",
        reference: "> 0.5 合格，> 1.0 良好，> 1.5 优秀",
        note: "衡量相对基准的稳定超额能力",
      },
      {
        name: "Beta",
        meaning: "策略相对市场的弹性",
        formula: "策略收益对市场收益的回归系数",
        reference: "< 1 低弹性，≈ 1 跟随市场，> 1 高弹性",
        note: "Beta 低说明策略独立于大盘",
      },
    ],
  },
];

const aifaExample = [
  { metric: "年化收益率", value: "39.91%", eval: "优秀" },
  { metric: "最大回撤", value: "-41.27%", eval: "偏大，需警惕" },
  { metric: "夏普比率", value: "2.085", eval: "优秀" },
  { metric: "日胜率", value: "50.12%", eval: "接近随机，靠盈亏比取胜" },
  { metric: "信息比率", value: "1.971", eval: "优秀" },
  { metric: "Beta", value: "较低", eval: "较好" },
];

const judgmentRules = [
  "高收益 + 低回撤 + 高夏普 → 理想策略，重点关注是否过拟合。",
  "高收益 + 高回撤 + 低夏普 → 收益来自冒险，实盘容易扛不住。",
  "低收益 + 低回撤 + 中等夏普 → 稳健策略，适合保守资金。",
  "高胜率 + 低盈亏比 → 赚小钱亏大钱，长期可能归零。",
  "低胜率 + 高盈亏比 → 趋势型策略，需要忍受连续亏损。",
  "信息比率低但夏普高 → 收益主要来自市场 Beta，而非真实 Alpha。",
];

export default function Metrics() {
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
            <h1 className="text-2xl font-bold text-white">指标说明</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              核心回测指标含义、参考值与“好策略”判断标准
            </p>
          </div>
        </div>

        {/* Dimensions */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {dimensions.map((dim) => (
            <GlassCard key={dim.title} title={dim.title}>
              <div className="space-y-4">
                {dim.metrics.map((m) => (
                  <div
                    key={m.name}
                    className="bg-white/[0.03] rounded-xl p-4 hover:bg-white/[0.05] transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-sm font-semibold text-white">
                        {m.name}
                      </h4>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] mb-2">
                      {m.meaning}
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-[var(--text-muted)]">公式：</span>
                        <span className="text-[var(--cyan)] font-mono">
                          {m.formula}
                        </span>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)]">参考值：</span>
                        <span className="text-[var(--green)]">{m.reference}</span>
                      </div>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-2">
                      💡 {m.note}
                    </p>
                  </div>
                ))}
              </div>
            </GlassCard>
          ))}
        </div>

        {/* Good strategy criteria */}
        <GlassCard title="什么叫“好的策略”？">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-semibold text-white mb-3">
                基础门槛
              </h4>
              <ul className="space-y-2 text-xs text-[var(--text-secondary)]">
                <li>年化收益率 &gt; 10%</li>
                <li>最大回撤 &lt; -30%</li>
                <li>夏普比率 &gt; 1.0</li>
                <li>信息比率 &gt; 0.5</li>
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white mb-3">
                优秀策略画像
              </h4>
              <ul className="space-y-2 text-xs text-[var(--text-secondary)]">
                <li>年化收益率 &gt; 20%，Alpha &gt; 10%</li>
                <li>最大回撤 &lt; -20%，波动率 &lt; 20%</li>
                <li>夏普 &gt; 1.5，索提诺 &gt; 2.0，卡玛 &gt; 2.0</li>
                <li>胜率 &gt; 55%，盈亏比 &gt; 2.0</li>
                <li>信息比率 &gt; 1.0，Beta &lt; 1.0</li>
              </ul>
            </div>
          </div>

          <div className="mt-6 pt-6 border-t border-white/5">
            <h4 className="text-sm font-semibold text-white mb-3">
              综合判断口诀
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {judgmentRules.map((rule, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-xs text-[var(--text-secondary)]"
                >
                  <BookOpen className="w-3.5 h-3.5 text-[var(--cyan)] flex-shrink-0 mt-0.5" />
                  <span>{rule}</span>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>

        {/* AifaQuant example */}
        <GlassCard
          title="AifaQuant 当前表现对照"
          subtitle="2020–2024 上证 50 全因子滚动回测（已做正则化 + 特征筛选）"
        >
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                    指标
                  </th>
                  <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">
                    数值
                  </th>
                  <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3">
                    评价
                  </th>
                </tr>
              </thead>
              <tbody>
                {aifaExample.map((row) => (
                  <tr
                    key={row.metric}
                    className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="py-3 pr-4 text-sm text-white">
                      {row.metric}
                    </td>
                    <td className="py-3 pr-4 text-sm text-[var(--cyan)] font-mono">
                      {row.value}
                    </td>
                    <td className="py-3 text-xs text-[var(--text-secondary)]">
                      {row.eval}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-4">
            ⚠️ 以上为回测结果，不代表实盘表现。最大回撤超过 -40%
            说明策略在极端行情下仍会承受较大压力，实盘前需要进一步风控优化。
          </p>
        </GlassCard>
      </div>
    </div>
  );
}
