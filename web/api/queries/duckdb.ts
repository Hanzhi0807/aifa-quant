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

let dbInstance: Database | null = null;
let connectionInstance: Connection | null = null;

export function isDuckDBAvailable(): boolean {
  return existsSync(getDuckDBPath());
}

async function getConnection(): Promise<Connection | null> {
  if (!isDuckDBAvailable()) return null;
  if (connectionInstance) return connectionInstance;

  try {
    const duckdbMod = await import("duckdb");
    const duckdb = duckdbMod.default || duckdbMod;
    dbInstance = new duckdb.Database(getDuckDBPath(), duckdb.OPEN_READONLY);
    connectionInstance = dbInstance.connect();
    return connectionInstance;
  } catch (err) {
    console.error("Failed to initialize DuckDB:", err);
    return null;
  }
}

export async function queryDuckDB<T = any>(sql: string): Promise<T[]> {
  const conn = await getConnection();
  if (!conn) return [];

  return new Promise((resolve) => {
    conn.all(sql, (err, rows) => {
      if (err) {
        console.error("DuckDB query error:", err);
        resolve([]);
      } else {
        resolve((rows || []) as T[]);
      }
    });
  });
}
