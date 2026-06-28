# AifaQuant 文档

AifaQuant 是一个面向 A 股的 AI 量化研究框架，支持数据获取、特征工程、模型训练、回测、模拟交易和 Web 可视化。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 首次拉取数据（沪深300+中证500+中证1000，2025年起）
python scripts/daily_refresh.py --force --skip-paper-trade

# 3. 训练模型
python -m aifa_quant.cli.main train --start 20250101 --end 20260626 --no-sentiment --cache-only

# 4. 回测
python -m aifa_quant.cli.main backtest --start 20250101 --end 20260626 --benchmark 000300.SH --top-k 5 --freq 5 --no-sentiment --cache-only

# 5. 启动 Web
python -m aifa_quant.cli.main web
```

> 如果没有 `aifa web` 命令，直接 `cd web && npm install && npm run dev`。

## 文档目录

- [数据源与本地存储](DATA.md)
- [模拟交易](PAPER_TRADING.md)
- [回测指标说明](METRICS.md)
- [集成路线图](INTEGRATION_ROADMAP.md)
- [开发路线图](ROADMAP.md)

## 主要特性

- **多数据源**：AkShare、Tushare、iFind MCP
- **本地优先**：DuckDB 本地缓存，首次拉取后每日增量更新
- **特征工程**：技术指标、Alpha101/191 因子、基本面、宏观、情绪因子
- **模型**：LightGBM 二分类 / LambdaRank 排序 / Ensemble 集成
- **策略风格**：5 种投资者偏好 profile（aggressive / balanced / conservative / growth / value）
- **回测**：事件驱动，支持 A 股涨跌停规则与沪深 300 / 上证指数基准对比
- **模拟交易**：按 profile 隔离持仓，ATR 三层风控
- **可解释性**：SHAP 特征重要性分析
- **Web**：React + Hono + DuckDB 实时查询
- **自动化**：每日数据刷新 + 每周 AI 选股报告
