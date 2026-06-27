import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { exec } from "child_process";
import { promisify } from "util";
import { existsSync } from "fs";
import { resolve } from "path";

const execAsync = promisify(exec);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface RefreshResult {
  success: boolean;
  message: string;
  output?: string;
}

function getProjectRoot(): string {
  return resolve(process.cwd(), "..");
}

function resolvePython(projectRoot: string): string {
  const candidates =
    process.platform === "win32"
      ? [resolve(projectRoot, ".venv", "Scripts", "python.exe")]
      : [resolve(projectRoot, ".venv", "bin", "python")];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return process.platform === "win32" ? "python" : "python3";
}

async function runRefresh(projectRoot: string, python: string): Promise<RefreshResult> {
  const cmd = `"${python}" scripts/daily_refresh.py`;

  const { stdout, stderr } = await execAsync(cmd, {
    cwd: projectRoot,
    maxBuffer: 10 * 1024 * 1024,
    timeout: 10 * 60 * 1000,
  });

  return {
    success: true,
    message: "数据刷新完成",
    output: stdout + (stderr ? `\n${stderr}` : ""),
  };
}

function isLockError(err: Error): boolean {
  const msg = err.message.toLowerCase();
  return msg.includes("cannot open file") || msg.includes("already open");
}

export const refreshRouter = createRouter({
  run: publicQuery
    .input(z.object({}).optional())
    .mutation(async () => {
      const projectRoot = getProjectRoot();
      const python = resolvePython(projectRoot);

      // Give pending DuckDB queries a chance to close before launching Python.
      await sleep(1500);

      try {
        return await runRefresh(projectRoot, python);
      } catch (err: any) {
        // If the DuckDB file is still locked, wait longer and retry once.
        if (isLockError(err)) {
          await sleep(5000);
          try {
            return await runRefresh(projectRoot, python);
          } catch (retryErr: any) {
            return {
              success: false,
              message: retryErr.message || "刷新失败（重试后仍冲突）",
              output: retryErr.stdout ? String(retryErr.stdout) : undefined,
            };
          }
        }
        return {
          success: false,
          message: err.message || "刷新失败",
          output: err.stdout ? String(err.stdout) : undefined,
        };
      }
    }),
});
