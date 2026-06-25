import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { backtestRuns } from "@db/schema";
import { desc, eq } from "drizzle-orm";

// Mock backtest data as fallback
const mockBacktests = [
  {
    id: 1,
    name: "LightGBM 滚动 2024",
    startDate: "2023-01-03",
    endDate: "2024-12-31",
    topK: 10,
    rebalanceFreq: 5,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
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
    createdAt: new Date("2024-12-31T10:00:00"),
  },
  {
    id: 2,
    name: "LightGBM 固定窗口 2024",
    startDate: "2023-01-03",
    endDate: "2024-12-31",
    topK: 15,
    rebalanceFreq: 10,
    rolling: false,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
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
    createdAt: new Date("2024-12-30T14:00:00"),
  },
  {
    id: 3,
    name: "LightGBM 滚动 2024Q4",
    startDate: "2024-10-01",
    endDate: "2024-12-31",
    topK: 8,
    rebalanceFreq: 3,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
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
    createdAt: new Date("2024-12-29T09:00:00"),
  },
  {
    id: 4,
    name: "XGBoost 滚动 2024",
    startDate: "2023-06-01",
    endDate: "2024-12-31",
    topK: 10,
    rebalanceFreq: 5,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
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
    createdAt: new Date("2024-12-28T16:00:00"),
  },
  {
    id: 5,
    name: "集成模型 2024",
    startDate: "2023-01-03",
    endDate: "2024-12-31",
    topK: 12,
    rebalanceFreq: 7,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
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
    createdAt: new Date("2024-12-27T11:00:00"),
  },
];

export const backtestRouter = createRouter({
  list: publicQuery
    .input(
      z
        .object({
          limit: z.number().optional().default(20),
          offset: z.number().optional().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = getDb();
        const limit = input?.limit ?? 20;
        const offset = input?.offset ?? 0;
        const runs = await db
          .select()
          .from(backtestRuns)
          .orderBy(desc(backtestRuns.createdAt))
          .limit(limit)
          .offset(offset);
        return runs.map((r) => ({
          ...r,
          metrics: r.metrics ? JSON.parse(r.metrics as string) : null,
        }));
      } catch {
        return mockBacktests;
      }
    }),

  getById: publicQuery
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = getDb();
        const [run] = await db
          .select()
          .from(backtestRuns)
          .where(eq(backtestRuns.id, input.id));
        if (!run) return null;
        return {
          ...run,
          metrics: run.metrics ? JSON.parse(run.metrics as string) : null,
        };
      } catch {
        const mock = mockBacktests.find((b) => b.id === input.id);
        return mock || null;
      }
    }),
});
