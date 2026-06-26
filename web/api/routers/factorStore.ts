import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDataStorePath } from "../queries/duckdb";
import { readFile, writeFile } from "fs/promises";
import { existsSync } from "fs";
import { join } from "path";
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

const CONFIG_DIR = getDataStorePath("config");
const SELECTED_FEATURES_PATH = join(CONFIG_DIR, "selected_features.json");
const AVAILABLE_FEATURES_PATH = join(CONFIG_DIR, "available_features.json");

async function ensureConfigDir() {
  if (!existsSync(CONFIG_DIR)) {
    await import("fs/promises").then((m) => m.mkdir(CONFIG_DIR, { recursive: true }));
  }
}

async function loadSelectedFeatures(): Promise<string[]> {
  try {
    const content = await readFile(SELECTED_FEATURES_PATH, "utf-8");
    return JSON.parse(content) as string[];
  } catch {
    return [];
  }
}

async function loadAvailableFeatures(): Promise<Record<string, string>> {
  try {
    const content = await readFile(AVAILABLE_FEATURES_PATH, "utf-8");
    return JSON.parse(content) as Record<string, string>;
  } catch {
    return {};
  }
}

async function refreshAvailableFeatures(): Promise<Record<string, string>> {
  try {
    const python = process.env.PYTHON_CMD || "python3";
    const { stdout } = await execFileAsync(
      python,
      ["-m", "aifa_quant.cli.main", "list-features", "--json"],
      { cwd: process.cwd(), timeout: 60000 }
    );
    const data = JSON.parse(stdout) as Record<string, string>;
    await ensureConfigDir();
    await writeFile(AVAILABLE_FEATURES_PATH, JSON.stringify(data, null, 2), "utf-8");
    return data;
  } catch (err) {
    console.error("Failed to refresh available features:", err);
    return loadAvailableFeatures();
  }
}

export const factorStoreRouter = createRouter({
  listAvailable: publicQuery.query(async () => {
    const available = await refreshAvailableFeatures();
    const selected = await loadSelectedFeatures();
    return Object.entries(available).map(([name, group]) => ({
      name,
      group,
      selected: selected.length === 0 || selected.includes(name),
    }));
  }),

  getSelected: publicQuery.query(async () => {
    return loadSelectedFeatures();
  }),

  setSelected: publicQuery
    .input(z.object({ features: z.array(z.string()) }))
    .mutation(async ({ input }) => {
      await ensureConfigDir();
      await writeFile(
        SELECTED_FEATURES_PATH,
        JSON.stringify(input.features, null, 2),
        "utf-8"
      );
      return { success: true, count: input.features.length };
    }),
});
