import { existsSync } from "fs";
import { resolve } from "path";
import type { Database, Connection } from "duckdb";

function resolveDataStoreRoot(): string {
  if (process.env.DUCKDB_PATH) {
    return process.env.DUCKDB_PATH;
  }
  // In both dev (`npm run dev` from web/) and production (`node dist/boot.js` from web/)
  // the data_store directory is the sibling of the web/ directory.
  return resolve(process.cwd(), "../data_store/aifa_quant.duckdb");
}

export function getDuckDBPath(): string {
  return resolveDataStoreRoot();
}

export function getDataStorePath(subPath: string): string {
  const dbPath = getDuckDBPath();
  const root = dbPath.endsWith(".duckdb") ? resolve(dbPath, "..") : dbPath;
  return resolve(root, subPath);
}

export function isDuckDBAvailable(): boolean {
  return existsSync(getDuckDBPath());
}

export async function queryDuckDB<T = any>(sql: string): Promise<T[]> {
  if (!isDuckDBAvailable()) return [];

  let db: Database | null = null;
  let conn: Connection | null = null;
  try {
    const duckdbMod = await import("duckdb");
    const duckdb = duckdbMod.default || duckdbMod;
    db = new duckdb.Database(getDuckDBPath(), duckdb.OPEN_READONLY);
    conn = db.connect();

    const rows = await new Promise<T[]>((resolve) => {
      conn!.all(sql, (err, rows) => {
        if (err) {
          console.error("DuckDB query error:", err);
          resolve([]);
        } else {
          resolve((rows || []) as T[]);
        }
      });
    });
    return rows;
  } catch (err) {
    console.error("Failed to query DuckDB:", err);
    return [];
  } finally {
    // Close per-query so the web server does not hold a persistent lock
    // on the DuckDB file; this lets daily_refresh.py open it exclusively.
    try {
      conn?.close();
    } catch {}
    try {
      db?.close();
    } catch {}
  }
}
