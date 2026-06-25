# AifaQuant - A股 AI 量化研究框架

个人本地运行的 A股 AI 量化研究与回测系统，以同花顺 iFind MCP 为主要数据源，支持从数据获取、因子构建、模型训练、策略回测到模拟交易的完整闭环。

## 快速开始

1. 复制环境变量模板并填入你的 MCP token（已完成 `.env`）：
   ```bash
   cp .env.example .env
   # 编辑 .env 填入真实 token
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 测试数据连接：
   ```bash
   python -m aifa_quant.cli.main test-connection
   ```

4. 更新本地数据：
   ```bash
   python -m aifa_quant.cli.main data-update --start 20230101 --end 20241231
   ```

5. 训练选股模型：
   ```bash
   python -m aifa_quant.cli.main train --start 20230101 --end 20231231 --horizon 5
   ```

6. 运行回测：
   ```bash
   python -m aifa_quant.cli.main backtest --start 20240101 --end 20241231 --top-k 3 --freq 5
   ```

## 项目结构

- `config/` - 配置管理（Pydantic Settings + `.env`）
- `data/adapters/` - iFind MCP 适配器（股票、宏观、新闻、指数）
- `data/storage/` - DuckDB 本地存储
- `data/pipeline/` - ETL 与增量更新
- `features/` - 因子工程（技术、财务、宏观、情绪）
- `models/` - AI 模型（LightGBM 等）
- `strategy/` - 策略定义
- `backtest/` - 回测引擎与绩效分析
- `execution/` - 模拟/实盘交易执行
- `cli/` - 命令行入口
- `notebooks/` - 研究与探索

## CLI 命令

```bash
# 查看帮助
python -m aifa_quant.cli.main --help

# 常用工作流
python -m aifa_quant.cli.main test-connection
python -m aifa_quant.cli.main data-update --start 20230101 --end 20241231
python -m aifa_quant.cli.main db-info
python -m aifa_quant.cli.main train --start 20230101 --end 20231231
python -m aifa_quant.cli.main backtest --start 20240101 --end 20241231 --top-k 3
```

## 当前 baseline 回测结果（示例）

使用上证 50 成分股中 10 只、2023 年训练、2024 年测试：

| 指标 | 数值 |
|------|------|
| 总收益率 | 26.55% |
| 年化收益率 | 227.61% |
| 年化波动率 | 26.75% |
| 夏普比率 | 8.510 |
| 最大回撤 | -3.25% |
| 日胜率 | 63.27% |

> ⚠️ 以上为极小规模样本的演示结果，存在过拟合和幸存者偏差风险，不代表实盘表现。

## 安全提示

`.env` 文件包含你的 iFind MCP token，**绝对不要提交到 Git**（已在 `.gitignore` 中排除）。
