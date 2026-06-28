import { createRouter, publicQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

interface ShapRow {
  feature: string;
  importance: number;
  rank: number;
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

async function findLatestShapSummary(): Promise<string | null> {
  const shapDir = getDataStorePath("reports/shap");
  try {
    const files = await readdir(shapDir);
    const csvFiles = files
      .filter((f) => f.startsWith("shap_summary_") && f.endsWith(".csv"))
      .sort();
    return csvFiles.length > 0 ? join(shapDir, csvFiles[csvFiles.length - 1]) : null;
  } catch {
    return null;
  }
}

async function findLatestShapPlot(): Promise<string | null> {
  const shapDir = getDataStorePath("reports/shap");
  try {
    const files = await readdir(shapDir);
    const pngFiles = files
      .filter((f) => f.startsWith("shap_summary_") && f.endsWith(".png"))
      .sort();
    return pngFiles.length > 0 ? `/api/shap/plot/${pngFiles[pngFiles.length - 1]}` : null;
  } catch {
    return null;
  }
}

export const shapRouter = createRouter({
  summary: publicQuery.query(async () => {
    const path = await findLatestShapSummary();
    if (!path) return { rows: [], plotUrl: null };
    try {
      const content = await readFile(path, "utf-8");
      const parsed = parseCsv(content);
      const rows: ShapRow[] = parsed
        .map((r, idx) => ({
          feature: String(r.feature || r["feature_name"] || `-`),
          importance: Number(r.importance || r["mean(|SHAP value|)"] || 0),
          rank: idx + 1,
        }))
        .sort((a, b) => b.importance - a.importance)
        .map((r, idx) => ({ ...r, rank: idx + 1 }));
      const plotUrl = await findLatestShapPlot();
      return { rows, plotUrl };
    } catch {
      return { rows: [], plotUrl: null };
    }
  }),
});
