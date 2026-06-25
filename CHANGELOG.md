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
- 接入新闻情绪因子与另类数据。
- 增加参数优化与多策略对比。
- 实现模拟盘/实盘接口（QMT / easytrader）。
