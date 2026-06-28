import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

interface NavRow {
  trade_date: Date;
  total_value: number;
}

interface QuoteRow {
  symbol: string;
  trade_date: Date;
  close: number;
}

interface EquityPoint {
  tradeDate: string;
  normalizedValue: number;
  benchmarkNormalized?: number;
}

function formatDate(d: Date | string | undefined): string {
  if (!d) return "-";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toISOString().split("T")[0];
}

function oneYearBefore(d: Date): Date {
  const start = new Date(d);
  start.setFullYear(start.getFullYear() - 1);
  return start;
}

async function getLatestNavDate(profile: string): Promise<Date | null> {
  const rows = await queryDuckDB<NavRow>(
    `SELECT trade_date FROM paper_nav
     WHERE profile = ? AND market_value > 0
     ORDER BY trade_date DESC LIMIT 1`,
    [profile],
  );
  return rows[0]?.trade_date ? new Date(rows[0].trade_date) : null;
}

async function getEquityForProfile(profile: string): Promise<EquityPoint[] | null> {
  const latestDate = await getLatestNavDate(profile);
  if (!latestDate) return null;

  const startDate = oneYearBefore(latestDate);
  const startStr = formatDate(startDate);
  const endStr = formatDate(latestDate);

  const rows = await queryDuckDB<NavRow>(
    `SELECT trade_date, total_value FROM paper_nav
     WHERE profile = ? AND market_value > 0
       AND trade_date >= ? AND trade_date <= ?
     ORDER BY trade_date`,
    [profile, startStr, endStr],
  );
  if (rows.length < 2) return null;

  const first = Number(rows[0].total_value);
  if (first <= 0) return null;

  const benchRows = await queryDuckDB<QuoteRow>(
    `SELECT symbol, trade_date, close FROM daily_quotes
     WHERE symbol = '000300.SH'
       AND trade_date >= ? AND trade_date <= ?
     ORDER BY trade_date`,
    [startStr, endStr],
  );

  const benchFirst = benchRows.length > 0 ? Number(benchRows[0].close) : 0;
  const benchMap = new Map(
    benchRows.map((r) => [formatDate(r.trade_date), Number(r.close)]),
  );

  let lastBench = benchFirst || 0;

  return rows.map((r) => {
    const tradeDate = formatDate(r.trade_date);
    if (benchMap.has(tradeDate)) lastBench = benchMap.get(tradeDate)!;
    const point: EquityPoint = {
      tradeDate,
      normalizedValue: Number((Number(r.total_value) / first).toFixed(6)),
    };
    if (benchFirst > 0 && lastBench > 0) {
      point.benchmarkNormalized = Number((lastBench / benchFirst).toFixed(6));
    }
    return point;
  });
}

export const equityCurveRouter = createRouter({
  getByBacktestId: publicQuery
    .input(z.object({ backtestId: z.number() }))
    .query(async () => {
      if (!isDuckDBAvailable()) return null;
      return getEquityForProfile("balanced");
    }),

  latest: publicQuery.query(async () => {
    if (!isDuckDBAvailable()) return null;
    return getEquityForProfile("balanced");
  }),
});
