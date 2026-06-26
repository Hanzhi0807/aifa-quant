import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { execFile } from "child_process";
import { promisify } from "util";
import { getDataStorePath } from "../queries/duckdb";
import { readFile } from "fs/promises";
import { join } from "path";

const execFileAsync = promisify(execFile);

const BacktestInput = z.object({
  start: z.string().default("20240101"),
  end: z.string().default("20241231"),
  topK: z.number().int().default(5),
  freq: z.number().int().default(5),
  rolling: z.boolean().default(false),
  benchmark: z.string().default("000300.SH"),
});

export const backtestRunnerRouter = createRouter({
  run: publicQuery.input(BacktestInput).mutation(async ({ input }) => {
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
        error: err.message || String(err),
        stdout: err.stdout?.slice(-2000) || "",
        stderr: err.stderr?.slice(-1000) || "",
      };
    }
  }),
});
