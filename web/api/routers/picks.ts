import { createRouter, publicQuery } from "../middleware";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

interface PositionRow {
  symbol: string;
  shares: number;
  cost_basis: number;
}

interface QuoteRow {
  symbol: string;
  close: number;
  trade_date: Date;
}

interface NavRow {
  trade_date: Date;
  cash: number;
  market_value: number;
  total_value: number;
}

export interface PickItem {
  symbol: string;
  name: string;
  rank: number;
  shares: number;
  costBasis: number;
  latestClose: number;
  marketValue: number;
  weight: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
}

export interface PicksResult {
  tradeDate: string;
  strategy: string;
  picks: PickItem[];
}

function formatDate(d: Date | string | undefined): string {
  if (!d) return "-";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toISOString().split("T")[0];
}

export const picksRouter = createRouter({
  daily: publicQuery.query(async () => {
    if (!isDuckDBAvailable()) {
      return null;
    }

    try {
      const [navRow] = await queryDuckDB<NavRow>(
        `SELECT trade_date, cash, market_value, total_value
         FROM paper_nav
         ORDER BY trade_date DESC
         LIMIT 1`
      );
      if (!navRow) return null;

      const totalValue = Number(navRow.total_value) || 1;
      const positions = await queryDuckDB<PositionRow & { name?: string }>(
        `SELECT p.symbol, p.shares, p.cost_basis, COALESCE(u.name, p.symbol) AS name
         FROM paper_positions p
         LEFT JOIN stock_universe u ON p.symbol = u.symbol
         ORDER BY p.symbol`
      );

      // Fetch latest close for each held symbol
      const symbolList = positions.map((p) => `'${p.symbol}'`).join(",");
      const latestQuotes: QuoteRow[] = symbolList
        ? await queryDuckDB<QuoteRow>(
            `SELECT q.symbol, q.close, q.trade_date
             FROM daily_quotes q
             INNER JOIN (
               SELECT symbol, MAX(trade_date) AS trade_date
               FROM daily_quotes
               WHERE symbol IN (${symbolList})
               GROUP BY symbol
             ) m ON q.symbol = m.symbol AND q.trade_date = m.trade_date`
          )
        : [];

      const quoteMap = new Map(latestQuotes.map((q) => [q.symbol, q]));

      const picks: PickItem[] = positions
        .map((pos, idx) => {
          const quote = quoteMap.get(pos.symbol);
          const close = quote ? Number(quote.close) : Number(pos.cost_basis);
          const marketValue = close * Number(pos.shares);
          const costValue = Number(pos.cost_basis) * Number(pos.shares);
          const unrealizedPnl = marketValue - costValue;
          const unrealizedPnlPct =
            costValue > 0 ? (unrealizedPnl / costValue) : 0;
          return {
            symbol: pos.symbol,
            name: pos.name || pos.symbol,
            rank: idx + 1,
            shares: Number(pos.shares),
            costBasis: Number(pos.cost_basis),
            latestClose: close,
            marketValue,
            weight: totalValue > 0 ? marketValue / totalValue : 0,
            unrealizedPnl,
            unrealizedPnlPct,
          };
        })
        .sort((a, b) => b.marketValue - a.marketValue);

      return {
        tradeDate: formatDate(navRow.trade_date),
        strategy: "AI 日度选股（TopK-Dropout，5 日调仓）",
        picks,
      } as PicksResult;
    } catch (err) {
      console.error("Failed to load daily picks:", err);
      return null;
    }
  }),
});
