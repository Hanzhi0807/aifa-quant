# AifaQuant Web Dashboard

A dark-mode quantitative finance dashboard for the AifaQuant A-share quantitative research framework. Built with React + TypeScript + Tailwind CSS + shadcn/ui frontend and Hono + tRPC backend, reading directly from the local DuckDB.

## Features

- **Dashboard** — strategy profile selector, per-profile positions, equity curve with CSI300 / SSE benchmarks, performance metrics, FAQ
- **Backtest** — backtest history with search/filter, configuration panel
- **Models** — model registry table with feature importance visualization
- **Data** — database statistics, data summary, quick start guide

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Recharts |
| Backend | Hono + tRPC 11.x + superjson |
| Database | DuckDB (`data_store/aifa_quant.duckdb`) |
| Auth | None (public access) |

## Project Structure

```
├── api/                      # Backend API
│   ├── routers/              # tRPC routers
│   │   ├── health.ts         # Health check
│   │   ├── dbInfo.ts         # Database statistics
│   │   ├── strategies.ts     # Profile list, positions, equity curve with benchmarks
│   │   ├── backtest.ts       # Backtest CRUD
│   │   ├── equityCurve.ts    # Equity curve data points
│   │   ├── metrics.ts        # Performance metrics
│   │   ├── model.ts          # Model registry
│   │   ├── factor.ts         # Factor importance
│   │   ├── factorStore.ts    # Factor store
│   │   ├── risk.ts           # Risk overview
│   │   └── refresh.ts        # Data refresh trigger
│   ├── middleware.ts         # tRPC middleware
│   ├── router.ts             # Router registration
│   ├── context.ts            # Request context
│   ├── boot.ts               # Server entry
│   └── queries/              # Database queries
│       ├── duckdb.ts         # DuckDB read-only query wrapper
│       └── connection.ts     # Legacy MySQL connection (unused)
├── db/                       # Legacy Drizzle schema (unused)
├── contracts/                # Shared types (frontend/backend)
├── src/
│   ├── pages/                # Route pages (Home/Backtest/Models/Data)
│   ├── components/           # React components
│   │   ├── layout/           # Navigation, GlassCard
│   │   └── dashboard/        # KPI, Charts, Tables
│   ├── providers/trpc.tsx    # tRPC client setup
│   └── App.tsx               # Routes
├── design/
│   ├── design.md             # Frontend design spec
│   └── backend.md            # Backend design spec
├── README.md                 # This file
└── DEPLOY.md                 # Deployment guide
```

## Database

Web 仪表盘直接读取项目根目录下的 DuckDB 文件。默认路径由 `web/api/queries/duckdb.ts` 解析为 `../data_store/aifa_quant.duckdb`。

主要查询的表：

- `daily_quotes` — 日线行情（股票 + 指数）
- `paper_nav` — 模拟交易净值（按 `profile` 隔离）
- `paper_positions` — 当前持仓
- `model_registry` — 模型注册表

## API Endpoints (tRPC)

| Router | Procedure | Type | Description |
|--------|-----------|------|-------------|
| `health` | `check` | query | Health check + version |
| `dbInfo` | `stats` | query | Database statistics |
| `strategies` | `list` | query | List all profiles with latest return |
| `strategies` | `getPicks` | query | Current picks for a profile |
| `strategies` | `getEquity` | query | Normalized equity curve + benchmarks |
| `backtest` | `list` | query | List backtest runs |
| `backtest` | `getById` | query | Single backtest details |
| `equityCurve` | `getByBacktestId` | query | Equity curve data points |
| `metrics` | `getByBacktestId` | query | Performance metrics JSON |
| `model` | `list` | query | List all models |
| `model` | `getById` | query | Single model details |
| `factor` | `getByModelId` | query | Factor importances by model |

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server (port 3000) |
| `npm run build` | Build frontend + backend bundle |
| `npm run start` | Start production server |
| `npm run check` | TypeScript type check |
| `npm run test` | Run vitest |
| `npm run lint` | Run ESLint |
| `npm run format` | Run Prettier |

## Quick Start

```bash
cd web
npm install
npm run dev
```

Then open `http://localhost:3000`.

> 确保项目根目录已有 `data_store/aifa_quant.duckdb`。如果没有，运行 `python scripts/daily_refresh.py --force --skip-paper-trade`。

See [`DEPLOY.md`](DEPLOY.md) for production deployment options.
