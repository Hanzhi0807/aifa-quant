import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { trpc } from "@/providers/trpc";
import PicksList from "@/components/dashboard/PicksList";
import HomeEquityChart from "@/components/dashboard/HomeEquityChart";
import SimpleFAQ from "@/components/dashboard/SimpleFAQ";
import type { PickItemView } from "@/components/dashboard/PicksList";

const PROFILES = [
  { id: "aggressive", label: "激进型", desc: "高收益高波动" },
  { id: "balanced", label: "均衡型", desc: "攻守兼备" },
  { id: "conservative", label: "稳健型", desc: "低回撤分散" },
  { id: "growth", label: "成长型", desc: "高成长潜力" },
  { id: "value", label: "价值型", desc: "低估值优先" },
];

const faqItems = [
  {
    question: "不同策略有什么区别？",
    answer:
      "激进型集中持有 5 只股票追求高收益；均衡型持有 8 只兼顾收益与风险；稳健型分散持有 12 只严格控制回撤；成长型聚焦高 ROE 成长股；价值型偏好低估值股票。最终分数会按各 profile 的 factor_weights 加权，因此持仓会不同。",
  },
  {
    question: "多久调仓一次？",
    answer:
      "所有策略每天收盘后审视一次持仓：盘中不做调整，盘后使用当日收盘价计算信号和风控制度，生成次日开盘可执行的目标持仓。如果大盘处于震荡状态，策略只卖不买，避免反复交易损耗。",
  },
  {
    question: "这个策略靠谱吗？",
    answer:
      "策略基于上百个量化因子和机器学习模型，在历史回测中表现优异。但历史表现不代表未来收益，股市有风险，投资需谨慎。",
    link: { text: "了解技术细节", to: "/models" },
  },
  {
    question: "AI 是怎么选股的？",
    answer:
      "模型综合技术面趋势、动量、波动率、基本面估值等上百个因子，使用 LightGBM 机器学习算法对沪深 300 + 中证 500 + 中证 1000 约 1800 只股票打分，再按 profile 偏好加权，选出上涨概率最高的股票。",
    link: { text: "查看因子分析", to: "/models" },
  },
];

interface RiskPosition {
  symbol: string;
  name: string;
  shares: number;
  costBasis: number;
  currentPrice: number;
  stopLossPrice: number | null;
  takeProfitPrice: number | null;
  atr: number | null;
  unrealizedPnlPct: number;
}

interface OrderRow {
  orderId: string;
  tradeDate: string;
  symbol: string;
  side: string;
  quantity: number;
  fillPrice: number;
  commission: number;
  stampDuty: number;
  status: string;
}

