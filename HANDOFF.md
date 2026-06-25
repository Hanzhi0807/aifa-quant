# Handoff Guide - AifaQuant

> 本文档面向后续接力的开发者/Agent，说明项目结构、当前状态、已知问题和推荐下一步。

## 项目一句话

AifaQuant 是一个基于 **Python + DuckDB + LightGBM** 的 A股 AI 量化研究与回测框架，以 **同花顺 iFind MCP** 为主要数据源。

## 当前状态（v0.2.0）

- ✅ 项目骨架搭建完成
- ✅ iFind MCP 数据接入（股票、宏观、指数）
- ✅ DuckDB 本地存储 + 增量更新
- ✅ 技术面因子工程
- ✅ 基本面因子工程（PE / PB / ROE）
- ✅ 宏观因子工程（CPI / PMI / M2）
- ✅ LightGBM 选股模型
- ✅ 滚动窗口训练 / out-of-sample 预测
- ✅ TopK-Dropout 策略 + A股回测引擎
- ✅ 基准对比（沪深 300 超额收益）
- ✅ CLI 入口
- ✅ GitHub Actions CI（lint + test）
- ⚠️ 当前为研究与框架验证阶段，结果不代表实盘表现

## 目录速查

```
aifa_quant/
├── config/             # 配置管理，token 在 .env 中
├── data/
│   ├── adapters/       # iFind MCP 适配器
│   ├── pipeline/       # ETL / 增量更新
│   └── storage/        # DuckDB 封装
├── features/           # 因子工程
├── models/             # LightGBM 模型
├── strategy/           # 策略定义
├── backtest/           # 回测引擎 + 绩效指标
├── cli/                # 命令行入口
├── notebooks/          # 研究 notebook
└── tests/              # 单元测试
```

## 如何本地跑起来

```bash
cd d:/kimi/aifa_quant

# 1. 确认 .env 里有 iFind MCP token
cat .env

# 2. 安装依赖
pip install -r requirements.txt

# 3. 跑测试
pytest tests/ -v

# 4. 完整工作流
python -m aifa_quant.cli.main test-connection
python -m aifa_quant.cli.main data-update --start 20230101 --end 20241231
python -m aifa_quant.cli.main train --start 20230101 --end 20231231
python -m aifa_quant.cli.main backtest --start 20240101 --end 20241231 --top-k 3 --freq 5
```

## 关键设计决策

1. **不与 Abu 耦合**：Abu 仅作为参考，新项目独立维护。
2. **MCP 适配器**：iFind MCP 使用自然语言查询，返回 Markdown 表格。适配器负责解析、标准化列名、处理中文单位、合并不一致的成交量/成交额字段。
3. **数据存储**：DuckDB 本地文件，查询快、压缩率高、兼容 pandas。
4. **模型目标**：二分类预测未来 5 日是否上涨，输出概率作为选股评分。
5. **回测引擎**：自定义事件驱动，内置 A股规则（T+1、涨跌停、100 股手、手续费、印花税）。

## 已知问题与坑

| 问题 | 说明 | 建议修复方向 |
|------|------|-------------|
| 数据量小 | 当前仅 13 只股票已入库，目标完整上证 50 | 继续跑 `data-update` 增量拉取 |
| iFind 返回不稳定 | 不同股票/查询返回的列名和字段不一致 | 已在 `stock_mcp.py` 做合兼容处理，但仍需持续观察 |
| 日线长度限制 | 单次查询约返回 100 条日线 | 已按 4 个月分段拉取，50 只股票约 20 分钟 |
| 涨跌停判断简化 | 使用前一日成本价代替真实前收盘价 | 维护完整历史前收盘价字段 |
| 可能存在过拟合 | 小样本 + 多因子 | 扩展数据、滚动训练、正则化、特征筛选 |

## 推荐下一步（优先级排序）

1. **继续扩大股票池**
   - 当前已接入上证 50 全成分股查询，继续跑 `data-update` 完成 50 只日线入库。
   - 注意 iFind MCP 调用频率和配额。

2. **加入情绪因子**
   - `data/adapters/news_mcp.py` 仍是占位实现，可接入新闻情绪或舆情因子。

3. **参数优化**
   - 对 `top_k`、`rebalance_freq`、模型超参、滚动窗口长度做网格搜索或贝叶斯优化。

5. **特征筛选与可解释性**
   - 加入特征重要性、SHAP 分析、多重共线性检查。

6. **实盘/模拟盘**
   - 在 `execution/` 下实现 QMT 或 easytrader 接口。
   - 先跑模拟盘验证。

## 代码规范

- 使用 `ruff` 做 lint 和 format：`ruff check aifa_quant tests` / `ruff format aifa_quant tests`
- 使用 `pytest` 跑测试：`pytest tests/ -v`
- Python 版本支持：3.10 / 3.11 / 3.12 / 3.13

## 敏感信息

- `.env` 文件包含 iFind MCP token，**已加入 `.gitignore`**，不要提交到 Git。
- 如果 token 泄露，请在 iFind 后台重置。

## 联系人

- 创建者：ivyzhi0807 / jiangjas@gmail.com
- 仓库：https://github.com/ivyzhi0807/aifa-quant
- 当前版本：v0.2.0
