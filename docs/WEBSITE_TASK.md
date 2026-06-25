# 网站前后端实现任务书

> 本文档面向后续接力的开发者 / Kimi 客户端，说明如何为 AifaQuant 项目构建一个带数据库的前后端网站，用于项目展示和轻量交互。

---

## 1. 项目背景

- **仓库**: https://github.com/ivyzhi0807/aifa-quant
- **核心项目**: `aifa_quant`（Python + DuckDB + LightGBM 的 A股量化研究框架）
- **当前阶段**: v0.2.0，已具备数据接入、因子工程、滚动训练、回测、基准对比能力。
- **目标**: 为项目添加一个**前后端网站**，实现：
  - 项目介绍与文档展示
  - 回测结果可视化（权益曲线、绩效指标、沪深 300 基准对比）
  - 历史模型/回测记录的数据库存储
  - （可选）网页触发滚动回测或模型训练

---

## 2. 能力边界说明

- **Kimi Code CLI 已能做的**：编写前后端代码、设计 API、生成测试数据、提交到 GitHub。
- **不能直接做的**：一键“制作并发布带数据库的网站”到公网。数据库 + 后端需要部署到具体平台（见下方推荐）。
- **建议方案**：先用 **Vercel/Netlify + Render/Railway/Fly.io** 做一个免费托管版；如果 Kimi 客户端支持“妙搭 / Spark / Miaoda”等低代码平台，也可按本文档的接口规范实现。

---

## 3. 推荐技术栈

### 前端
- **极简版**：HTML + Tailwind CSS + Chart.js
- **现代版**：React + Vite + Recharts/Ant Design Charts
- **托管**：GitHub Pages / Vercel / Netlify

### 后端
- **FastAPI**（推荐）：异步、自动文档、适合数据/模型类项目
- 备选：Flask / Django Ninja

### 数据库
- **开发/本地**：DuckDB（与核心项目一致）
- **线上**：PostgreSQL / SQLite（小项目够用）
- 如果部署到 Render/Railway，通常自带 PostgreSQL

### 部署组合（推荐）

| 组合 | 前端 | 后端 | 数据库 | 成本 |
|---|---|---|---|---|
| 免费入门 | GitHub Pages | Render / Railway | Render/Railway PostgreSQL | 免费额度内 |
| 一体化 | Vercel | Vercel Serverless Functions | Vercel Postgres / Supabase | 免费额度内 |
| 国内/低代码 | 妙搭 / Miaoda | 妙搭后端 | 妙搭应用数据库 | 取决于平台 |

---

## 4. 功能需求

### Phase 1：只读展示（先做）
- [ ] 首页：项目介绍、核心能力、快速开始
- [ ] 回测结果页：展示最近一次回测的权益曲线、绩效表、沪深 300 基准对比
- [ ] 模型/因子页：展示当前使用的模型、特征列表、因子重要性（可后续补充 SHAP）
- [ ] 数据页：展示数据库中股票数量、日期范围、最新更新日期
- [ ] 数据来源：从后端 API 读取数据库或静态 JSON

### Phase 2：交互式回测（后做）
- [ ] 前端表单：选择时间区间、top_k、rebalance_freq、是否滚动训练
- [ ] 点击“运行回测”后，后端异步执行 `aifa_quant` 的回测流程
- [ ] 使用任务队列（Redis/RQ/Celery）或后台线程，避免 HTTP 超时
- [ ] 结果存入数据库，前端轮询或 WebSocket 获取结果

---

## 5. 推荐目录结构

建议新建一个独立仓库或放在 `aifa-quant/web/` 子目录：

```
aifa-quant-web/                 # 或 aifa-quant/web/
├── frontend/                   # 前端项目
│   ├── index.html
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api.js              # 封装后端 API 调用
│   │   └── charts.js           # 图表渲染
│   └── package.json
├── backend/                    # 后端项目
│   ├── main.py                 # FastAPI 入口
│   ├── api/
│   │   ├── backtest.py
│   │   ├── db_info.py
│   │   └── models.py
│   ├── core/
│   │   └── runner.py           # 调用 aifa_quant 逻辑
│   ├── database.py             # 数据库连接与模型
│   └── requirements.txt
├── data/                       # 线上数据目录（gitignore）
├── README.md
└── DEPLOY.md                   # 部署指南
```