export default function Home() {
  const [profile, setProfile] = useState("balanced");
  const [activeTab, setActiveTab] = useState<"holdings" | "risk" | "orders" | "about">("holdings");
  const utils = trpc.useUtils();

  const { data: strategies } = trpc.strategies.list.useQuery(undefined, {
    refetchInterval: 60_000,
  });
  const { data: picks } = trpc.strategies.getPicks.useQuery({ profile });
  const { data: equity } = trpc.strategies.getEquity.useQuery({ profile });
  const { data: riskStatus } = trpc.risk.status.useQuery({ profile }, {
    refetchInterval: 120_000,
  });
  const { data: orders } = trpc.orders.list.useQuery({ profile }, {
    refetchInterval: 120_000,
  });
  const { data: profileConfig } = trpc.strategies.getProfile.useQuery({ profile });

  const refreshMutation = trpc.refresh.run.useMutation({
    onSuccess: async (result) => {
      if (result.success) {
        toast.success("数据刷新完成", { description: result.message });
        await utils.strategies.list.invalidate();
        await utils.strategies.getPicks.invalidate();
        await utils.strategies.getEquity.invalidate();
        await utils.risk.status.invalidate();
        await utils.orders.list.invalidate();
      } else {
        toast.error("刷新失败", { description: result.message });
      }
    },
    onError: (err) => toast.error("刷新失败", { description: err.message }),
  });

  const currentStrategy = strategies?.find((s) => s.id === profile);
  const pickItems: PickItemView[] =
    picks?.picks
      .map((p) => ({
        symbol: p.symbol,
        name: p.name,
        rank: p.rank,
        close: p.close,
        weight: p.weight,
        action: "持有" as const,
        pnlPct: p.pnlPct,
      }))
      .sort((a, b) => (b.weight || 0) - (a.weight || 0))
      .map((p, idx) => ({ ...p, rank: idx + 1 })) || [];

  const firstEq = equity?.[0];
  const lastEq = equity?.[equity.length - 1];
  const eqReturn =
    firstEq && lastEq
      ? lastEq.normalizedValue / firstEq.normalizedValue - 1
      : null;
  const csiReturn =
    firstEq && lastEq && firstEq.csi300Normalized != null && lastEq.csi300Normalized != null
      ? lastEq.csi300Normalized / firstEq.csi300Normalized - 1
      : null;
  const sseReturn =
    firstEq && lastEq && firstEq.sseNormalized != null && lastEq.sseNormalized != null
      ? lastEq.sseNormalized / firstEq.sseNormalized - 1
      : null;

  const bestReturn = Math.max(
    ...(strategies || []).map((s) => s.totalReturn || 0),
    0.01,
  );

  const tabs = [
    { key: "holdings", label: "当前持仓" },
    { key: "risk", label: "风控详情" },
    { key: "orders", label: "调仓记录" },
    { key: "about", label: "策略说明" },
  ] as const;

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1200px] mx-auto space-y-8">
        {/* ===== Hero ===== */}
        <section className="animate-fade-in space-y-5">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">
              AI 智能选股
            </h1>
            <p className="text-[var(--text-secondary)] max-w-2xl">
              选择适合你的策略风格，查看 AI 推荐的精选股票。每个策略独立运作，有不同的选股侧重和风控参数。盘中不做调整，盘后根据当日收盘价生成次日目标持仓。
            </p>
          </div>

          {/* Strategy selector */}
          <div className="flex flex-wrap items-center gap-2">
            {PROFILES.map((p) => (
              <button
                key={p.id}
                onClick={() => setProfile(p.id)}
                className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  profile === p.id
                    ? "bg-[var(--cyan)]/15 text-[var(--cyan)] border border-[var(--cyan)]/20"
                    : "bg-white/5 text-[var(--text-muted)] hover:text-white hover:bg-white/10 border border-transparent"
                }`}
              >
                <span>{p.label}</span>
                <span className="ml-1.5 text-[10px] opacity-60">{p.desc}</span>
              </button>
            ))}
          </div>

          {/* Meta */}
          <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-muted)]">
            <span>最新日期：{currentStrategy?.tradeDate || "-"}</span>
            {riskStatus && (
              <span
                className={`px-2 py-0.5 rounded-full text-xs ${
                  riskStatus.marketTrend === "trending"
                    ? "bg-[var(--green)]/10 text-[var(--green)]"
                    : "bg-[var(--orange)]/10 text-[var(--orange)]"
                }`}
              >
                {riskStatus.marketTrend === "trending" ? "趋势市" : "震荡市"}
              </span>
            )}
            <button
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
              className="text-[var(--cyan)] hover:underline disabled:opacity-50 ml-auto"
            >
              {refreshMutation.isPending ? "刷新中..." : "手动刷新"}
            </button>
          </div>
        </section>

        {/* Risk disclaimer */}
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <ShieldAlert className="w-3.5 h-3.5 text-[var(--orange)] flex-shrink-0" />
          以下为 AI 模型分析结果，仅供学习参考，不构成投资建议。持仓每日收盘后调整，盘中不做交易。
        </div>

        {/* ===== Strategy Comparison ===== */}
        {strategies && strategies.length > 0 && (
          <section>
            <h2 className="text-lg font-bold text-white mb-3">策略对比</h2>
            <div className="grid grid-cols-5 gap-3">
              {strategies.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setProfile(s.id)}
                  className={`rounded-xl p-3 text-center transition-all cursor-pointer ${
                    profile === s.id
                      ? "bg-[var(--cyan)]/10 border border-[var(--cyan)]/20"
                      : "bg-white/[0.03] border border-transparent hover:bg-white/[0.05]"
                  }`}
                >
                  <p className="text-xs font-medium text-white mb-1">
                    {s.name}
                  </p>
                  <p className="text-lg font-bold text-[var(--green)]">
                    {s.totalReturn != null
                      ? `${(s.totalReturn >= 0 ? "+" : "")}${(s.totalReturn * 100).toFixed(0)}%`
                      : "-"}
                  </p>
                  <div className="h-1 bg-white/5 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className="h-full bg-[var(--green)]/40 rounded-full"
                      style={{
                        width: `${Math.min(((s.totalReturn || 0) / bestReturn) * 100, 100)}%`,
                      }}
                    />
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] mt-1">
                    {s.pickCount}只 · {s.name}
                  </p>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ===== Selected Strategy Detail Tabs ===== */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-bold text-white">
              {currentStrategy?.name || "均衡型"}
              <span className="text-sm font-normal text-[var(--text-muted)] ml-2">
                {currentStrategy?.description}
              </span>
            </h2>
            <div className="flex items-center gap-1 bg-white/5 p-1 rounded-lg">
              {tabs.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    activeTab === t.key
                      ? "bg-[var(--cyan)]/15 text-[var(--cyan)]"
                      : "text-[var(--text-muted)] hover:text-white"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {activeTab === "holdings" && (
            <PicksList
              title=""
              picks={pickItems}
              emptyText="暂无持仓，请先刷新数据"
              variant="cards"
              cardVariant="daily"
            />
          )}

          {activeTab === "risk" && (
            <div className="glass-card rounded-2xl p-5">
              {riskStatus?.positions && riskStatus.positions.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/5 text-[var(--text-muted)] text-xs">
                        <th className="text-left py-2 pr-4">股票</th>
                        <th className="text-right py-2 pr-4">持仓股数</th>
                        <th className="text-right py-2 pr-4">成本价</th>
                        <th className="text-right py-2 pr-4">最新价</th>
                        <th className="text-right py-2 pr-4">浮盈亏</th>
                        <th className="text-right py-2 pr-4">ATR</th>
                        <th className="text-right py-2 pr-4">止损价</th>
                        <th className="text-right py-2">止盈价</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(riskStatus.positions as RiskPosition[]).map((pos) => (
                        <tr key={pos.symbol} className="border-b border-white/[0.03]">
                          <td className="py-3 pr-4">
                            <span className="text-white font-medium">{pos.name || pos.symbol}</span>
                            <span className="ml-2 text-xs text-[var(--text-muted)]">{pos.symbol}</span>
                          </td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">{pos.shares}</td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{pos.costBasis.toFixed(2)}</td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{pos.currentPrice.toFixed(2)}</td>
                          <td className={`text-right py-3 pr-4 ${pos.unrealizedPnlPct >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                            {(pos.unrealizedPnlPct * 100).toFixed(1)}%
                          </td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">
                            {pos.atr != null ? pos.atr.toFixed(2) : "-"}
                          </td>
                          <td className="text-right py-3 pr-4 text-[var(--red)]">
                            {pos.stopLossPrice != null ? pos.stopLossPrice.toFixed(2) : "-"}
                          </td>
                          <td className="text-right py-3 text-[var(--green)]">
                            {pos.takeProfitPrice != null ? pos.takeProfitPrice.toFixed(2) : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">暂无风控数据</p>
              )}
              <p className="text-xs text-[var(--text-muted)] mt-4">
                仓位按 target_risk / (N × ATR) 计算，默认 N = 2。止损/止盈价基于最新 ATR 动态计算，盘中不触发调仓。
              </p>
            </div>
          )}

          {activeTab === "orders" && (
            <div className="glass-card rounded-2xl p-5">
              {orders && orders.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/5 text-[var(--text-muted)] text-xs">
                        <th className="text-left py-2 pr-4">日期</th>
                        <th className="text-left py-2 pr-4">股票</th>
                        <th className="text-left py-2 pr-4">方向</th>
                        <th className="text-right py-2 pr-4">数量</th>
                        <th className="text-right py-2 pr-4">成交价</th>
                        <th className="text-right py-2 pr-4">佣金</th>
                        <th className="text-right py-2 pr-4">印花税</th>
                        <th className="text-left py-2">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(orders as OrderRow[]).map((o) => (
                        <tr key={o.orderId} className="border-b border-white/[0.03]">
                          <td className="py-3 pr-4 text-[var(--text-secondary)]">{o.tradeDate}</td>
                          <td className="py-3 pr-4 text-white font-medium">{o.symbol}</td>
                          <td className="py-3 pr-4">
                            <span className={`px-2 py-0.5 rounded-full text-xs ${o.side === "BUY" ? "bg-[var(--green)]/10 text-[var(--green)]" : "bg-[var(--red)]/10 text-[var(--red)]"}`}>
                              {o.side === "BUY" ? "买入" : "卖出"}
                            </span>
                          </td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">{o.quantity}</td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{o.fillPrice.toFixed(2)}</td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{o.commission.toFixed(2)}</td>
                          <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{o.stampDuty.toFixed(2)}</td>
                          <td className="py-3 text-[var(--text-secondary)]">{o.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">暂无调仓记录</p>
              )}
            </div>
          )}

          {activeTab === "about" && profileConfig && (
            <div className="glass-card rounded-2xl p-5 space-y-4">
              <div>
                <h3 className="text-white font-semibold mb-1">{profileConfig.name}</h3>
                <p className="text-sm text-[var(--text-secondary)]">{profileConfig.description}</p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">目标持仓数</p>
                  <p className="text-white font-medium">{profileConfig.topK} 只</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">单仓风险预算</p>
                  <p className="text-white font-medium">{(profileConfig.targetRiskPct * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">止损 ATR 倍数</p>
                  <p className="text-white font-medium">{profileConfig.atrStopLoss}×</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3">
                  <p className="text-xs text-[var(--text-muted)]">止盈 ATR 倍数</p>
                  <p className="text-white font-medium">{profileConfig.atrTakeProfit}×</p>
                </div>
              </div>
              {Object.keys(profileConfig.factorWeights).length > 0 && (
                <div>
                  <p className="text-xs text-[var(--text-muted)] mb-2">因子权重偏好（factor_weights）</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(profileConfig.factorWeights).map(([k, v]) => (
                      <span key={k} className="px-2 py-1 bg-white/5 rounded-md text-xs text-[var(--text-secondary)]">
                        {k}: {Number(v).toFixed(1)}×
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <p className="text-xs text-[var(--text-muted)]">
                最终分数 = 0.7 × 模型分 + 0.3 × profile 因子偏好分。因此不同 profile 会从同一批股票中选出不同标的。
              </p>
            </div>
          )}
        </section>

        {/* ===== Performance ===== */}
        <section>
          <h2 className="text-lg font-bold text-white mb-3">
            历史表现 · {currentStrategy?.name || "均衡型"}
          </h2>
          <HomeEquityChart profile={profile} equityData={equity || []} />
          {eqReturn != null && (
            <div className="grid grid-cols-4 gap-4 mt-3">
              <div className="text-center">
                <p className="text-xs text-[var(--text-muted)]">组合收益</p>
                <p className={`text-sm font-bold ${eqReturn >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                  {eqReturn >= 0 ? "+" : ""}
                  {(eqReturn * 100).toFixed(1)}%
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--text-muted)]">沪深300</p>
                <p className={`text-sm font-bold ${(csiReturn ?? 0) >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                  {csiReturn != null
                    ? `${csiReturn >= 0 ? "+" : ""}${(csiReturn * 100).toFixed(1)}%`
                    : "-"}
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--text-muted)]">上证指数</p>
                <p className={`text-sm font-bold ${(sseReturn ?? 0) >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                  {sseReturn != null
                    ? `${sseReturn >= 0 ? "+" : ""}${(sseReturn * 100).toFixed(1)}%`
                    : "-"}
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--text-muted)]">总资产</p>
                <p className="text-sm font-bold text-white">
                  ¥{(currentStrategy?.totalValue || 0).toLocaleString()}
                </p>
              </div>
            </div>
          )}
        </section>

        {/* ===== FAQ ===== */}
        <section>
          <SimpleFAQ items={faqItems} />
        </section>

        <footer className="text-center pt-6 border-t border-white/5">
          <p className="text-xs text-[var(--text-muted)]">
            AifaQuant — AI 驱动的 A 股量化策略平台。历史表现不代表未来收益。
          </p>
        </footer>
      </div>
    </div>
  );
}
