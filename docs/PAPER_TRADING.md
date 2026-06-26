# AifaQuant 模拟交易（Paper Trading）使用说明

## 1. 什么是模拟交易

模拟交易让你在**不花真钱、也不调用 iFind 实时行情额度**的情况下，验证模型选出的股票在“今天”买入后表现如何。

本项目的模拟交易默认把 **DuckDB 本地缓存的最新交易日** 当作“今天”：

- 离线读取已缓存的日线、基本面、宏观数据；
- 用训练好的 LightGBM 模型给股票打分；
- 按 TopK-Dropout 策略选出目标持仓；
- 通过 `SimulatedBroker` 虚拟下单，并扣除佣金、印花税；
- 订单、持仓、净值自动写入 DuckDB，方便复盘和后续接入 Web UI。

> ⚠️ 这仍然是研究/验证工具，不代表真实实盘收益。

---

## 2. 前置条件

### 2.1 已有本地数据

确保 `data_store/aifa_quant.duckdb` 中已有日线数据。如果没有，可通过以下任一方式获取：

**方式 A：从 GitHub Release 导入（推荐，不消耗 iFind 额度）**

```bash
python scripts/import_source_data.py data_store/
```

**方式 B：从 iFind MCP 下载（需要 token 和额度）**

```bash
python -m aifa_quant.cli.main data-update \
  --symbol-file data_store/csi300_symbols.txt \
  --start 20230101 --end 20241231 \
  --workers 5 --fundamental --macro
```

### 2.2 已有训练好的模型

模拟交易需要 `data_store/models/lgb_stock_selector_latest.pkl`。如果没有，先训练：

```bash
python -m aifa_quant.cli.main train \
  --start 20230101 --end 20241231 \
  --no-sentiment --cache-only
```

---

## 3. 常用命令

所有命令都在项目根目录 `d:/kimi/aifa_quant` 下执行。

### 3.1 初始化 / 重置账户

```bash
python -m aifa_quant.cli.main paper-trade reset --cash 1000000
```

- 清空 `paper_positions`、`paper_orders`、`paper_nav` 三张表；
- 把初始现金设为 100 万；
- 持仓归零。

### 3.2 查看账户状态

```bash
python -m aifa_quant.cli.main paper-trade status
```

输出示例：

```text
现金：        2,239.76
持仓数：      5
最新净值日：  2024-12-31
市值：        997,461.00
总资产：      999,700.76

当前持仓：
| 股票      | 股数  | 成本   |
|-----------|-------|--------|
| 600048.SH | 22500 | 8.860  |
| 600522.SH | 13900 | 14.320 |
| ...       | ...   | ...    |
```

### 3.3 执行一次模拟交易

```bash
# 使用缓存的最新交易日作为“今天”
python -m aifa_quant.cli.main paper-trade run

# 指定某个历史交易日
python -m aifa_quant.cli.main paper-trade run --date 20241231
```

常用选项：

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--date YYYYMMDD` | 指定交易日期 | 缓存最新交易日 |
| `--model NAME` | 使用指定模型（默认读 `lgb_stock_selector_latest.pkl`） | `lgb_stock_selector` |
| `--top-k N` | 持仓股票数量 | 5 |
| `--freq N` | 再平衡周期（天） | 5 |
| `--cash N` | 初始资金（仅在 `--reset` 时生效） | 1,000,000 |
| `--dry-run` | 只打印信号和计划交易，不写入数据库 | False |
| `--reset` | 运行前先清空账户 | False |
| `--fundamental/--no-fundamental` | 是否使用 PE/PB/ROE 因子 | True |
| `--macro/--no-macro` | 是否使用 CPI/PMI/M2 因子 | True |
| `--sentiment/--no-sentiment` | 是否使用新闻情绪因子（当前建议关闭） | False |
| `--corr-threshold X` | 特征高相关性剔除阈值 | 0.95 |

### 3.4 推荐工作流

```bash
# 1. 确保有数据 + 模型
python -m aifa_quant.cli.main db-info
ls data_store/models/

# 2. 初始化账户
python -m aifa_quant.cli.main paper-trade reset --cash 1000000

# 3. 先试跑，看信号和计划交易
python -m aifa_quant.cli.main paper-trade run --dry-run

# 4. 正式执行（写入 DuckDB）
python -m aifa_quant.cli.main paper-trade run

