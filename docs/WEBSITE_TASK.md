# 网站前后端实现任务书

> 本文档面向后续接力的开发者 / Kimi 客户端，说明如何为 AifaQuant 项目构建一个带数据库的前后端网站，用于项目展示和轻量交互。
> 2026-06-26 更新：项目实际实现已从最初的 FastAPI/MySQL 方案改为 **React + Hono + tRPC + DuckDB**，本文档已同步。

---

## 1. 项目背景

- **仓库**: https://github.com/ivyzhi0807/aifa-quant
- **核心项目**: `aifa_quant`（Python + DuckDB + LightGBM 的 A股量化研究框架）
- **当前阶段**: v0.6.0，已具备数据接入、因子工程、滚动训练、回测、模拟交易、Web 可视化能力
- **网站实现**: 源码位于 `web/`，技术栈为 React + Vite + Hono + tRPC + DuckDB
- **目标**: 为项目添加一个**前后端网站**，实现：
  - 项目介绍与文档展示
  - 回测结果可视化（权益曲线、绩效指标、沪深 300 / 上证指数基准对比）
  - 模拟交易状态展示（按 profile 隔离的持仓、净值、订单）
  - （可选）网页触发滚动回测或模型训练

---

## 2. 能力边界说明

- **Kimi Code CLI 已能做的**：编写前后端代码、设计 API、生成测试数据、提交到 GitHub。
- **不能直接做的**：一键“制作并发布带数据库的网站”到公网。数据库 + 后端需要部署到具体平台（见下方推荐）。
- **当前方案**：网站直接读取本地 DuckDB，最适合本地运行或同机部署；公网部署需要把 DuckDB 一起打包或迁移到 PostgreSQL。

---

## 3. 推荐技术栈

### 当前实现

| 层 | 技术 |
|---|---|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Recharts |
| 后端 | Hono + tRPC 11.x + superjson |
| 数据库 | DuckDB（与核心项目一致） |
| 认证 | 无（公开访问） |

### 如要重构或扩展

| 层 | 极简版 | 现代版 |
|---|---|---|
| 前端 | HTML + Tailwind CSS + Chart.js | React + Vite + Recharts |
| 后端 | FastAPI | Hono / Express + tRPC |
| 数据库 | DuckDB | DuckDB / PostgreSQL |

### 部署组合

| 组合 | 前端 | 后端 | 数据库 | 成本 |
|---|---|---|---|---|
| 本地优先 | React dev server | Hono (Node.js) | 本地 DuckDB | 免费 |
| 一体化 | Vercel | Vercel Serverless Functions | Vercel Postgres / Supabase | 免费额度内 |
| 国内/低代码 | 妙搭 / Miaoda | 妙搭后端 | 妙搭应用数据库 | 取决于平台 |

---

## 4. 功能需求

### Phase 1：只读展示（已完成 ✅）

已由 Kimi 客户端在 `web/` 中实现并构建通过：

- [x] 首页：项目介绍、策略 profile 选择器、独立持仓、历史表现（叠加沪深 300 / 上证指数基准）、FAQ
- [x] 回测结果页：展示回测历史、权益曲线、绩效表、基准对比
- [x] 模型/因子页：展示当前使用的模型、特征列表、因子重要性
- [x] 数据页：展示数据库中股票数量、日期范围、最新更新日期
- [x] 数据来源：从后端 tRPC API 读取 DuckDB，DuckDB 不可用时自动降级为 mock 数据

### Phase 2：交互式回测（待做）

- [ ] 前端表单：选择时间区间、top_k、rebalance_freq、是否滚动训练、profile
- [ ] 点击“运行回测”后，后端异步执行 `aifa_quant` 的回测流程
- [ ] 使用任务队列（Redis/RQ/Celery）或后台线程，避免 HTTP 超时
- [ ] 结果存入数据库，前端轮询或 WebSocket 获取结果

---

## 5. 推荐目录结构

当前实际目录：

```
web/
├── api/                      # 后端 API
│   ├── routers/              # tRPC routers
│   │   ├── health.ts
│   │   ├── dbInfo.ts
│   │   ├── strategies.ts     # profile 列表、持仓、权益曲线
│   │   ├── backtest.ts
│   │   ├── equityCurve.ts
│   │   ├── metrics.ts
│   │   ├── model.ts
│   │   ├── factor.ts
│   │   ├── factorStore.ts
│   │   ├── risk.ts
│   │   └── refresh.ts
│   ├── queries/
│   │   ├── duckdb.ts         # DuckDB 只读查询封装
│   │   └── connection.ts     # 旧 MySQL 连接（已弃用）
│   ├── middleware.ts
│   ├── router.ts
│   ├── context.ts
│   └── boot.ts
├── db/                       # 旧 Drizzle schema（已弃用）
├── src/                      # React 前端
│   ├── pages/
│   ├── components/
│   └── App.tsx
└── package.json
```

