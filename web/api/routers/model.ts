import { z } from "zod";
import { createRouter, protectedQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

interface ModelMeta {
  feature_names?: string[];
  feature_importance?: Record<string, number>;
  train_start?: string;
  train_end?: string;
  model_type?: string;
}

export interface ModelRow {
  id: number;
  name: string;
  path: string;
  featureColumns: string[];
  featureImportance: Record<string, number>;
  trainStart: string;
  trainEnd: string;
  createdAt: string;
}

async function readModelJson(filePath: string): Promise<ModelRow | null> {
  try {
    const content = await readFile(filePath, "utf-8");
    const data = JSON.parse(content) as ModelMeta;
    const pklPath = filePath.replace(/\.json$/, ".pkl");
    const stat = await import("fs/promises").then((m) => m.stat(filePath));

    return {
      id: 0, // assigned later
      name: data.model_type || filePath.split(/[\\/]/).pop()?.replace(".json", "") || "model",
      path: pklPath,
      featureColumns: data.feature_names || [],
      featureImportance: data.feature_importance || {},
      trainStart: data.train_start || "-",
      trainEnd: data.train_end || "-",
      createdAt: stat.mtime.toISOString(),
    };
  } catch (err) {
    console.error("Failed to read model json:", filePath, err);
    return null;
  }
}

async function listModels(): Promise<ModelRow[]> {
  const modelsDir = getDataStorePath("models");
  const rows: ModelRow[] = [];
  try {
    const files = await readdir(modelsDir);
    const jsonFiles = files.filter((f) => f.endsWith(".json")).sort();
    for (const file of jsonFiles) {
      const row = await readModelJson(join(modelsDir, file));
      if (row) rows.push(row);
    }
  } catch {
    // models directory may not exist
  }
  return rows.map((r, idx) => ({ ...r, id: idx + 1 }));
}

export const modelRouter = createRouter({
  list: protectedQuery.query(async () => {
    return listModels();
  }),

  getById: protectedQuery
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const models = await listModels();
      return models.find((m) => m.id === input.id) || null;
    }),
});
