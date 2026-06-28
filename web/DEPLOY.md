# AifaQuant Web Dashboard — Deployment Guide

> 当前 Web 仪表盘直接读取本地 DuckDB，不再依赖 MySQL/Drizzle。以下内容反映实际运行方式。

## Prerequisites

- Node.js 20+
- Python 3.10+ 虚拟环境 `.venv`（用于后端通过子进程调用 `aifa_quant` 时复现环境，当前版本仅前端展示 DuckDB 数据）
- 本地 `data_store/aifa_quant.duckdb` 已存在数据

## Option 1: 本地开发（推荐）

```bash
cd web
npm install
npm run dev
```

本地开发地址：`http://localhost:3000`（若 3000 被占用，Vite 会自动切换端口）。

确保项目根目录已有数据：

```bash
python scripts/daily_refresh.py --force --skip-paper-trade
```

## Option 2: 生产构建

```bash
cd web
npm install
npm run build
NODE_ENV=production node dist/boot.js
```

生产构建会输出 `dist/boot.js`，启动后同样监听 `localhost:3000`。可通过环境变量 `PORT` 修改端口：

```bash
PORT=8080 NODE_ENV=production node dist/boot.js
```

> `duckdb` 是外部原生依赖，不能被打包进 `dist/boot.js`，因此生产环境需要在 `web/` 目录保留 `node_modules`。

## Environment Variables

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 服务端口 | `3000` |
| `DUCKDB_PATH` | DuckDB 文件路径（相对项目根目录） | `../data_store/aifa_quant.duckdb` |
| `NODE_ENV` | 运行环境 | `development` |

> 旧版 `DATABASE_URL`（MySQL）已不再使用；`web/db/` 下的 Drizzle 文件保留，但当前仪表盘不走 MySQL。

## Option 3: Docker（需可访问 Docker Hub 或离线镜像）

项目已提供 `Dockerfile` 与 `docker-compose.yml`，把 Python CLI 与 Web 服务打包在一起：

```bash
# 构建并启动（需 Docker daemon 运行中，且能拉取 python:3.12-slim / node:22-slim）
docker compose up --build -d
```

访问 `http://localhost:3000` 即可查看由本地 DuckDB 驱动的仪表盘。

默认会把当前目录的 `data_store/` 挂载到容器 `/app/data_store`，因此：

- 先在本地用 CLI 准备好数据，或
- 进入容器运行 CLI：`docker exec -it aifa-quant bash` 后执行 `aifa ...`

> ⚠️ 本机构建受网络限制可能无法拉取基础镜像，需要配置镜像源或离线导入基础镜像后再试。

## Architecture Overview

```
User Browser
    |
    v
React Frontend (Vite + Recharts)
    |
    | tRPC (HTTP)
    v
Hono Backend (Node.js)
    |
    | duckdb (只读连接，每次查询后关闭)
    v
DuckDB (data_store/aifa_quant.duckdb)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 首页无数据 | 确认 `data_store/aifa_quant.duckdb` 存在且 `DUCKDB_PATH` 正确 |
| `npm run check` fails | 运行 `npm install` 确保所有 deps 已安装 |
| 构建失败 | 检查 Node 版本（requires 20+），运行 `npm install` |
| DuckDB locked | Web 已优化关闭逻辑；若仍锁库，检查是否有孤儿 Node/Python 进程并手动结束 |
| Docker build fails | 配置镜像源或先离线导入 `python:3.12-slim`、`node:22-slim` |

## Integration with aifa_quant Core

Web 仪表盘当前只读展示 DuckDB 中的模拟交易状态、回测净值、因子重要性等数据。若后续需要网页触发回测/训练，可通过以下方式扩展：

### Option A: Python subprocess

```typescript
// api/routers/backtestRunner.ts — add execution endpoint
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

execute: publicMutation
  .input(z.object({ config: backtestConfigSchema }))
  .mutation(async ({ input }) => {
    const result = await execAsync(
      `python -m aifa_quant.cli.main backtest '${JSON.stringify(input.config)}'`
    );
    return JSON.parse(result.stdout);
  }),
```

### Option B: HTTP API bridge

Run the Python core as a separate FastAPI service:

```python
# aifa_quant/api.py
from fastapi import FastAPI
app = FastAPI()

@app.post("/backtest")
def run_backtest(config: BacktestConfig):
    engine = BacktestEngine(config)
    return engine.run()
```

Then call it from the Hono backend.
