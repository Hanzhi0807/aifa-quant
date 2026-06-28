import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

async function listMetricsFiles(): Promise<string[]> {
  const reportsDir = getDataStorePath("reports");
  try {
    const files = await readdir(reportsDir);
    return files
      .filter((f) => f.startsWith("metrics_") && f.endsWith(".json"))
      .sort();
  } catch {
    return [];
  }
}

async function readMetricsByIndex(index: number): Promise<Record<string, number> | null> {
  const files = await listMetricsFiles();
  const file = files[index - 1];
  if (!file) return null;
  try {
    const content = await readFile(join(getDataStorePath("reports"), file), "utf-8");
    return JSON.parse(content) as Record<string, number>;
  } catch {
    return null;
  }
}

async function readLatestMetrics(): Promise<Record<string, number> | null> {
  const files = await listMetricsFiles();
  if (files.length === 0) return null;
  return readMetricsByIndex(files.length);
}

export const metricsRouter = createRouter({
  getByBacktestId: publicQuery
    .input(z.object({ backtestId: z.number() }))
    .query(async ({ input }) => {
      return readMetricsByIndex(input.backtestId);
    }),

  latest: publicQuery.query(async () => {
    return readLatestMetrics();
  }),
});
