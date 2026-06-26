import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { factorImportance } from "@db/schema";
import { eq, asc } from "drizzle-orm";
import { getDataStorePath } from "../queries/duckdb";
import { readFile } from "fs/promises";

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

interface FactorRow {
  id: number;
  modelId: number;
  factorName: string;
  importance: number;
  rank: number;
}

async function readFactorImportance(): Promise<FactorRow[] | null> {
  try {
    const path = getDataStorePath("models/lgb_stock_selector_latest.json");
    const content = await readFile(path, "utf-8");
    const data = JSON.parse(content) as {
      feature_importance?: Record<string, number>;
    };

    if (!data.feature_importance) return null;

    const entries = Object.entries(data.feature_importance)
      .map(([factorName, importance]) => ({
        factorName,
        importance: Number(importance),
      }))
      .sort((a, b) => b.importance - a.importance);

    return entries.map((entry, index) => ({
      id: index + 1,
      modelId: 1,
      factorName: entry.factorName,
      importance: entry.importance,
      rank: index + 1,
    }));
  } catch {
    return null;
  }
}

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
        const factors = await readFactorImportance();
        if (factors) {
          return factors
            .filter((f) => f.modelId === input.modelId)
            .slice(0, input.limit);
        }

        const db = getDb();
        const rows = await db
          .select()
          .from(factorImportance)
          .where(eq(factorImportance.modelId, input.modelId))
          .orderBy(asc(factorImportance.rank))
          .limit(input.limit);
        return rows.map((f) => ({
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
