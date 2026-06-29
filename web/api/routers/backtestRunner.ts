import { z } from "zod";
import { createRouter, protectedQuery } from "../middleware";
import { execFile } from "child_process";
import { promisify } from "util";
import { getDataStorePath } from "../queries/duckdb";
import { readFile } from "fs/promises";
import { join } from "path";
import { env } from "../lib/env";

const execFileAsync = promisify(execFile);

const BacktestInput = z.object({
  start: z.string().regex(/^\d{8}$/).default("20240101"),
  end: z.string().regex(/^\d{8}$/).default("20241231"),
  topK: z.number().int().min(1).max(50).default(5),
  freq: z.number().int().min(1).max(60).default(5),
  rolling: z.boolean().default(false),
  benchmark: z.string().regex(/^\d{6}\.(SH|SZ)$/).default("000300.SH"),
});

export const backtestRunnerRouter = createRouter({
  run: protectedQuery.input(BacktestInput).mutation(async ({ input }) => {
    const python = process.env.PYTHON_CMD || "python3";
    const args = [
      "-m",
      "aifa_quant.cli.main",
      "backtest",
      "--start",
      input.start,
      "--end",
      input.end,
      "--top-k",
      String(input.topK),
      "--freq",
      String(input.freq),
      "--benchmark",
      input.benchmark,
      "--no-sentiment",
      "--cache-only",
    ];
    if (input.rolling) {
      args.push("--rolling");
    }

    try {
      const { stdout, stderr } = await execFileAsync(python, args, {
        cwd: process.cwd(),
        timeout: 300000,
      });
      const reportsDir = getDataStorePath("reports");
      const metricsPath = join(
        reportsDir,
        `metrics_${input.start}_${input.end}${input.rolling ? "_rolling" : ""}.json`
      );
      let metrics = null;
      try {
        metrics = JSON.parse(await readFile(metricsPath, "utf-8")) as Record<string, number>;
      } catch {
        // ignore
      }
      return {
        success: true,
        metrics,
        stdout: stdout.slice(-2000),
        stderr: stderr.slice(-1000),
      };
    } catch (err: any) {
      return {
        success: false,
        error: env.isProduction ? "Backtest execution failed" : (err.message || String(err)),
        stdout: env.isProduction ? "" : (err.stdout?.slice(-2000) || ""),
        stderr: env.isProduction ? "" : (err.stderr?.slice(-1000) || ""),
      };
    }
  }),
});
