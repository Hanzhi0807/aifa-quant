import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { equityCurve } from "@db/schema";
import { eq, asc } from "drizzle-orm";

// Generate mock equity curve data
function generateMockEquityCurve(): {
  tradeDate: string;
  normalizedValue: number;
  benchmarkNormalized: number;
}[] {
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

export const equityCurveRouter = createRouter({
  getByBacktestId: publicQuery
    .input(z.object({ backtestId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = getDb();
        const curves = await db
          .select({
            tradeDate: equityCurve.tradeDate,
            normalizedValue: equityCurve.normalizedValue,
            benchmarkNormalized: equityCurve.benchmarkNormalized,
          })
          .from(equityCurve)
          .where(eq(equityCurve.backtestId, input.backtestId))
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