# 5. 查看结果
python -m aifa_quant.cli.main paper-trade status
```

---

## 4. dry-run 用法

`--dry-run` 是非常有用的调试选项：它会完整走一遍选股、计算目标持仓的流程，但**不会真正下单，也不会修改数据库**。

```bash
python -m aifa_quant.cli.main paper-trade run --date 20241231 --dry-run
```

输出会显示：

- 交易日期
- 选股信号（排名、股票、分数）
- 计划交易（买卖方向、股数）
- 当前账户净值

这样你可以先确认模型今天想买什么，再决定是否执行。

---

## 5. 状态存在哪里

模拟交易状态全部存在 `data_store/aifa_quant.duckdb` 中，可用任何 DuckDB 客户端查询：

```bash
python -m aifa_quant.cli.main db-info
# 或用 duckdb CLI
 duckdb data_store/aifa_quant.duckdb
```

相关表：

| 表名 | 含义 | 关键字段 |
|------|------|----------|
| `paper_positions` | 当前持仓 | `symbol`, `shares`, `cost_basis` |
| `paper_orders` | 历史订单 | `order_id`, `trade_date`, `symbol`, `side`, `quantity`, `fill_price`, `commission`, `stamp_duty`, `status` |
| `paper_nav` | 每日净值 | `trade_date`, `cash`, `market_value`, `total_value` |

示例查询：

```sql
-- 当前持仓
SELECT * FROM paper_positions WHERE shares != 0;

-- 今日订单
SELECT * FROM paper_orders WHERE trade_date = '2024-12-31';

-- 净值曲线
SELECT * FROM paper_nav ORDER BY trade_date;
```

---

## 6. 内部流程

执行一次 `paper-trade run` 时，系统按以下顺序工作：

1. **确定交易日**：默认取 `daily_quotes` 中最新日期，也可 `--date` 指定。
2. **加载模型**：从 `data_store/models/lgb_stock_selector_latest.pkl` 读取 LightGBM 模型。
3. **构建特征**：读取 DuckDB 缓存数据，生成技术/基本面/宏观因子（默认 `cache_only=True`，不调用 iFind）。
4. **预测打分**：对当日所有股票输出上涨概率 `pred_score`。
5. **生成信号**：`TopKDropoutStrategy` 选出 TopK 股票；已在持仓中的股票若排名未掉出 `dropout_threshold`（默认 `top_k * 2`）则保留。
6. **计算目标持仓**：按总资产等权分配，得到每只股票目标股数（100 股整数倍）。
7. **模拟下单**：调用 `SimulatedBroker`，按当日收盘价成交，并扣减佣金、印花税。
8. **记录净值**：把收盘后的现金、市值、总资产写入 `paper_nav`。

---

## 7. 常见问题

### Q1: 为什么 `paper-trade run` 显示“今日无交易”？

- 当前持仓已经等于目标持仓，不需要调仓。
- 或 `--date` 指定的日期在缓存中没有任何股票数据。

### Q2: 选股信号每次一样吗？

只要模型和数据没变，同一交易日的信号是一致的。

### Q3: 可以每天自动运行吗？

目前 CLI 是手动单次执行。你可以用操作系统定时任务调用：

- **Linux/macOS**: `cron`
- **Windows**: 任务计划程序

示例 cron（每天 15:30 执行）：

```cron
30 15 * * 1-5 cd /path/to/aifa_quant && python -m aifa_quant.cli.main paper-trade run >> logs/paper_trade.log 2>&1
```

> 注意：当前默认读取缓存数据，不会自动拉取最新行情。若需要自动更新日线，需额外先跑 `data-update`。

### Q4: 情绪因子为什么默认关闭？

当前 iFind news MCP 配额紧张，经常返回空数据或限流，因此 `paper-trade run` 默认 `--no-sentiment`。等额度恢复后可手动打开 `--sentiment`。

### Q5: 怎么重新开始？

```bash
python -m aifa_quant.cli.main paper-trade reset --cash 1000000
```

这会清空所有模拟交易记录。

---

## 8. 与回测的区别

| 维度 | 回测（backtest） | 模拟交易（paper-trade） |
|------|------------------|-------------------------|
| 时间范围 | 一段历史区间 | 单个“今天” |
| 目的 | 评估策略历史表现 | 验证模型在最新数据上的实际选股/下单 |
| 执行 | 引擎内部撮合 | `SimulatedBroker` 逐单模拟 |
| 状态 | 内存中，运行结束即消失 | 持久化到 DuckDB |
| 费用 | 已考虑佣金/印花税 | 同样考虑佣金/印花税 |

建议先用 `backtest` 做历史验证，再用 `paper-trade` 滚动跑最新数据，两者结合使用。
