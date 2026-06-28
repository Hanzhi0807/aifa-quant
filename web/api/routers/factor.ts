import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

interface FactorRow {
  id: number;
  modelId: number;
  factorName: string;
  importance: number;
  rank: number;
}

async function readFactorImportance(modelId: number): Promise<FactorRow[]> {
  const modelsDir = getDataStorePath("models");
  try {
    const files = (await readdir(modelsDir)).filter((f) => f.endsWith(".json")).sort();
    const file = files[modelId - 1];
    if (!file) return [];

    const content = await readFile(join(modelsDir, file), "utf-8");
    const data = JSON.parse(content) as {
      feature_importance?: Record<string, number>;
    };

    if (!data.feature_importance) return [];

    return Object.entries(data.feature_importance)
      .map(([factorName, importance]) => ({ factorName, importance: Number(importance) }))
      .sort((a, b) => b.importance - a.importance)
      .map((entry, index) => ({
        id: index + 1,
        modelId,
        factorName: entry.factorName,
        importance: entry.importance,
        rank: index + 1,
      }));
  } catch {
    return [];
  }
}

export const factorRouter = createRouter({
  getByModelId: publicQuery
    .input(
      z.object({
        modelId: z.number(),
        limit: z.number().optional().default(20),
      }),
    )
    .query(async ({ input }) => {
      const factors = await readFactorImportance(input.modelId);
      return factors.slice(0, input.limit);
    }),
});
