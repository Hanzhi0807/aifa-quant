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

## [Unreleased]

### Planned
- 扩展股票池至 50-300 只，提升样本多样性。
- 加入财务、估值、宏观、新闻情绪因子。
- 实现滚动训练/交叉验证，降低过拟合。
- 接入沪深 300 等基准，计算超额收益。
- 增加参数优化与多策略对比。
- 接入模拟盘/实盘接口（QMT / easytrader）。
