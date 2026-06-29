# 数据源与本地存储

> 说明 AifaQuant 的数据来源、本地 DuckDB 存储，以及“首次部署拉取 + 后续增量更新”的数据工作流。

---

## 1. 数据来源

- **默认数据源**：[AkShare](https://www.akshare.xyz/)（免费，无需 token）
  - A 股日线行情（OHLCV，前复权）
  - 指数行情（沪深 300、上证指数、中证 500、中证 1000）
  - 指数成分股列表
- **可选数据源**：
  - [Tushare Pro](https://tushare.pro/)（需 `TUSHARE_TOKEN`）
  - 同花顺 iFind MCP（需 token 与额度）
- **iFind 专用数据类型**（当前配额紧张，建议按需缓存）：
  - 财务/估值指标（PE、PB、ROE）
  - 宏观指标（CPI、PMI、M2 同比）
  - 新闻情绪数据

- **可用时点保护**：基本面合并优先使用公告日 `ann_date`；缺少公告日时使用 `report_date + 90 天` 的保守延迟。宏观数据默认使用指标日期后 30 天才对日线可见，避免回测提前使用未发布数据。

---

## 2. 本地优先的数据工作流

AifaQuant 的所有市场数据和模拟交易状态都保存在本地 DuckDB，**不提交到 GitHub**。部署时执行一次全量拉取，之后每日运行增量刷新脚本即可。

### 2.1 首次部署：全量拉取

```bash
# 在项目根目录、激活 .venv 后执行
python scripts/daily_refresh.py --force --skip-paper-trade
```

该脚本会：

1. 合并沪深 300 / 中证 500 / 中证 1000 的最新成分股，去重后约 1800 只；
2. 写入 `stock_universe` 股票名称表；
3. 从 `20250101` 起拉取日线行情；
4. 同步拉取沪深 300、上证指数、中证 500、中证 1000 指数日线；
5. 尽力缓存基本面数据（PE/PB/ROE，失败不中断）。

> `--force`：忽略周末跳过逻辑，确保首次一定执行。
> `--skip-paper-trade`：此时还没有训练好的模型，先跳过模拟交易。

拉取完成后可用下面命令查看数据概况：

```bash
python -m aifa_quant.cli.main db-info
```

### 2.2 日常：每日增量更新

```bash
python scripts/daily_refresh.py
```

工作日（周一至周五）会自动：

1. 增量更新股票日线；
2. 增量更新指数日线；
3. 为每个策略 profile 执行一次模拟交易（`paper-trade run --all-profiles`）。

周末默认跳过日线更新，只刷新成分股列表和股票名称。

常用选项：

| 选项 | 作用 |
|------|------|
| `--force` | 强制刷新，忽略周末跳过 |
| `--skip-paper-trade` | 只更新数据，不运行模拟交易 |

### 2.3 只更新指数基准

如果只想单独刷新指数：

```bash
python scripts/update_index_data.py
```

默认更新 `000300.SH`、`000001.SH`、`000905.SH`、`000852.SH`。

### 2.4 手动拉取指定范围

```bash
# 沪深 300 成分股（2025 年起）
python -m aifa_quant.cli.main data-update \
  --universe 沪深300 \
  --start 20250101 --end 20261231

# 中证 500 / 1000
python -m aifa_quant.cli.main data-update \
  --universe 中证500 \
  --start 20250101 --end 20261231

# 同时缓存基本面/宏观（需要 iFind token）
python -m aifa_quant.cli.main data-update \
  --universe 沪深300 \
  --start 20250101 --end 20261231 \
  --fundamental --macro
```

---

## 3. 本地存储

所有数据默认存储在本地 DuckDB：

```
./data_store/aifa_quant.duckdb
```

该文件及 `data_store/` 目录已通过 `.gitignore` 排除，**不会提交到 GitHub**。

### 3.1 主要表结构

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `daily_quotes` | 日线行情（股票 + 指数） | `symbol`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `amount` |
| `stock_universe` | 股票代码与名称 | `symbol`, `name`, `updated_at` |
| `fundamental_data` | 基本面指标 | `symbol`, `report_date`, `ann_date`, `pe_lyr`, `pb`, `roe_*` 等 |
| `macro_data` | 宏观指标 | `indicator_name`, `trade_date`, `value` |
| `paper_positions` | 模拟交易当前持仓 | `profile`, `symbol`, `shares`, `cost_basis` |
| `paper_orders` | 模拟交易历史订单 | `profile`, `order_id`, `trade_date`, `symbol`, `side`, `quantity`, `fill_price` |
| `paper_nav` | 模拟交易每日净值 | `profile`, `trade_date`, `cash`, `market_value`, `total_value` |

### 3.2 用 DuckDB CLI 查询

```bash
# 查看最近一个交易日的股票数量
 duckdb data_store/aifa_quant.duckdb -c "SELECT trade_date, COUNT(*) FROM daily_quotes GROUP BY trade_date ORDER BY trade_date DESC LIMIT 5;"

# 查看某只股票的最新日线
 duckdb data_store/aifa_quant.duckdb -c "SELECT * FROM daily_quotes WHERE symbol = '600519.SH' ORDER BY trade_date DESC LIMIT 5;"

# 查看模拟交易净值
 duckdb data_store/aifa_quant.duckdb -c "SELECT * FROM paper_nav WHERE profile = 'balanced' ORDER BY trade_date DESC LIMIT 5;"
```

---

## 4. 数据备份与迁移

由于数据文件较大，**不再通过 GitHub Release 分发**。如需在多台机器间迁移，可直接复制：

```bash
# 备份
mkdir -p backup
cp data_store/aifa_quant.duckdb backup/aifa_quant_$(date +%Y%m%d).duckdb

# 恢复到新环境
cp backup/aifa_quant_YYYYMMDD.duckdb data_store/aifa_quant.duckdb
```

> 旧版 `scripts/export_source_data.py` / `scripts/import_source_data.py` 仍保留，用于本地导出/导入 gzip CSV，但不再与 GitHub Release 配套维护。

---

## 5. 注意事项

- **成分股为当前最新**：AkShare 返回的是当前最新成分股，不是历史 point-in-time 成分股，因此长周期回测存在幸存者偏差。
- **基本面/宏观不按原始日期直接可见**：财务指标按公告日或保守延迟合并，宏观指标按固定发布延迟合并；如后续数据源提供真实发布日期，应优先使用真实发布日期。
- **日线从 2025-01-01 起**：2024 年及以前的数据不再通过默认刷新脚本补充，旧数据如需使用请手动指定 `--start`。
- **DuckDB 并发**：Web 服务每次查询会新建只读连接并正确关闭；但如果 dev server 进程异常未退出，仍可能锁库。Windows 下可用任务管理器结束对应 Node/Python 进程。
