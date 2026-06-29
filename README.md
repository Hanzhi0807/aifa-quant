# AI Factor Alpha（AIFA） Quant · 爱发量化

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
![License](https://img.shields.io/badge/license-MIT-green)
[![Release](https://img.shields.io/github/v/release/ivyzhi0807/aifa-quant)](https://github.com/ivyzhi0807/aifa-quant/releases)

> **⚠️ 免责声明**
>
> AifaQuant 是一个**量化研究与学习框架**，所有代码、示例、回测结果和模拟交易结果**仅供技术研究参考，不构成任何投资建议**。
> 作者不对因使用本项目而产生的任何投资亏损、交易风险或法律责任负责。在将任何策略用于实盘之前，请自行充分回测、风险评估，并遵守所在国家/地区的法律法规。

---

AifaQuant 是一个**本地优先的 A股 AI 量化研究与回测框架**，覆盖数据获取、因子工程、模型训练、策略回测、模拟交易到 Web 可视化的完整闭环。

## 核心特性

- **本地数据优先**：所有市场数据和模拟交易状态保存在本地 DuckDB，首次部署拉取，之后每日增量更新，**不提交 GitHub**。
- **多数据源**：默认 [AkShare](https://www.akshare.xyz/)（免费，无需 token）；可选 [Tushare Pro](https://tushare.pro/)（需 token）。如需商业基本面、宏观或资讯数据，可自行接入 iFinD 等数据服务。
- **股票池**：沪深 300 + 中证 500 + 中证 1000 合并选股池，约 **1800 只** A股。
- **时间范围**：日线默认从 **2025-01-01** 起增量更新。
- **因子工程**：技术指标、Alpha101/191 风格因子、基本面（PE/PB/ROE）、宏观（CPI/PMI/M2）、情绪数据、高相关性剔除。
- **模型**：LightGBM 二分类 / LambdaRank 排序 / Ensemble 集成 / XGBoost。
- **策略风格**：5 种投资者偏好 profile（激进 / 均衡 / 稳健 / 成长 / 价值），通过 `factor_weights` 让不同策略选出不同股票。
- **风控**：ATR 三层止损止盈（止损、止盈、单日暴跌、利润回撤），仓位 sizing 为 `target_risk / (N × ATR)`。
- **回测**：A股规则引擎（T+1、涨跌停、100 股整数手、佣金、印花税），支持沪深 300 / 上证指数基准对比。
- **模拟交易**：按 profile 隔离持仓，虚拟成交并持久化到 DuckDB。
- **Web 仪表盘**：React + Hono + tRPC + DuckDB，支持 profile 切换、独立持仓、基准叠加权益曲线。
- **自动化**：`scripts/daily_refresh.py` 每日增量刷新数据并自动运行模拟交易；`scripts/push_to_supabase.py` 将信号推送到云端看板；每周 AI 选股报告自动生成。

---

## 目录

- [复制给你的 Agent（零基础上手）](#复制给你的-agent零基础上手)
- [快速开始](#快速开始)
- [标准工作流](#标准工作流)
- [CLI 命令速查](#cli-命令速查)
- [项目结构](#项目结构)
- [数据工作流](#数据工作流)
- [Profile 与风控](#profile-与风控)
- [Web 仪表盘](#web-仪表盘)
- [Docker 一键启动](#docker-一键启动)
- [注意事项](#注意事项)
- [文档索引](#文档索引)

---

## 复制给你的 Agent（零基础上手）

> 请帮我完成 AifaQuant 项目的初始配置并跑通完整工作流：
> 1. 进入项目根目录（例如 `D:\workspace\AI QUANT` 或你 clone 到的目录）。
> 2. 确认已安装 Python 3.10、3.11 或 3.12。
> 3. 创建虚拟环境 `.venv`：Windows 运行 `python -m venv .venv` 并激活 `.venv\Scripts\activate`；macOS/Linux 运行 `python3 -m venv .venv` 并激活 `source .venv/bin/activate`。
> 4. 安装依赖：`pip install -r requirements.txt`。
> 5. 复制 `.env.example` 为 `.env`。如果只想使用免费数据，外部数据源 token 可以暂时留空。
> 6. 运行测试确认环境正常：`pytest tests/ -q`。
> 7. 首次拉取数据：`python scripts/daily_refresh.py --force --skip-paper-trade`。
> 8. 查看数据概况：`python -m aifa_quant.cli.main db-info`。
> 9. 训练选股模型：`python -m aifa_quant.cli.main train --start 20250101 --end <今天日期> --no-sentiment --cache-only`。
> 10. 初始化模拟账户：`python -m aifa_quant.cli.main paper-trade reset --cash 1000000 --all-profiles`。
> 11. 运行所有 profile 的模拟交易：`python -m aifa_quant.cli.main paper-trade run --all-profiles`。
> 12. 启动前端：`cd web && npm install && npm run dev`，然后打开 `http://localhost:3000`。
> 每完成一步请向我汇报结果；如果遇到报错，先尝试修复并继续。

---

## 快速开始

### 1. 环境准备

```bash
cd <aifa-quant-project-root>

# 创建并激活虚拟环境（Windows 示例）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制并编辑 .env（外部数据源 token 可选）
cp .env.example .env
```

> `.env` 与 `data_store/` 已加入 `.gitignore`，**不要提交到 Git**。

### 2. 首次拉取数据

```bash
python scripts/daily_refresh.py --force --skip-paper-trade
```

这会：

- 合并沪深 300 / 中证 500 / 中证 1000 成分股，约 1800 只；
- 从 2025-01-01 起拉取日线行情；
- 同步更新沪深 300、上证指数、中证 500、中证 1000 指数日线；
- 跳过模拟交易（此时还没有训练好的模型）。

### 3. 验证数据

```bash
python -m aifa_quant.cli.main db-info
```

---

## 标准工作流

```bash
# 1. 每日收盘后增量刷新（首次已用 --force 跑过）
python scripts/daily_refresh.py

# 2. 训练模型（把 <今天日期> 换成实际日期，例如 20260628）
python -m aifa_quant.cli.main train \
  --start 20250101 --end <今天日期> \
  --no-sentiment --cache-only

# 3. 滚动回测（带沪深 300 基准）
python -m aifa_quant.cli.main backtest \
  --start 20250101 --end <今天日期> \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 --no-sentiment --cache-only

# 4. 初始化模拟账户（所有 profile）
python -m aifa_quant.cli.main paper-trade reset --cash 1000000 --all-profiles

# 5. 试跑单个 profile
python -m aifa_quant.cli.main paper-trade run --profile balanced --dry-run

# 6. 正式运行所有 profile 模拟交易
python -m aifa_quant.cli.main paper-trade run --all-profiles

# 7. 查看状态
python -m aifa_quant.cli.main paper-trade status

# 8. 生成每周选股报告
python -m aifa_quant.cli.main weekly-report --cache-only

# 9. SHAP 模型解释
python -m aifa_quant.cli.main explain \
  --start 20250101 --end <今天日期> \
  --output data_store/reports/shap --cache-only
```

> 日常运行只需第 1 步：`scripts/daily_refresh.py` 会自动增量更新数据并执行所有 profile 的模拟交易。

---

## CLI 命令速查

| 命令 | 作用 |
|------|------|
| `python scripts/daily_refresh.py` | 每日增量刷新数据 + 指数 + 模拟交易 |
| `python scripts/daily_refresh.py --force --skip-paper-trade` | 首次全量拉取数据 |
| `python scripts/push_to_supabase.py` | 推送所有 profile 信号到 Supabase 云端 |
| `python scripts/update_index_data.py` | 同步更新指数基准 |
| `python -m aifa_quant.cli.main data-update --universe 沪深300 --start 20250101 --end <今天日期>` | 用 AkShare 更新日线数据 |
| `python -m aifa_quant.cli.main db-info` | 查看 DuckDB 数据概览 |
| `python -m aifa_quant.cli.main train --start 20250101 --end <今天日期>` | 训练 LightGBM 模型 |
| `python -m aifa_quant.cli.main backtest --start 20250101 --end <今天日期> --top-k 5` | 回测 |
| `python -m aifa_quant.cli.main paper-trade reset --cash 1000000 --all-profiles` | 初始化模拟账户 |
| `python -m aifa_quant.cli.main paper-trade run --all-profiles` | 执行所有 profile 模拟交易 |
| `python -m aifa_quant.cli.main paper-trade status` | 查看模拟账户 |
| `python -m aifa_quant.cli.main factor-analysis --start 20250101 --end <今天日期>` | 因子有效性分析 |
| `python -m aifa_quant.cli.main weekly-report --cache-only` | 生成每周 AI 选股报告 |
| `python -m aifa_quant.cli.main explain --output data_store/reports/shap --cache-only` | SHAP 可解释性分析 |

常用参数：

- `--source {akshare,tushare}`：数据源，默认 `akshare`。
- `--cache-only`：只使用 DuckDB 缓存，不调用外部数据源。
- `--no-sentiment`：关闭新闻情绪因子。
- `--sentiment-source free`：使用东方财富 / AkShare 免费情绪数据。
- `--rolling`：滚动窗口训练，避免未来函数。
- `--profile {aggressive,balanced,conservative,growth,value}`：指定投资者偏好 profile。
- `--all-profiles`：依次运行所有 profile。

---

## 项目结构

```text
aifa_quant/
├── aifa_quant/               # Python 核心包
│   ├── data/                 # 数据源适配器、DuckDB 存储、增量更新 Pipeline
│   ├── features/             # 因子工程（技术 / Alpha101 / 基本面 / 宏观 / 情绪）
│   ├── models/               # LightGBM / LambdaRank / Ensemble / XGBoost
│   ├── strategy/             # TopK-Dropout 策略、策略模板、5 种 profile
│   ├── risk/                 # ATR 止损/止盈/回撤/暴跌风控
│   ├── backtest/             # A股规则回测引擎 + 绩效指标
│   ├── paper_trading/        # 模拟交易引擎
│   ├── analysis/             # 因子分析 / SHAP
│   ├── research/             # 每周选股报告
│   └── cli/                  # Typer 命令行入口
├── web/                      # 本地仪表盘（React + Hono + tRPC + DuckDB）
├── signals-web/              # 云端信号看板（React + Vite + Supabase，部署 Vercel）
├── scripts/                  # 每日刷新、指数更新、Supabase 推送等脚本
├── tests/                    # 单元测试
├── data_store/               # DuckDB、模型、报告（不提交 Git）
└── docs/                     # 文档
```

---

## 数据工作流

AifaQuant 采用**本地优先**的数据策略：

1. **首次部署**：`scripts/daily_refresh.py --force --skip-paper-trade` 一次性拉取约 1800 只股票从 2025-01-01 起的日线和指数数据。
2. **每日增量**：`scripts/daily_refresh.py` 工作日自动增量更新日线、指数，并运行所有 profile 的模拟交易。
3. **云端推送**：`scripts/push_to_supabase.py` 将本地 DuckDB 中的持仓数据推送到 Supabase，供云端信号看板展示。
4. **备份迁移**：直接复制 `data_store/aifa_quant.duckdb` 即可，**不通过 GitHub Release 分发数据**。

详见 [`docs/DATA.md`](docs/DATA.md)。

---

## Profile 与风控

### 5 种投资者偏好

| Profile | 名称 | 持仓数 | 风格 |
|---------|------|--------|------|
| `aggressive` | 激进型 | 5 | 高集中度，追求高收益 |
| `balanced` | 均衡型 | 8 | 攻守兼备 |
| `conservative` | 稳健型 | 12 | 分散持仓，严格控制回撤 |
| `growth` | 成长型 | 6 | 聚焦高成长潜力股 |
| `value` | 价值型 | 8 | 低估值选股，安全边际优先 |

### 差异化逻辑

不同 profile 不仅 `top_k` 不同，还会通过 `apply_profile_score()` 按 `factor_weights` 加权特征列前缀，使模型为不同风格选出不同股票：

```
final_score = 0.7 × model_score + 0.3 × profile_factor_score
```

### 风控

- 仓位 sizing：`target_risk_pct / (N × ATR)`，默认 `N = 2`；
- ATR 三层风控：止损、止盈、单日暴跌、利润回撤；
- 大盘震荡时跳过新买入（`market_choppy`）。

详见 [`docs/PAPER_TRADING.md`](docs/PAPER_TRADING.md)。

---

## Web 仪表盘

### 本地版（web/）

```bash
cd web
npm install
npm run dev
```

打开 `http://localhost:3000`。

首页包含：

- 策略 profile 选择器；
- 每个 profile 的独立持仓（已按仓位占比排序，仓位最大的是 1 号）；
- 历史表现权益曲线，叠加沪深 300、上证指数归一化曲线；
- FAQ 与风险提示。

生产构建：

```bash
npm run build
NODE_ENV=production node dist/boot.js
```

> Web 直接读取本地 DuckDB，不再依赖 MySQL。部署说明见 [`web/DEPLOY.md`](web/DEPLOY.md)。

### 云端信号看板（signals-web/）

独立的轻量前端，部署在 **Vercel**，后端使用 **Supabase**（PostgreSQL + Auth + RLS）。每日收盘后由 `scripts/push_to_supabase.py` 将 5 个 profile 的持仓信号推送到云端数据库，推送后即可随时查看最新信号。

**技术栈**：React 19 + Vite + TailwindCSS 4 + Supabase JS SDK

**功能**：
- Supabase Auth 邮箱登录；前端不开放注册，访问权限由 Supabase RLS + `allowed_emails` 白名单控制；
- 5 种策略 profile 一键切换（激进 / 均衡 / 稳健 / 价值 / 成长）；
- 每日当前持仓信号排名（按持仓市值）+ 当日持仓推荐卡片；
- Vercel 部署，可绑定仓库自动部署或手动部署。

**本地开发**：

```bash
cd signals-web
npm install
npm run dev
```

**Supabase 初始化**：

1. 在 Supabase SQL Editor 中执行 [`supabase/schema.sql`](supabase/schema.sql)。
2. 只给受邀邮箱授权访问：

```sql
insert into public.allowed_emails (email, note)
values ('reader@example.com', 'friend');
```

**环境变量**：

前端本地 `.env` 或 Vercel 面板只配置 anon key：

```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbG...
```

根目录 `.env` 配置服务端推送密钥，**不要放到 Vercel 前端环境变量**：

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...
```

**数据推送**：

```bash
# 推送所有 profile 到 Supabase
python scripts/push_to_supabase.py

# 仅推送单个 profile
python scripts/push_to_supabase.py --profile balanced
```

> 推送使用 Service Role Key（绕过 RLS），需在 `.env` 中配置 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY`。

---

## Docker 一键启动

已提供 `Dockerfile` 与 `docker-compose.yml`：

```bash
docker compose up --build -d
```

访问 `http://localhost:3000`。

> ⚠️ 本机构建受网络限制可能无法拉取 `python:3.12-slim` / `node:22-slim`，需要配置镜像源或离线导入基础镜像。

---

## 注意事项

- **情绪因子默认关闭**：需要时可使用 `--sentiment-source free` 通过东方财富/AkShare 获取免费情绪数据。
- **成分股非历史真实**：AkShare 返回当前最新成分股，非 point-in-time，长周期回测存在幸存者偏差。
- **模型需要重训**：现有模型基于沪深 300 训练，扩大到中证 500/1000 后建议用新 universe 重新训练。
- **DuckDB 锁**：Web 查询后会正确关闭连接；若 dev server 进程异常未退出，仍可能锁库，Windows 下请手动结束对应 Node/Python 进程。
- **数据不提交 Git**：`data_store/` 与 `*.duckdb` 已加入 `.gitignore`。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [`HANDOFF.md`](HANDOFF.md) | 开发者交接指南、标准工作流、已知问题 |
| [`docs/DATA.md`](docs/DATA.md) | 数据源、DuckDB 表结构、本地数据工作流 |
| [`docs/PAPER_TRADING.md`](docs/PAPER_TRADING.md) | 模拟交易完整使用说明 |
| [`docs/METRICS.md`](docs/METRICS.md) | 回测绩效指标说明 |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 产品迭代路线图 |
| [`docs/INTEGRATION_ROADMAP.md`](docs/INTEGRATION_ROADMAP.md) | 外部能力接入计划 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本变更记录 |
| [`AGENTS.md`](AGENTS.md) | 给 AI Agent 的规则手册 |
