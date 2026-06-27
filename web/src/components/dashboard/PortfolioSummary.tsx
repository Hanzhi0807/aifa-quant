import { Wallet, Coins, Briefcase, TrendingUp, TrendingDown } from "lucide-react";
import KPICard from "./KPICard";

interface PortfolioSummaryProps {
  cash: number;
  marketValue: number;
  totalValue: number;
  positionsCount: number;
  dailyPnl: number;
  dailyPnlPct: number;
  tradeDate: string;
}

export default function PortfolioSummary({
  cash,
  marketValue,
  totalValue,
  positionsCount,
  dailyPnl,
  dailyPnlPct,
  tradeDate,
}: PortfolioSummaryProps) {
  const pnlPositive = dailyPnl >= 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">模拟账户概览</h2>
        <span className="text-xs text-[var(--text-muted)]">
          数据截至 {tradeDate}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="总资产"
          value={totalValue.toLocaleString("zh-CN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
          prefix="¥"
          icon={Wallet}
          variant="cyan"
        />
        <KPICard
          label="持仓市值"
          value={marketValue.toLocaleString("zh-CN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
          prefix="¥"
          icon={Briefcase}
        />
        <KPICard
          label="现金"
          value={cash.toLocaleString("zh-CN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
          prefix="¥"
          icon={Coins}
        />
        <KPICard
          label="当日盈亏"
          value={`${(Math.abs(dailyPnlPct) * 100).toFixed(2)}%`}
          prefix={pnlPositive ? "+" : "-"}
          trend={pnlPositive ? "up" : "down"}
          trendValue={`¥${Math.abs(dailyPnl).toLocaleString("zh-CN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`}
          icon={pnlPositive ? TrendingUp : TrendingDown}
          variant={pnlPositive ? "green" : "default"}
        />
      </div>

      <p className="text-xs text-[var(--text-muted)]">
        当前持有 {positionsCount} 只股票，以上金额为模拟盘虚拟资金，仅供策略效果参考。
      </p>
    </div>
  );
}
