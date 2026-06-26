import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { backtestRuns } from "@db/schema";
import { eq } from "drizzle-orm";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

const mockMetrics: Record<number, Record<string, number>> = {
  1: {
    totalReturn: 0.2655,
    annualReturn: 0.1278,
    sharpeRatio: 1.35,
    maxDrawdown: -0.1523,
    volatility: 0.185,
    winRate: 0.62,
    profitFactor: 1.85,
    benchmarkTotalReturn: 0.1468,
    excessReturn: 0.1187,
    informationRatio: 0.92,
    calmarRatio: 0.84,
    sortinoRatio: 1.68,
  },
  2: {
    totalReturn: 0.1987,
    annualReturn: 0.0956,
    sharpeRatio: 1.12,
    maxDrawdown: -0.1892,
    volatility: 0.162,
    winRate: 0.58,
    profitFactor: 1.62,
    benchmarkTotalReturn: 0.1468,
    excessReturn: 0.0519,
    informationRatio: 0.45,
    calmarRatio: 0.51,
    sortinoRatio: 1.35,
  },
  3: {
    totalReturn: 0.0892,
    annualReturn: 0.3568,
    sharpeRatio: 2.15,
    maxDrawdown: -0.0456,
    volatility: 0.142,
    winRate: 0.71,
    profitFactor: 2.35,
    benchmarkTotalReturn: 0.0523,
    excessReturn: 0.0369,
    informationRatio: 1.25,
    calmarRatio: 2.15,
    sortinoRatio: 2.85,
  },
  4: {
    totalReturn: 0.2234,
    annualReturn: 0.1277,
    sharpeRatio: 1.28,
    maxDrawdown: -0.1734,
    volatility: 0.195,
    winRate: 0.59,
    profitFactor: 1.72,
    benchmarkTotalReturn: 0.1234,
    excessReturn: 0.10,
    informationRatio: 0.78,
    calmarRatio: 0.74,
    sortinoRatio: 1.55,
  },
  5: {
    totalReturn: 0.3123,
    annualReturn: 0.1502,
    sharpeRatio: 1.52,
    maxDrawdown: -0.1345,
    volatility: 0.172,
    winRate: 0.65,
    profitFactor: 1.95,
    benchmarkTotalReturn: 0.1468,
    excessReturn: 0.1655,
    informationRatio: 1.18,
    calmarRatio: 1.12,
    sortinoRatio: 1.95,
  },
};

async function readLatestMetricsJson(): Promise<Record<string, number> | null> {
  try {
    const reportsDir = getDataStorePath("reports");
    const files = await readdir(reportsDir);
    const jsonFiles = files
      .filter((f) => f.startsWith("metrics_") && f.endsWith(".json"))
      .sort();
    if (jsonFiles.length === 0) return null;

    const latest = jsonFiles[jsonFiles.length - 1];
    const content = await readFile(join(reportsDir, latest), "utf-8");
    return JSON.parse(content) as Record<string, number>;
  } catch {
    return null;
  }
}

export const metricsRouter = createRouter({
  getByBacktestId: publicQuery
    .input(z.object({ backtestId: z.number() }))
    .query(async ({ input }) => {
      try {
        const metrics = await readLatestMetricsJson();
        if (metrics) return metrics;

        const db = getDb();
        const [run] = await db
          .select({ metrics: backtestRuns.metrics })
          .from(backtestRuns)
          .where(eq(backtestRuns.id, input.backtestId));

        if (!run?.metrics) return null;
        return JSON.parse(run.metrics as string) as Record<string, number>;
      } catch {
        return mockMetrics[input.backtestId] || null;
      }
    }),
});
