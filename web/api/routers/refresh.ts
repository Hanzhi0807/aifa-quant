import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { exec } from "child_process";
import { promisify } from "util";
import { resolve } from "path";

const execAsync = promisify(exec);

interface RefreshResult {
  success: boolean;
  message: string;
  output?: string;
}

function getProjectRoot(): string {
  // API server runs from web/ in dev and from web/dist/ in production.
  return resolve(process.cwd(), "..");
}

export const refreshRouter = createRouter({
  run: publicQuery
    .input(z.object({}).optional())
    .mutation(async () => {
      const projectRoot = getProjectRoot();
      const python = process.platform === "win32"
        ? resolve(projectRoot, ".venv", "Scripts", "python.exe")
        : resolve(projectRoot, ".venv", "bin", "python");

      const cmd = `"${python}" scripts/daily_refresh.py`;

      try {
        const { stdout, stderr } = await execAsync(cmd, {
          cwd: projectRoot,
          maxBuffer: 10 * 1024 * 1024,
          timeout: 10 * 60 * 1000, // 10 minutes
        });

        return {
          success: true,
          message: "数据刷新完成",
          output: stdout + (stderr ? `\n${stderr}` : ""),
        } as RefreshResult;
      } catch (err: any) {
        return {
          success: false,
          message: err.message || "刷新失败",
          output: err.stdout ? String(err.stdout) : undefined,
        } as RefreshResult;
      }
    }),
});
