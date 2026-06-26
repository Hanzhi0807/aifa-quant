# Agent Guidelines - AifaQuant

> 面向后续接手本项目的 AI Agent / 开发者的规则手册。
> 只放“写代码时如果没看到就会犯错”的硬边界和踩坑警示，不写历史叙事。

## 1. 项目概览

- AifaQuant 是一个本地优先的 A股 AI 量化研究与回测框架。
- 代码在 `aifa_quant/` Python 包下。
- 所有 CLI 命令必须在项目根目录下执行（将 `<project-root>` 替换为你本地 clone 的目录）。

## 2. 必知环境

- **Python**：使用仓库根目录的 venv：`.venv/Scripts/python`（Windows）或 `.venv/bin/python`（macOS/Linux）。
- **CLI 入口**：`python -m aifa_quant.cli.main <command>`；也可用 `aifa <command>`（安装后）。
- **DuckDB**：`data_store/aifa_quant.duckdb`，thread-local 连接，禁止跨线程共享连接。
- **.env**：包含 iFind MCP token，**已加入 .gitignore，绝对不要提交**。
- **data_store/**：数据和模型目录，**已加入 .gitignore，绝对不要提交**。

## 3. 工作流红线

### 3.1 提交前必须跑

```bash
ruff check aifa_quant tests
pytest -q
```

### 3.2 数据源选择与 iFind 确认

- 默认数据源是 **AkShare**（免费），用于日线行情、指数行情、成分股列表。
- 可选 **Tushare Pro**（需 `TUSHARE_TOKEN`），回测/数据更新时 `--source tushare`。
- iFind MCP 只用于基本面（PE/PB/ROE）、宏观（CPI/PMI/M2）、新闻情绪（当前不可用）。
- 免费情绪因子可走东方财富/AkShare：`--sentiment-source free`。
- **任何会调用 iFind MCP 的 CLI 命令都会先提示用户确认**；脚本环境请加 `--yes` 跳过确认。
- iFind MCP 额度紧张，回测、训练、模拟交易默认应使用本地缓存：

```bash
python -m aifa_quant.cli.main backtest --no-sentiment --cache-only ...
python -m aifa_quant.cli.main train --no-sentiment --cache-only ...
python -m aifa_quant.cli.main paper-trade run ...
```

`paper-trade run` 内部已强制 `cache_only=True`。

### 3.3 情绪因子默认关闭

`--sentiment` 依赖 iFind news MCP，当前通常无数据/限流。不要默认开启。
需要情绪数据时可优先使用 `--sentiment-source free`（东方财富 / AkShare）。

### 3.4 不要修改 `.env`、DuckDB、模型文件后再提交

这些文件已被 Git 忽略，但本地改动不应出现在任何 commit 描述中。

## 4. 核心模块约定

| 模块 | 说明 | 关键文件 |
|------|------|----------|
| 数据层 | DuckDB 存储 + iFind MCP 适配器 | `data/storage/duckdb_store.py`, `data/adapters/` |
| 因子 | 技术/Alpha101/基本面/宏观/情绪因子 | `features/builder.py`, `features/alpha_factors.py` |
| 模型 | LightGBM 二分类 / LambdaRank / Ensemble | `models/lgb_ranker.py`, `models/lgb_lambdarank.py`, `models/ensemble.py`, `models/base.py` |
| 策略 | 默认 TopK-Dropout，支持策略模板 | `strategy/topk_dropout.py`, `strategy/templates.py` |
| 可解释性 | SHAP 特征重要性 | `analysis/shap_explainer.py` |
| 自动化 | 每周选股报告 | `research/weekly_picker.py` |
| 回测 | A股规则引擎 | `backtest/engine.py` |
| 模拟交易 | 基于 SimulatedBroker，状态持久化 | `paper_trading/engine.py`, `execution/broker/simulated_broker.py` |
| Web | React + Hono + tRPC，直接读 DuckDB；含因子商店、回测重跑 | `web/` |

## 5. 新增数据库表

如果在 DuckDB 新增业务表，必须同步：

1. 在 `data/storage/duckdb_store.py` 的 `_init_tables` 中建表；
2. 提供 `save_*` / `load_*` 方法；
3. 在 `README.md`、`HANDOFF.md`、相关 `docs/*.md` 中说明；
4. 加单元测试。

## 6. 策略与执行

- 默认选股策略是 `TopKDropoutStrategy`。
- 模拟交易通过 `SimulatedBroker` 成交，已内置 A股规则：100 股整数手、买入佣金最低 5 元、卖出印花税 0.1%、涨跌停过滤。
- 实盘接口（QMT / easytrader / Ptrade）尚未实现，需继续实现 `BaseBroker`。

## 7. 深入文档指针

| 主题 | 文档 |
|------|------|
| 快速开始 | `README.md` |
| 开发者交接 | `HANDOFF.md` |
| 模拟交易使用 | `docs/PAPER_TRADING.md` |
| 数据源说明 | `docs/DATA.md` |
| 绩效指标 | `docs/METRICS.md` |
| 外部能力接入计划 | `docs/INTEGRATION_ROADMAP.md` |
| 变更记录 | `CHANGELOG.md` |

## 8. 已知坑

- GitHub Actions 当前被禁用，CI 徽章不会更新。
- 沪深 300 成分股不完整（约 288 只），新浪财经抓取去重后缺失部分。
- Web UI 本地开发默认使用 `http://localhost:3000`，端口被占用时会自动切换。
- Web 生产构建需 `npm run build`；`duckdb` 是外部依赖，不能被打包进 `dist/boot.js`。
- Docker 一键启动需本地 Docker daemon 运行；Windows 上通常需要启动 Docker Desktop。
