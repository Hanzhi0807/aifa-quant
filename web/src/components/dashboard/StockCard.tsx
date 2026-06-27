import { ArrowUp, ArrowDown, Minus } from "lucide-react";

interface StockCardProps {
  rank: number;
  symbol: string;
  name?: string;
  close: number;
  weight?: number;
  score?: number;
  pnlPct?: number;
  variant: "daily" | "weekly";
}

function formatPnl(pct: number | undefined): {
  color: string;
  text: string;
  Icon: typeof ArrowUp;
} {
  if (pct === undefined || pct === 0) {
    return { color: "text-[var(--text-muted)]", text: "持平", Icon: Minus };
  }
  if (pct > 0) {
    return {
      color: "text-[var(--green)]",
      text: `+${(pct * 100).toFixed(1)}%`,
      Icon: ArrowUp,
    };
  }
  return {
    color: "text-[var(--red)]",
    text: `${(pct * 100).toFixed(1)}%`,
    Icon: ArrowDown,
  };
}

export default function StockCard({
  rank,
  symbol,
  name,
  close,
  weight,
  score,
  pnlPct,
  variant,
}: StockCardProps) {
  const pnl = formatPnl(pnlPct);
  const displayName = name || symbol;

  return (
    <div className="stock-card group animate-fade-in">
      {/* Rank badge */}
      <div className="flex items-start justify-between mb-3">
        <div
          className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold ${
            rank <= 3
              ? "bg-[var(--cyan)]/15 text-[var(--cyan)]"
              : "bg-white/5 text-[var(--text-muted)]"
          }`}
        >
          {rank}
        </div>
        {variant === "daily" && (
          <div className={`flex items-center gap-1 text-xs font-medium ${pnl.color}`}>
            <pnl.Icon className="w-3.5 h-3.5" />
            {pnl.text}
          </div>
        )}
        {variant === "weekly" && typeof score === "number" && (
          <div className="text-right">
            <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">
              AI 评分
            </span>
            <p className="text-sm font-bold text-[var(--cyan)]">
              {(score * 100).toFixed(0)}
              <span className="text-[10px] font-normal text-[var(--text-muted)]">分</span>
            </p>
          </div>
        )}
      </div>

      {/* Stock info */}
      <h3 className="text-base font-semibold text-white mb-0.5">{displayName}</h3>
      <p className="text-xs text-[var(--text-muted)] mb-3">{symbol}</p>

      {/* Price */}
      <div className="flex items-baseline gap-1 mb-3">
        <span className="text-lg font-bold text-white">¥{close.toFixed(2)}</span>
        <span className="text-[10px] text-[var(--text-muted)]">最新价</span>
      </div>

      {/* Progress bar */}
      {variant === "daily" && typeof weight === "number" && (
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-[var(--text-muted)]">持仓占比</span>
            <span className="text-xs font-medium text-white">
              {(weight * 100).toFixed(1)}%
            </span>
          </div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.min((weight || 0) * 100, 100)}%`,
                background:
                  "linear-gradient(90deg, var(--cyan), var(--green))",
              }}
            />
          </div>
        </div>
      )}

      {variant === "weekly" && typeof score === "number" && (
        <div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.min((score || 0) * 100, 100)}%`,
                background:
                  "linear-gradient(90deg, var(--cyan), var(--green))",
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
