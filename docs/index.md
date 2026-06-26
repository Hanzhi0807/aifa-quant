# AifaQuant 文档

AifaQuant 是一个面向 A 股的 AI 量化研究框架，支持数据获取、特征工程、模型训练、回测、模拟交易和 Web 可视化。

## 快速开始

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 下载数据
aifa data-update --start 20230101 --end 20241231 --universe 沪深300 --source akshare

# 3. 训练模型
aifa train --start 20230101 --end 20241231 --name lgb_stock_selector

# 4. 回测
aifa backtest --start 20240101 --end 20241231 --model lgb_stock_selector

# 5. 启动 Web
aifa web
```

## 文档目录

- [数据源与集成](DATA.md)
- [回测指标说明](METRICS.md)
- [模拟交易](PAPER_TRADING.md)
- [集成路线图](INTEGRATION_ROADMAP.md)
- [开发路线图](ROADMAP.md)

## 主要特性

- **多数据源**：AkShare、Tushare、iFind MCP
- **特征工程**：技术指标、Alpha101/191 因子、基本面、宏观、情绪因子
- **模型**：LightGBM 二分类 / LambdaRank 排序 / Ensemble 集成
- **回测**：事件驱动，支持 A 股涨跌停规则
- **可解释性**：SHAP 特征重要性分析
- **Web**：React + Hono + DuckDB 实时查询
- **自动化**：每周 AI 选股报告
