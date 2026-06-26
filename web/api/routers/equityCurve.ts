import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { equityCurve } from "@db/schema";
import { asc } from "drizzle-orm";
import { isDuckDBAvailable, queryDuckDB, getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

interface EquityPoint {
  tradeDate: string;
  normalizedValue: number;
  benchmarkNormalized?: number;
}

// Generate mock equity curve data
function generateMockEquityCurve(): EquityPoint[] {
  const tradingDays: { date: string; portfolio: number; benchmark: number }[] = [];
  const start = new Date("2023-01-03");
  const end = new Date("2024-12-31");
  let portfolio = 1.0;
  let benchmark = 1.0;

  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const day = d.getDay();
    if (day === 0 || day === 6) continue;

    const i = tradingDays.length;
    const pReturn = Math.sin(i * 0.05) * 0.005 + 0.0004 + (Math.random() - 0.5) * 0.008;
    const bReturn = Math.sin(i * 0.03) * 0.004 + 0.0002 + (Math.random() - 0.5) * 0.012;

    portfolio *= 1 + pReturn;
    benchmark *= 1 + bReturn;

    tradingDays.push({
      date: d.toISOString().split("T")[0],
      portfolio: Number(portfolio.toFixed(6)),
      benchmark: Number(benchmark.toFixed(6)),
    });
  }

  return tradingDays.map((d) => ({
    tradeDate: d.date,
    normalizedValue: d.portfolio,
    benchmarkNormalized: d.benchmark,
  }));
}

const mockEquityCurve = generateMockEquityCurve();

function parseEquityCsv(content: string): EquityPoint[] {
  const lines = content.trim().split("\n");
  if (lines.length < 2) return [];

  const rows: { tradeDate: string; totalValue: number }[] = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const parts = line.split(",");
    if (parts.length < 4) continue;
    const tradeDate = parts[0];
    const totalValue = parseFloat(parts[3]);
    if (isNaN(totalValue)) continue;
    rows.push({ tradeDate, totalValue });
  }

  if (rows.length === 0) return [];
  const firstValue = rows[0].totalValue;
  return rows.map((r) => ({
    tradeDate: r.tradeDate,
    normalizedValue: Number((r.totalValue / firstValue).toFixed(6)),
  }));
}

async function readLatestEquityCsv(): Promise<EquityPoint[] | null> {
  try {
    const reportsDir = getDataStorePath("reports");
    const files = await readdir(reportsDir);
    const csvFiles = files
      .filter((f) => f.startsWith("equity_") && f.endsWith(".csv"))
      .sort();
    if (csvFiles.length === 0) return null;

    const latest = csvFiles[csvFiles.length - 1];
    const content = await readFile(join(reportsDir, latest), "utf-8");
    return parseEquityCsv(content);
  } catch {
    return null;
  }
}

async function getDuckDBEquityCurve(): Promise<EquityPoint[] | null> {
  if (!isDuckDBAvailable()) return null;
  const rows = await queryDuckDB<{ trade_date: Date; total_value: number }>(
    "SELECT trade_date, total_value FROM paper_nav ORDER BY trade_date"
  );
  if (rows.length < 2) return null;

  const firstValue = rows[0].total_value;
  return rows.map((r) => ({
    tradeDate: new Date(r.trade_date).toISOString().split("T")[0],
    normalizedValue: Number((r.total_value / firstValue).toFixed(6)),
  }));
}

export const equityCurveRouter = createRouter({
  getByBacktestId: publicQuery
    .input(z.object({ backtestId: z.number() }))
    .query(async () => {
      try {
        const duckdbCurve = await getDuckDBEquityCurve();
        if (duckdbCurve && duckdbCurve.length > 0) {
          return duckdbCurve;
        }

        const csvCurve = await readLatestEquityCsv();
        if (csvCurve && csvCurve.length > 0) {
          return csvCurve;
        }

        const db = getDb();
        const curves = await db
          .select({
            tradeDate: equityCurve.tradeDate,
            normalizedValue: equityCurve.normalizedValue,
            benchmarkNormalized: equityCurve.benchmarkNormalized,
          })
          .from(equityCurve)
          .orderBy(asc(equityCurve.tradeDate));

        return curves.map((c) => ({
          tradeDate: c.tradeDate,
          normalizedValue: Number(c.normalizedValue),
          benchmarkNormalized: Number(c.benchmarkNormalized),
        }));
      } catch {
        return mockEquityCurve;
      }
    }),
});