---

## 6. API 设计（当前 tRPC）

| Procedure | 类型 | 说明 |
|---|---|---|
| `health.check` | query | 健康检查 + 版本 |
| `dbInfo.stats` | query | 数据库统计 |
| `strategies.list` | query | 所有 profile 最新收益与持仓数 |
| `strategies.getPicks` | query | 指定 profile 当前选股 |
| `strategies.getEquity` | query | 指定 profile 净值 + 基准归一化曲线 |
| `backtest.list` | query | 回测历史列表 |
| `backtest.getById` | query | 单次回测详情 |
| `equityCurve.getByBacktestId` | query | 回测权益曲线 |
| `metrics.getByBacktestId` | query | 绩效指标 JSON |
| `model.list` | query | 模型注册表 |
| `factor.getByModelId` | query | 模型因子重要性 |

### 示例响应

#### `dbInfo.stats`

```json
{
  "total_symbols": 1800,
  "date_range": {"min": "2025-01-02", "max": "2026-06-26"},
  "latest_trade_date": "2026-06-26"
}
```

#### `metrics.getByBacktestId`

```json
{
  "total_return": 0.2655,
  "annual_return": 0.1278,
  "sharpe_ratio": 1.35,
  "max_drawdown": -0.1523,
  "benchmark_total_return": 0.1468,
  "excess_return": 0.1187
}
```

---

## 7. 数据库表设计

当前 Web 直接读取核心项目 DuckDB 的以下表：

- `daily_quotes` — 日线行情（股票 + 指数）
- `stock_universe` — 股票代码与名称
- `paper_positions` — 模拟交易持仓（按 `profile` 隔离）
- `paper_orders` — 模拟交易订单（按 `profile` 隔离）
- `paper_nav` — 模拟交易净值（按 `profile` 隔离）
- `model_registry` — 模型注册表
- `backtest_runs` / `equity_curve`（如使用）— 回测记录

> 旧 `web/db/` 下的 Drizzle MySQL schema 保留但已弃用。如果未来需要线上多用户版本，再考虑 PostgreSQL/MySQL。

---

## 8. 与核心项目 `aifa_quant` 的集成方式

### 当前方式：直接读取 DuckDB

Web 后端通过 `web/api/queries/duckdb.ts` 直接打开项目根目录下的 `data_store/aifa_quant.duckdb`，无需额外 HTTP 服务。

### 可选扩展：Python subprocess

如需网页触发回测/训练，可通过 Hono 调用子进程：

```typescript
// api/routers/backtestRunner.ts
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

### 可选扩展：HTTP API bridge

把 Python 核心包装成 FastAPI 服务，Hono 通过 HTTP 调用。适合把前后端分离部署的场景。

---

## 9. 安全与注意事项

1. **不要把 `.env` 提交到 Git**  
   后端读取 `.env` 获取 iFind token，前端代码中不能出现任何 token。

2. **不要把完整 DuckDB 提交到 Git**  
   数据库文件大且可能包含敏感数据，已加入 `.gitignore`。

3. **线上回测注意超时**  
   LightGBM 训练 + 滚动回测可能跑几十秒到几分钟，HTTP 默认超时不够。使用异步任务队列或 SSE/WebSocket 推送进度。

4. **区分开发和生产数据库**  
   本地用 DuckDB；线上如需多实例，可迁移到 PostgreSQL 并通过环境变量切换。

---

## 10. 部署步骤

### 本地开发

```bash
cd web
npm install
npm run dev
```

然后打开 `http://localhost:3000`。

### 生产构建

```bash
cd web
npm install
npm run build
NODE_ENV=production node dist/boot.js
```

> `duckdb` 是外部原生依赖，不能被打包进 `dist/boot.js`，生产环境需要保留 `node_modules`。

### Docker（需能拉取基础镜像）

```bash
docker compose up --build -d
```

访问 `http://localhost:3000`。

---

## 11. 验收标准

- [x] 网站能正常打开，展示项目介绍
- [x] 能读取 DuckDB 展示真实数据
- [x] 能用图表展示权益曲线和沪深 300 / 上证指数基准曲线
- [x] 能按 profile 展示独立持仓和最新收益
- [ ] （Phase 2）网页能触发回测并展示结果
- [x] `.env` 和数据库文件未提交到 Git

---

## 12. 给谁看

本文档是给 **Kimi 客户端 / 后续开发者** 的任务说明。实现时，先读 GitHub 仓库根目录的 `README.md`、`HANDOFF.md`、`CHANGELOG.md`，再参考本文档实现网站。
