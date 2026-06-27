import { z } from "zod";
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
  high: number;
  low: number;
  trade_date: string;
}

export interface StopInfo {
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

export interface RiskStatus {
  marketTrend: "trending" | "choppy";
  positions: StopInfo[];
}

function computeATR(quotes: QuoteRow[], window: number = 14): number | null {
  if (quotes.length < window + 1) return null;
  const trValues: number[] = [];
  for (let i = 1; i < quotes.length; i++) {
    const high = quotes[i].high;
    const low = quotes[i].low;
    const prevClose = quotes[i - 1].close;
    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    trValues.push(tr);
  }
  if (trValues.length < window) return null;
  const recent = trValues.slice(-window);
  return recent.reduce((a, b) => a + b, 0) / window;
}

function detectOscillation(closes: number[], window: number = 20): boolean {
  if (closes.length < window) return false;
  const recent = closes.slice(-window);
  const base = recent[0];
  if (base === 0) return false;
  const normalized = recent.map((v) => v / base);
  const n = normalized.length;
  const xMean = (n - 1) / 2;
  const yMean = normalized.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    num += (i - xMean) * (normalized[i] - yMean);
    den += (i - xMean) ** 2;
  }
  const slope = den !== 0 ? num / den : 0;
  const intercept = yMean - slope * xMean;
  let residualSum = 0;
  for (let i = 0; i < n; i++) {
    const fitted = slope * i + intercept;
    residualSum += Math.abs(normalized[i] - fitted);
  }
  return residualSum / n > 0.02;
}

export const riskRouter = createRouter({
  status: publicQuery
    .input(z.object({ profile: z.string().default("balanced") }))
    .query(async ({ input }) => {
      if (!isDuckDBAvailable()) {
        return null;
      }

      try {
        const positions = await queryDuckDB<PositionRow>(
          `SELECT symbol, shares, cost_basis FROM paper_positions
           WHERE profile = ? AND shares > 0`,
          [input.profile],
        );

        if (positions.length === 0) return null;

        const symbols = positions.map((p) => `'${p.symbol}'`).join(",");

        // Get latest 60 days of quotes for ATR calculation
        const allQuotes = await queryDuckDB<QuoteRow>(
          `SELECT symbol, close, high, low, trade_date
           FROM daily_quotes
           WHERE symbol IN (${symbols})
           ORDER BY symbol, trade_date`,
        );

        const nameRows = await queryDuckDB<{ symbol: string; name: string }>(
          `SELECT symbol, COALESCE(name, symbol) AS name FROM stock_universe WHERE symbol IN (${symbols})`
        );
        const nameMap = new Map(nameRows.map((r) => [r.symbol, r.name]));

        // Benchmark for market trend (CSI 300 = 000300.SH)
        const benchQuotes = await queryDuckDB<QuoteRow>(
          `SELECT close, trade_date FROM daily_quotes
           WHERE symbol = '000300.SH'
           ORDER BY trade_date DESC
           LIMIT 60`
        );
        const benchCloses = benchQuotes.reverse().map((q) => q.close);
        const marketTrend = detectOscillation(benchCloses) ? "choppy" : "trending";

        const stopInfo: StopInfo[] = positions.map((pos) => {
          const symQuotes = allQuotes.filter((q) => q.symbol === pos.symbol);
          const currentPrice = symQuotes.length > 0 ? symQuotes[symQuotes.length - 1].close : pos.cost_basis;
          const atr = computeATR(symQuotes);
          const stopLossPrice = atr ? currentPrice - atr : null;
          const takeProfitPrice = atr ? currentPrice + 3 * atr : null;
          const unrealizedPnlPct = pos.cost_basis > 0
            ? (currentPrice - pos.cost_basis) / pos.cost_basis
            : 0;

          return {
            symbol: pos.symbol,
            name: nameMap.get(pos.symbol) || pos.symbol,
            shares: pos.shares,
            costBasis: pos.cost_basis,
            currentPrice,
            stopLossPrice,
            takeProfitPrice,
            atr,
            unrealizedPnlPct,
          };
        });

        return { marketTrend, positions: stopInfo } as RiskStatus;
      } catch (err) {
        console.error("Failed to load risk status:", err);
        return null;
      }
    }),
});
