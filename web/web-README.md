# AifaQuant Web Dashboard

A dark-mode quantitative finance dashboard for the AifaQuant A-share quantitative research framework. Built with React + TypeScript + Tailwind CSS + shadcn/ui frontend and Hono + tRPC + Drizzle ORM + MySQL backend.

## Features

- **Dashboard** — KPI overview, equity curve chart, performance metrics grid, recent backtest runs table, factor importance chart
- **Backtest** — Backtest history with search/filter, configuration panel (Phase 2 — async execution)
- **Models** — Model registry table with feature importance visualization
- **Data** — Database statistics, data summary, quick start guide

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Recharts |
| Backend | Hono + tRPC 11.x + superjson |
| Database | MySQL + Drizzle ORM |
| Auth | None (Phase 1 — public access) |

## Project Structure

```
├── api/                      # Backend API
│   ├── routers/              # tRPC routers
│   │   ├── health.ts         # Health check
│   │   ├── dbInfo.ts         # Database statistics
│   │   ├── backtest.ts       # Backtest CRUD
│   │   ├── equityCurve.ts    # Equity curve data
│   │   ├── metrics.ts        # Performance metrics
│   │   ├── model.ts          # Model registry
│   │   └── factor.ts         # Factor importance
│   ├── middleware.ts         # tRPC middleware
│   ├── router.ts             # Router registration
│   ├── context.ts            # Request context
│   ├── boot.ts               # Server entry
│   └── queries/connection.ts # Database connection
├── db/
│   ├── schema.ts             # Database tables
│   ├── relations.ts          # Drizzle relations
│   └── seed.ts               # Seed script
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

## Database Schema

### backtest_runs
| Column | Type | Description |
|--------|------|-------------|
| id | serial PK | Auto-increment ID |
| name | varchar(255) | Backtest name |
| start_date / end_date | date | Date range |
| top_k | int | Top-K stock selection |
| rebalance_freq | int | Rebalance frequency (days) |
| rolling | boolean | Rolling training flag |
| benchmark | varchar(50) | Benchmark index (CSI300) |
| metrics | json | Performance metrics JSON |
| status | varchar(20) | completed/running/failed |
| created_at | timestamp | Creation time |

### equity_curve
| Column | Type | Description |
|--------|------|-------------|
| id | serial PK | Auto-increment ID |
| backtest_id | bigint FK | Associated backtest |
| trade_date | date | Trading date |
| total_value | decimal(18,4) | Portfolio value |
| normalized_value | decimal(18,6) | Normalized to 1.0 |
| benchmark_normalized | decimal(18,6) | Benchmark normalized |

### model_registry
| Column | Type | Description |
|--------|------|-------------|
| id | serial PK | Auto-increment ID |
| name | varchar(255) | Model name |
| path | varchar(500) | Model file path |
| feature_columns | json | Feature list |
| train_start / train_end | date | Training period |
| created_at | timestamp | Creation time |

### factor_importance
| Column | Type | Description |
|--------|------|-------------|
| id | serial PK | Auto-increment ID |
| model_id | bigint FK | Associated model |
| factor_name | varchar(100) | Feature name |
| importance | decimal(10,6) | Importance score |
| rank | int | Rank by importance |

## API Endpoints (tRPC)

| Router | Procedure | Type | Description |
|--------|-----------|------|-------------|
| health | check | query | Health check + version |
| dbInfo | stats | query | Database statistics |
| backtest | list | query | List backtest runs |
| backtest | getById | query | Single backtest details |
| equityCurve | getByBacktestId | query | Equity curve data points |
| metrics | getByBacktestId | query | Performance metrics JSON |
| model | list | query | List all models |
| model | getById | query | Single model details |
| factor | getByModelId | query | Factor importances by model |

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server (port 3000) |
| `npm run build` | Build for production |
| `npm run check` | Type-check TypeScript |
| `npm run db:push` | Sync schema to database |
| `npm run db:generate` | Generate migration SQL |
| `npm run db:migrate` | Apply pending migrations |

## Mock Data

All API routers include mock data fallbacks — if the database is unavailable, realistic simulated data is returned so the dashboard always displays correctly. This enables:
- Frontend development without database setup
- Static deployment previews
- Graceful degradation in production

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | MySQL connection string |
| `APP_ID` | Yes | Application ID |
| `APP_SECRET` | Yes | Application secret |

## Phase 2 Roadmap

- [ ] Async backtest execution via task queue
- [ ] WebSocket/SSE for real-time progress
- [ ] Phase 2 form validation with Zod
- [ ] User authentication (OAuth 2.0)
- [ ] SHAP value visualization
- [ ] Real-time data feed integration
