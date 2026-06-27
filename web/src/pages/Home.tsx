import { useState } from "react";
import { Calendar, Sparkles, ShieldAlert, Clock } from "lucide-react";
import { trpc } from "@/providers/trpc";
import GlassCard from "@/components/layout/GlassCard";
import PicksList from "@/components/dashboard/PicksList";
import PortfolioSummary from "@/components/dashboard/PortfolioSummary";
import MiniEquityChart from "@/components/dashboard/MiniEquityChart";
import type { PickItemView } from "@/components/dashboard/PicksList";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"daily" | "weekly">("daily");

  const { data: portfolio } = trpc.portfolio.snapshot.useQuery();
  const { data: dailyPicks } = trpc.picks.daily.useQuery();
  const { data: weeklyPicks } = trpc.weeklyPicks.latest.useQuery();

  const latestDate = dailyPicks?.tradeDate || weeklyPicks?.predictionDate || "-";

  const dailyItems: PickItemView[] =
    dailyPicks?.picks.map((p) => ({
      symbol: p.symbol,
      rank: p.rank,
      close: p.latestClose,
      weight: p.weight,
      action: "持有",
    })) || [];

  const weeklyItems: PickItemView[] =
    weeklyPicks?.picks.map((p) => ({
      symbol: p.symbol,
      rank: p.rank,
      score: p.score,
      close: p.close,
      action: "买入",
    })) || [];

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1200px] mx-auto space-y-8">
        {/* Hero */}
        <div className="animate-fade-in space-y-2">
          <div className="flex items-center gap-2 text-[var(--cyan)]">
            <Sparkles className="w-5 h-5" />
            <span className="text-sm font-medium">AI 选股信号</span>
          </div>
          <h1 className="text-3xl font-bold text-white">今日 AI 推荐持仓</h1>
          <p className="text-[var(--text-secondary)] max-w-2xl">
            基于 LightGBM 模型对沪深 300 成分股打分，每日收盘后生成下一交易日的持仓建议。
            最小时间维度为日线，周度版本为每周一次的调仓视角。
          </p>
          <div className="flex items-center gap-4 text-sm text-[var(--text-muted)] pt-1">
            <span className="flex items-center gap-1.5">
              <Calendar className="w-4 h-4" />
              最新信号日期：{latestDate}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="w-4 h-4" />
              更新频率：交易日 15:30 后
            </span>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="flex items-start gap-3 p-4 rounded-xl bg-[var(--orange)]/10 border border-[var(--orange)]/20">
          <ShieldAlert className="w-5 h-5 text-[var(--orange)] shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-[var(--orange)] font-medium">风险提示</p>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              以下股票由量化模型根据历史数据生成，仅供学习与研究参考，不构成任何投资建议。
              股市有风险，入市需谨慎。请勿直接据此进行实盘交易。
            </p>
          </div>
        </div>

        {/* Portfolio + Mini Chart */}
        {portfolio && (
          <PortfolioSummary
            cash={portfolio.cash}
            marketValue={portfolio.marketValue}
            totalValue={portfolio.totalValue}
            positionsCount={portfolio.positionsCount}
            dailyPnl={portfolio.dailyPnl}
            dailyPnlPct={portfolio.dailyPnlPct}
            tradeDate={portfolio.tradeDate}
          />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {/* Tabs */}
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => setActiveTab("daily")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  activeTab === "daily"
                    ? "bg-white/10 text-white"
                    : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
                }`}
              >
                日度策略
              </button>
              <button
                onClick={() => setActiveTab("weekly")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  activeTab === "weekly"
                    ? "bg-white/10 text-white"
                    : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
                }`}
              >
                周度策略
              </button>
            </div>

            {activeTab === "daily" ? (
              <PicksList
                title="日度持仓名单"
                subtitle={`${dailyPicks?.strategy || "AI 日度选股"} · ${dailyPicks?.tradeDate || "-"}`}
                picks={dailyItems}
                emptyText="暂无日度持仓，请先运行 paper-trade run"
              />
            ) : (
              <PicksList
                title="周度选股名单"
                subtitle={`每周 AI 选股报告 · ${weeklyPicks?.predictionDate || "-"}`}
                picks={weeklyItems}
                emptyText="暂无周度选股，请先运行 weekly-report"
              />
            )}
          </div>

          <div className="space-y-6">
            <MiniEquityChart />
            <GlassCard title="策略说明" subtitle="给普通投资者">
              <ul className="space-y-3 text-sm text-[var(--text-secondary)]">
                <li className="flex gap-2">
                  <span className="text-[var(--cyan)]">•</span>
                  <span>
                    <strong className="text-white">日度策略</strong>：每 5 个交易日审视一次持仓，模型自动替换掉排名靠后的股票。
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-[var(--cyan)]">•</span>
                  <span>
                    <strong className="text-white">周度策略</strong>：以周为视角，筛选未来一周模型认为上涨概率最高的 10 只股票。
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-[var(--cyan)]">•</span>
                  <span>
                    想看模型原理、因子贡献、回测曲线，请进入“策略原理”页签。
                  </span>
                </li>
              </ul>
            </GlassCard>
          </div>
        </div>
      </div>
    </div>
  );
}
