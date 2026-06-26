import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { equityCurve, modelRegistry } from "@db/schema";
import { sql } from "drizzle-orm";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

export const dbInfoRouter = createRouter({
  stats: publicQuery.query(async () => {
    try {
      if (isDuckDBAvailable()) {
        const [recordsRow] = await queryDuckDB<{ count: bigint }>(
          "SELECT COUNT(*) AS count FROM daily_quotes"
        );
        const [symbolsRow] = await queryDuckDB<{ count: bigint }>(
          "SELECT COUNT(DISTINCT symbol) AS count FROM daily_quotes"
        );
        const [dateRangeRow] = await queryDuckDB<{ min: Date; max: Date }>(
          "SELECT MIN(trade_date) AS min, MAX(trade_date) AS max FROM daily_quotes"
        );
        const [positionsRow] = await queryDuckDB<{ count: bigint }>(
          "SELECT COUNT(*) AS count FROM paper_positions"
        );

        const formatDate = (d: Date | undefined) =>
          d ? new Date(d).toISOString().split("T")[0] : undefined;

        return {
          totalRecords: Number(recordsRow?.count) || 0,
          symbols: Number(symbolsRow?.count) || 0,
          models: Number(positionsRow?.count) || 0,
          dateRange: {
            min: formatDate(dateRangeRow?.min) || "2023-01-03",
            max: formatDate(dateRangeRow?.max) || "2024-12-31",
          },
        };
      }

      const db = getDb();

      const [recordsCount] = await db
        .select({ count: sql<number>`count(*)` })
        .from(equityCurve);

      const [symbolsCount] = await db
        .select({ count: sql<number>`count(distinct ${equityCurve.backtestId})` })
        .from(equityCurve);

      const [dateRange] = await db
        .select({
          min: sql<string>`min(${equityCurve.tradeDate})`,
          max: sql<string>`max(${equityCurve.tradeDate})`,
        })
        .from(equityCurve);

      const [modelsCount] = await db
        .select({ count: sql<number>`count(*)` })
        .from(modelRegistry);

      return {
        totalRecords: Number(recordsCount.count) || 0,
        symbols: Number(symbolsCount.count) || 0,
        models: Number(modelsCount.count) || 0,
        dateRange: {
          min: dateRange?.min || "2023-01-03",
          max: dateRange?.max || "2024-12-31",
        },
      };
    } catch {
      // Fallback mock data
      return {
        totalRecords: 24200,
        symbols: 5,
        models: 3,
        dateRange: {
          min: "2023-01-03",
          max: "2024-12-31",
        },
      };
    }
  }),
});
