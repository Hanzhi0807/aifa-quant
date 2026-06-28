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

function toCamelCase(key: string): string {
  return key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function normalizeMetrics(raw: Record<string, number>): Record<string, number> {
  const normalized: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw)) {
    normalized[toCamelCase(key)] = Number(value);
  }

  // Alias for frontend components that expect a single volatility key.
  if (normalized.annualVolatility != null && normalized.volatility == null) {
    normalized.volatility = normalized.annualVolatility;
  }

  // Derived ratios when missing.
  const annualReturn = normalized.annualReturn || 0;
  const maxDrawdown = normalized.maxDrawdown || 0;
  if (normalized.calmarRatio == null && maxDrawdown < 0) {
    normalized.calmarRatio = annualReturn / Math.abs(maxDrawdown);
  }

  return normalized;
}

async function readMetricsByIndex(index: number): Promise<Record<string, number> | null> {
  const files = await listMetricsFiles();
  const file = files[index - 1];
  if (!file) return null;
  try {
    const content = await readFile(join(getDataStorePath("reports"), file), "utf-8");
    const raw = JSON.parse(content) as Record<string, number>;
    return normalizeMetrics(raw);
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
