import { createRouter, protectedQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

interface ReportMeta {
  filename: string;
  date: string;
  title: string;
}

async function listReports(): Promise<ReportMeta[]> {
  const reportsDir = getDataStorePath("reports");
  try {
    const files = await readdir(reportsDir);
    return files
      .filter((f) => f.startsWith("weekly_picks_") && f.endsWith(".md"))
      .sort()
      .reverse()
      .map((f) => {
        const dateStr = f.replace("weekly_picks_", "").replace(".md", "");
        const formatted = dateStr.length === 8
          ? `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
          : dateStr;
        return {
          filename: f,
          date: formatted,
          title: `AI 选股报告 ${formatted}`,
        };
      });
  } catch {
    return [];
  }
}

export const reportsRouter = createRouter({
  list: protectedQuery.query(async () => {
    return await listReports();
  }),

  get: protectedQuery
    .input((v: unknown) => {
      const val = v as { filename?: string };
      if (!val.filename || typeof val.filename !== "string") {
        throw new Error("filename is required");
      }
      if (val.filename.includes("..") || val.filename.includes("/")) {
        throw new Error("invalid filename");
      }
      return { filename: val.filename };
    })
    .query(async ({ input }) => {
      const reportsDir = getDataStorePath("reports");
      const filePath = join(reportsDir, input.filename);
      try {
        const content = await readFile(filePath, "utf-8");
        return { content, filename: input.filename };
      } catch {
        return { content: null, filename: input.filename };
      }
    }),
});
