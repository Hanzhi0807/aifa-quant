import { createRouter, publicQuery } from "../middleware";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

interface NavRow {
  trade_date: Date;
  cash: number;
  market_value: number;
  total_value: number;
}

export interface PortfolioSnapshot {
  tradeDate: string;
  cash: number;
  marketValue: number;
  totalValue: number;
  positionsCount: number;
  dailyPnl: number;
  dailyPnlPct: number;
}

function formatDate(d: Date | string | undefined): string {
  if (!d) return "-";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toISOString().split("T")[0];
}

export const portfolioRouter = createRouter({
  snapshot: publicQuery.query(async () => {
    if (!isDuckDBAvailable()) {
      return null;
    }

    try {
      const [positionsRow] = await queryDuckDB<{ count: bigint }>(
        `SELECT COUNT(*) AS count FROM paper_positions`
      );

      const rows = await queryDuckDB<NavRow>(
        `SELECT trade_date, cash, market_value, total_value
         FROM paper_nav
         ORDER BY trade_date DESC
         LIMIT 2`
      );
      if (!rows || rows.length === 0) return null;

      const latest = rows[0];
      const previous = rows[1];
      const totalValue = Number(latest.total_value);
      const prevTotal = previous ? Number(previous.total_value) : totalValue;
      const dailyPnl = totalValue - prevTotal;
      const dailyPnlPct = prevTotal > 0 ? dailyPnl / prevTotal : 0;

      return {
        tradeDate: formatDate(latest.trade_date),
        cash: Number(latest.cash),
        marketValue: Number(latest.market_value),
        totalValue,
        positionsCount: Number(positionsRow?.count) || 0,
        dailyPnl,
        dailyPnlPct,
      } as PortfolioSnapshot;
    } catch (err) {
      console.error("Failed to load portfolio snapshot:", err);
      return null;
    }
  }),
});