---

## 6. API 设计（FastAPI）

```
GET  /api/health                # 健康检查
GET  /api/db-info               # 数据库统计
GET  /api/backtests             # 历史回测列表
GET  /api/backtests/{id}        # 单次回测详情
POST /api/backtests             # 触发新回测（Phase 2）
GET  /api/equity-curve/{id}     # 权益曲线数据
GET  /api/metrics/{id}          # 绩效指标
GET  /api/benchmark/{id}        # 基准对比数据
```

### 示例响应

#### GET /api/db-info
```json
{
  "total_records": 24200,
  "symbols": 50,
  "date_range": {"min": "2023-01-03", "max": "2024-12-31"}
}
```

#### GET /api/metrics/{id}
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

使用 SQLAlchemy 或直接用 DuckDB。建议先建三张表：

```sql
CREATE TABLE backtest_runs (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    start_date DATE,
    end_date DATE,
    top_k INTEGER,
    rebalance_freq INTEGER,
    rolling BOOLEAN,
    benchmark VARCHAR,
    metrics JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE equity_curve (
    id INTEGER PRIMARY KEY,
    backtest_id INTEGER,
    trade_date DATE,
    total_value DOUBLE,
    normalized_value DOUBLE,
    benchmark_normalized DOUBLE
);

CREATE TABLE model_registry_web (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    path VARCHAR,
    feature_columns JSON,
    train_start DATE,
    train_end DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. 与核心项目 `aifa_quant` 的集成方式

### 推荐方式 A：作为子模块/依赖引入
把 `aifa_quant` 核心项目发布为 Python 包或直接用 `git+https` 安装：

```bash
pip install git+https://github.com/ivyzhi0807/aifa-quant.git
```

后端 `runner.py` 中调用：

```python
from aifa_quant.features import FeatureBuilder
from aifa_quant.models.rolling_trainer import RollingTrainer
from aifa_quant.backtest import BacktestEngine, compute_metrics
from aifa_quant.strategy import TopKDropoutStrategy
```

### 推荐方式 B：本地相对路径（开发阶段）
如果网站仓库和核心仓库在同一目录：

```python
import sys
sys.path.insert(0, "../aifa-quant")
```

---

## 9. 安全与注意事项

1. **不要把 `.env` 提交到 Git**  
   后端读取 `.env` 获取 iFind token，前端代码中不能出现任何 token。

2. **不要把完整 DuckDB 提交到 Git**  
   数据库文件大且可能包含敏感数据，应加入 `.gitignore`。

3. **线上回测注意超时**  
   LightGBM 训练 + 滚动回测可能跑几十秒到几分钟，HTTP 默认超时不够。使用异步任务队列或 SSE/WebSocket 推送进度。

4. **区分开发和生产数据库**  
   本地用 DuckDB，线上用 PostgreSQL 或 SQLite，通过环境变量切换。

---

## 10. 部署步骤（Render + GitHub Pages 示例）

### 后端（Render）
1. 新建 Web Service，选择 Python。
2. 设置启动命令：`uvicorn backend.main:app --host 0.0.0.0 --port 10000`
3. 设置环境变量：`DATABASE_URL`、`IFIND_STOCK_MCP_URL`、`IFIND_STOCK_MCP_TOKEN` 等。
4. 部署后得到 `https://aifa-quant-api.onrender.com`。

### 前端（GitHub Pages）
1. 在仓库 `Settings → Pages` 中选择分支和 `frontend/` 目录。
2. 前端 `api.js` 中配置后端地址：
   ```js
   const API_BASE = "https://aifa-quant-api.onrender.com/api";
   ```
3. 发布得到 `https://ivyzhi0807.github.io/aifa-quant-web`。

---

## 11. 验收标准

- [ ] 网站能正常打开，展示项目介绍
- [ ] 能从后端读取最近一次回测的绩效指标
- [ ] 能用图表展示权益曲线和沪深 300 基准曲线
- [ ] （Phase 2）网页能触发回测并展示结果
- [ ] `.env` 和数据库文件未提交到 Git

---

## 12. 给谁看

本文档是给 **Kimi 客户端 / 后续开发者** 的任务说明。实现时，先读 GitHub 仓库根目录的 `README.md`、`HANDOFF.md`、`CHANGELOG.md`，再参考本文档实现网站。
