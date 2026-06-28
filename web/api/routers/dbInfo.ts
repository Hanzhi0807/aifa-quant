import { createRouter, publicQuery } from "../middleware";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

function formatDate(d: Date | undefined): string | undefined {
  return d ? new Date(d).toISOString().split("T")[0] : undefined;
}

export const dbInfoRouter = createRouter({
  stats: publicQuery.query(async () => {
    if (!isDuckDBAvailable()) {
      return {
        totalRecords: 0,
        symbols: 0,
        models: 0,
        positions: 0,
        dateRange: { min: undefined, max: undefined },
      };
    }

    try {
      const [recordsRow] = await queryDuckDB<{ count: bigint }>(
        "SELECT COUNT(*) AS count FROM daily_quotes",
      );
      const [symbolsRow] = await queryDuckDB<{ count: bigint }>(
        "SELECT COUNT(DISTINCT symbol) AS count FROM daily_quotes",
      );
      const [dateRangeRow] = await queryDuckDB<{ min: Date; max: Date }>(
        "SELECT MIN(trade_date) AS min, MAX(trade_date) AS max FROM daily_quotes",
      );
      const [positionsRow] = await queryDuckDB<{ count: bigint }>(
        "SELECT COUNT(*) AS count FROM paper_positions WHERE shares > 0",
      );

      return {
        totalRecords: Number(recordsRow?.count) || 0,
        symbols: Number(symbolsRow?.count) || 0,
        models: 0, // populated by model router
        positions: Number(positionsRow?.count) || 0,
        dateRange: {
          min: formatDate(dateRangeRow?.min),
          max: formatDate(dateRangeRow?.max),
        },
      };
    } catch (err) {
      console.error("Failed to load db info:", err);
      return {
        totalRecords: 0,
        symbols: 0,
        models: 0,
        positions: 0,
        dateRange: { min: undefined, max: undefined },
      };
    }
  }),
});
