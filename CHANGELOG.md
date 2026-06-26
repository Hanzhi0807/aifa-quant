# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-25

### Added
- 初始化 AifaQuant 项目骨架，模块化设计（data/features/models/strategy/backtest/cli）。
- 实现 iFind MCP Streamable HTTP 适配器，支持股票、宏观、新闻、指数四类数据源。
- 完成日线数据获取、清洗、标准化（OHLCV + 中文单位解析）并持久化到 DuckDB。
- 实现增量更新 Pipeline，支持每日收盘后增量拉取。
- 构建技术面因子库：收益率、均线、RSI、MACD、波动率、ATR、成交量等。
- 接入 LightGBM 二分类选股模型，输出上涨概率评分。
- 实现 TopK-Dropout 轮动策略。
- 实现 A股自定义回测引擎，考虑 T+1、涨跌停、100 股整数手、手续费、印花税。
- 提供 Typer 命令行入口：test-connection / data-update / db-info / train / backtest。
- 添加 Quickstart Jupyter Notebook。
- 配置 GitHub Actions CI（Python 3.10/3.11/3.12 + ruff lint + pytest）。
- 添加单元测试覆盖 adapter / storage / features / backtest 核心模块。

### Notes
- 当前 baseline 使用 10 只上证 50 成分股、2023 年训练、2024 年测试，结果仅供框架验证，不代表实盘表现。

## [0.2.0] - 2026-06-25

### Added
- 扩展股票池：上证 50 成分股从 10 只覆盖到完整 50 只（2023-2024 日线）。
- 新增基本面因子：市盈率 PE、市净率 PB、ROE（加权/摊薄/TTM）等，按报告期前向填充到日线。
- 新增宏观因子：CPI 同比、PMI、M2 同比，通过 iFind EDB MCP 接入。
- 新增 `RollingTrainer` 滚动训练器，按滑动窗口训练并在每个调仓日生成 out-of-sample 预测，避免按年份切分的未来函数和过拟合。
- 回测接入基准对比：支持沪深 300（000300.SH）等指数，计算基准收益、超额收益、超额夏普和日超额胜率。
- CLI `backtest` 新增 `--rolling` 与 `--benchmark` 参数；日线获取自动按 4 个月分段，突破单次返回行数限制。
- 新增 `features/fundamental.py`、`features/macro.py`、`models/rolling_trainer.py` 模块。

### Changed
- `FeatureBuilder.build_features` 增加 `include_fundamental` / `include_macro` 开关，默认开启。
- 回测引擎兼容外部预计算 `pred_score`（滚动训练结果），未提供时再调用模型预测。
- `data/adapters/stock_mcp.py` 支持分段拉取日线，`get_financial_data` 获取财务指标。
- `data/adapters/edb_mcp.py` / `index_mcp.py` 从占位实现改为可用适配器。

### Notes
- 当前回测使用滚动训练 + 50 只上证 50 成分股，结果仅供框架验证，不代表实盘表现。

## [Unreleased]

### Planned
- 接入新闻情绪因子与另类数据（待 iFind 配额恢复）。
- 增加参数优化与多策略对比。
- 实现实盘接口（QMT / easytrader / Ptrade）。

## [0.4.0] - 2026-06-26

### Added
- 新增模拟交易（Paper Trading）能力：
  - `aifa_quant/paper_trading/engine.py` 模拟交易引擎；
  - `SimulatedBroker` 增强，支持 A股规则（100 股手、佣金、印花税、涨跌停过滤）和 DuckDB 状态持久化；
  - CLI 新增 `paper-trade reset / run / status` 子命令；
  - 状态表 `paper_positions`、`paper_orders`、`paper_nav` 持久化到 DuckDB。
- 新增 `docs/PAPER_TRADING.md` 模拟交易使用说明。
- `FeatureBuilder` 支持 `prediction_mode=True`，用于预测时无需未来标签。
- 发布 GitHub Release `v0.4.0-data-full`：日线 + 基本面 + 宏观 gzip CSV。

### Changed
- `paper-trade run` 默认 `cache_only=True`，离线执行、不消耗 iFind 额度。
- `load_paper_cash` 按 `updated_at` 取最新现金，避免重置行干扰。

## [0.3.0] - 2026-06-25

### Added
- DuckDB 持久化基本面与宏观数据：`fundamental_data`、`macro_data` 表。
- CLI `data-update` 新增 `--fundamental`、`--macro`、`--skip-daily`、`--workers`。
- CLI `backtest` / `train` 新增 `--cache-only`、`--sentiment/--no-sentiment`、`--corr-threshold`。
- 增量更新 Pipeline：按 symbol 增量拉取、限速 5 req/s、thread-local DuckDB 连接。
- 情绪因子 SHAP 与解析修复，新增 `NewsMCPAdapter` 非表格 answer 解析。
- 全因子滚动回测（2023–2024 沪深 300）：总收益 336.37%，超额收益 335.16%。
- 网站前端本地化（中文）与仪表盘，本地 dev server 端口 3000。

### Changed
- `.env` 发现逻辑改为从 `settings.py` 向上查找项目根。
- 特征构建时排除 `created_at` 等时间列，避免 LightGBM 类型错误。
- 回测默认使用缓存数据，避免训练/回测阶段意外调用 iFind。

### Notes
- iFind news MCP 配额耗尽，情绪因子当前无数据，建议 `--no-sentiment`。
- GitHub Actions 仍被账号禁用，CI 徽章不会自动更新。
