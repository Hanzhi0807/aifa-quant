import { createRouter, protectedQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

export interface BacktestRun {
  id: number;
  name: string;
  startDate: string;
  endDate: string;
  topK: number;
  rebalanceFreq: number;
  rolling: boolean;
  benchmark: string;
  status: string;
  metrics: Record<string, number> | null;
  createdAt: string;
}

function parseDateRange(filename: string): { start: string; end: string; rolling: boolean } {
  // equity_YYYYMMDD_YYYYMMDD.csv or equity_YYYYMMDD_YYYYMMDD_rolling.csv
  const match = filename.match(/equity_(\d{8})_(\d{8})(_rolling)?/);
  if (!match) return { start: "-", end: "-", rolling: false };
  return {
    start: `${match[1].slice(0, 4)}-${match[1].slice(4, 6)}-${match[1].slice(6, 8)}`,
    end: `${match[2].slice(0, 4)}-${match[2].slice(4, 6)}-${match[2].slice(6, 8)}`,
    rolling: !!match[3],
  };
}

async function readMetricsJson(metricsPath: string): Promise<Record<string, number> | null> {
  try {
    const content = await readFile(metricsPath, "utf-8");
    return JSON.parse(content) as Record<string, number>;
  } catch {
    return null;
  }
}

async function listBacktestRuns(): Promise<BacktestRun[]> {
  const reportsDir = getDataStorePath("reports");
  const runs: BacktestRun[] = [];
  try {
    const files = await readdir(reportsDir);
    const equityFiles = files
      .filter((f) => f.startsWith("equity_") && f.endsWith(".csv"))
      .sort();

    for (const equityFile of equityFiles) {
      const { start, end, rolling } = parseDateRange(equityFile);
      const base = equityFile.replace(/\.csv$/, "");
      const metricsFile = `${base}.json`;
      const metricsPath = join(reportsDir, metricsFile);
      const metrics = await readMetricsJson(metricsPath);
      const stat = await import("fs/promises").then((m) => m.stat(join(reportsDir, equityFile)));

      runs.push({
        id: runs.length + 1,
        name: rolling ? `滚动回测 ${start} ~ ${end}` : `回测 ${start} ~ ${end}`,
        startDate: start,
        endDate: end,
        topK: 5,
        rebalanceFreq: 5,
        rolling,
        benchmark: "000300.SH",
        status: "completed",
        metrics,
        createdAt: stat.mtime.toISOString(),
      });
    }
  } catch {
    // reports directory may not exist
  }
  return runs.reverse();
}

export const backtestRouter = createRouter({
  list: protectedQuery.query(async () => {
    return listBacktestRuns();
  }),
});
