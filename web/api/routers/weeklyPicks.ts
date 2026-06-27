import { createRouter, publicQuery } from "../middleware";
import { getDataStorePath, queryDuckDB } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

export interface WeeklyPick {
  rank: number;
  symbol: string;
  name?: string;
  score: number;
  close: number;
}

export interface WeeklyPicksResult {
  generatedAt: string;
  predictionDate: string;
  benchmark: string;
  picks: WeeklyPick[];
}

function parseMarkdownTable(content: string): WeeklyPick[] {
  const lines = content.split("\n");
  const picks: WeeklyPick[] = [];
  let inTable = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("| 排名 ")) {
      inTable = true;
      continue;
    }
    if (inTable && trimmed.startsWith("|")) {
      if (trimmed.includes("---")) continue;
      const cells = trimmed
        .split("|")
        .map((c) => c.trim())
        .filter(Boolean);
      if (cells.length >= 4) {
        const rank = parseInt(cells[0], 10);
        const symbol = cells[1];
        const score = parseFloat(cells[2]);
        const close = parseFloat(cells[3]);
        if (!isNaN(rank) && symbol && !isNaN(score) && !isNaN(close)) {
          picks.push({ rank, symbol, name: symbol, score, close });
        }
      }
    }
  }
  return picks;
}

async function readLatestWeeklyReport(): Promise<WeeklyPicksResult | null> {
  try {
    const reportsDir = getDataStorePath("reports");
    const files = (await readdir(reportsDir)).filter((f) =>
      f.startsWith("weekly_picks_") && f.endsWith(".md")
    );
    if (files.length === 0) return null;

    files.sort();
    const latest = files[files.length - 1];
    const content = await readFile(join(reportsDir, latest), "utf-8");

    const generatedMatch = content.match(/\*\*生成日期\*\*:\s*(.+)/);
    const predictionMatch = content.match(/\*\*预测日期\*\*:\s*(\d{4}-\d{2}-\d{2})/);
    const benchmarkMatch = content.match(/\*\*基准指数\*\*:\s*(.+?)\s+\(/);

    let picks = parseMarkdownTable(content);
    if (picks.length > 0) {
      const symbols = picks.map((p) => `'${p.symbol}'`).join(",");
      const nameRows = await queryDuckDB<{ symbol: string; name: string }>(
        `SELECT symbol, COALESCE(name, symbol) AS name FROM stock_universe WHERE symbol IN (${symbols})`
      );
      const nameMap = new Map(nameRows.map((r) => [r.symbol, r.name]));
      picks = picks.map((p) => ({
        ...p,
        name: nameMap.get(p.symbol) || p.symbol,
      }));
    }

    return {
      generatedAt: generatedMatch ? generatedMatch[1].trim() : "-",
      predictionDate: predictionMatch ? predictionMatch[1] : "-",
      benchmark: benchmarkMatch ? benchmarkMatch[1].trim() : "沪深300",
      picks,
    };
  } catch (err) {
    console.error("Failed to read weekly report:", err);
    return null;
  }
}

export const weeklyPicksRouter = createRouter({
  latest: publicQuery.query(async () => {
    return readLatestWeeklyReport();
  }),
});
