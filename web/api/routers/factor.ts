import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { factorImportance } from "@db/schema";
import { eq, asc } from "drizzle-orm";

const mockFactors = [
  { id: 1, modelId: 1, factorName: "momentum_60d", importance: 0.15234, rank: 1 },
  { id: 2, modelId: 1, factorName: "roe_ttm", importance: 0.12892, rank: 2 },
  { id: 3, modelId: 1, factorName: "rsi_14", importance: 0.11567, rank: 3 },
  { id: 4, modelId: 1, factorName: "volatility_20d", importance: 0.09845, rank: 4 },
  { id: 5, modelId: 1, factorName: "pe_ttm", importance: 0.08723, rank: 5 },
  { id: 6, modelId: 1, factorName: "pb_lf", importance: 0.07654, rank: 6 },
  { id: 7, modelId: 1, factorName: "turnover_20d", importance: 0.07231, rank: 7 },
  { id: 8, modelId: 1, factorName: "momentum_20d", importance: 0.06892, rank: 8 },
  { id: 9, modelId: 1, factorName: "macd_signal", importance: 0.06123, rank: 9 },
  { id: 10, modelId: 1, factorName: "market_cap", importance: 0.05432, rank: 10 },
  { id: 11, modelId: 1, factorName: "close_ratio", importance: 0.04876, rank: 11 },
  { id: 12, modelId: 1, factorName: "amt_ratio", importance: 0.04215, rank: 12 },
  { id: 13, modelId: 1, factorName: "high_low_ratio", importance: 0.03892, rank: 13 },
  { id: 14, modelId: 1, factorName: "vol_ratio", importance: 0.03218, rank: 14 },
  { id: 15, modelId: 1, factorName: "industry_momentum", importance: 0.02186, rank: 15 },
];

export const factorRouter = createRouter({
  getByModelId: publicQuery
    .input(
      z.object({
        modelId: z.number(),
        limit: z.number().optional().default(20),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = getDb();
        const factors = await db
          .select()
          .from(factorImportance)
          .where(eq(factorImportance.modelId, input.modelId))
          .orderBy(asc(factorImportance.rank))
          .limit(input.limit);
        return factors.map((f) => ({
          ...f,
          importance: Number(f.importance),
        }));
      } catch {
        return mockFactors
          .filter((f) => f.modelId === input.modelId)
          .slice(0, input.limit);
      }
    }),
});
