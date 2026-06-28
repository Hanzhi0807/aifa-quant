import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

interface ICSummaryRow {
  feature: string;
  mean_ic: number;
  icir: number;
  win_rate: number;
  n_periods: number;
}

function parseCsv(content: string): Record<string, string>[] {
  const lines = content.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim());
  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    if (parts.length !== headers.length) continue;
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => (row[h] = parts[idx]));
    rows.push(row);
  }
  return rows;
}

async function listICSummaries(): Promise<string[]> {
  const dir = getDataStorePath("reports/factor_analysis");
  try {
    const files = await readdir(dir);
    return files.filter((f) => f.startsWith("ic_summary_") && f.endsWith(".csv")).sort();
  } catch {
    return [];
  }
}

async function readLatestICSummary(): Promise<ICSummaryRow[]> {
  const files = await listICSummaries();
  if (files.length === 0) return [];
  try {
    const content = await readFile(
      join(getDataStorePath("reports/factor_analysis"), files[files.length - 1]),
      "utf-8",
    );
    return parseCsv(content).map((r) => ({
      feature: r.feature || "-",
      mean_ic: Number(r.mean_ic) || 0,
      icir: Number(r.icir) || 0,
      win_rate: Number(r.win_rate) || 0,
      n_periods: Number(r.n_periods) || 0,
    }));
  } catch {
    return [];
  }
}

export const factorAnalysisRouter = createRouter({
  summary: publicQuery.query(async () => {
    return readLatestICSummary();
  }),

  detail: publicQuery
    .input(z.object({ feature: z.string() }))
    .query(async ({ input }) => {
      const dir = getDataStorePath("reports/factor_analysis");
      const files = await listICSummaries();
      if (files.length === 0) return null;
      const latest = files[files.length - 1];
      const range = latest.replace("ic_summary_", "").replace(".csv", "");
      try {
        const [quantileContent, decayContent] = await Promise.all([
          readFile(join(dir, `quantile_${input.feature}_${range}.csv`), "utf-8"),
          readFile(join(dir, `decay_${input.feature}_${range}.csv`), "utf-8"),
        ]);
        return {
          feature: input.feature,
          quantile: parseCsv(quantileContent),
          decay: parseCsv(decayContent),
        };
      } catch {
        return null;
      }
    }),
});
