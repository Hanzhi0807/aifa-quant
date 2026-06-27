import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import GlassCard from "../layout/GlassCard";
import StockCard from "./StockCard";

export interface PickItemView {
  symbol: string;
  name?: string;
  rank: number;
  score?: number;
  close?: number;
  weight?: number;
  action?: "买入" | "持有" | "观望";
  pnlPct?: number;
}

interface PicksListProps {
  title: string;
  subtitle?: string;
  picks: PickItemView[];
  emptyText?: string;
  variant?: "list" | "cards";
  cardVariant?: "daily" | "weekly";
  remark?: string;
}

export default function PicksList({
  title,
  subtitle,
  picks,
  emptyText = "暂无选股信号",
  variant = "list",
  cardVariant = "daily",
  remark,
}: PicksListProps) {
  return (
    <GlassCard title={title} subtitle={subtitle}>
      {remark && (
        <p className="text-xs text-[var(--text-muted)] -mt-3 mb-4 leading-relaxed">{remark}</p>
      )}
      {picks.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-sm text-[var(--text-muted)]">{emptyText}</p>
        </div>
      ) : variant === "cards" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {picks.map((pick) => (
            <StockCard
              key={pick.symbol}
              rank={pick.rank}
              symbol={pick.symbol}
              name={pick.name}
              close={pick.close || 0}
              weight={pick.weight}
              score={pick.score}
              pnlPct={pick.pnlPct}
              variant={cardVariant}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {picks.map((pick) => {
            const Icon =
              pick.action === "买入"
                ? ArrowUpRight
                : pick.action === "持有"
                ? Minus
                : ArrowDownRight;
            const actionColor =
              pick.action === "买入"
                ? "text-[var(--green)] bg-[var(--green)]/10"
                : pick.action === "持有"
                ? "text-[var(--cyan)] bg-[var(--cyan)]/10"
                : "text-[var(--text-muted)] bg-white/5";

            return (
              <div
                key={pick.symbol}
                className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-sm font-semibold text-white">
                    {pick.rank}
                  </div>
                  <div>
                    <p className="text-base font-medium text-white">
                      {pick.name || pick.symbol}
                      <span className="ml-2 text-xs text-[var(--text-muted)] font-normal">
                        {pick.symbol}
                      </span>
                    </p>
                    {typeof pick.close === "number" && (
                      <p className="text-xs text-[var(--text-muted)]">
                        最新收盘价 ¥{pick.close.toFixed(2)}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {typeof pick.score === "number" && (
                    <div className="text-right">
                      <p className="text-xs text-[var(--text-muted)]">AI 得分</p>
                      <p className="text-sm font-medium text-[var(--cyan)]">
                        {pick.score.toFixed(4)}
                      </p>
                    </div>
                  )}
                  {typeof pick.weight === "number" && (
                    <div className="text-right">
                      <p className="text-xs text-[var(--text-muted)]">仓位</p>
                      <p className="text-sm font-medium text-white">
                        {(pick.weight * 100).toFixed(1)}%
                      </p>
                    </div>
                  )}
                  {pick.action && (
                    <span
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${actionColor}`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {pick.action}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </GlassCard>
  );
}
