# 数据源与测试数据

> 说明 AifaQuant 项目的数据来源、本地 DuckDB 存储，以及 GitHub Release 上托管的测试/回测用源数据。

---

## 1. 数据来源

- **默认数据源**：[AkShare](https://www.akshare.xyz/)（免费，无需 token）
  - A股日线行情（OHLCV）
  - 指数行情（沪深 300、上证 50 等）
  - 指数成分股列表
- **可选数据源**：
  - [Tushare Pro](https://tushare.pro/)（需 `TUSHARE_TOKEN`）
  - 同花顺 iFind MCP（需 token 与额度）
- **iFind 专用数据类型**：
  - 财务/估值指标（PE、PB、ROE）
  - 宏观指标（CPI、PMI、M2 同比）
  - 新闻情绪数据（当前配额紧张，建议关闭或使用免费情绪源）

---

## 2. 本地存储

所有数据默认存储在本地 DuckDB：

```
./data_store/aifa_quant.duckdb
```

该文件通过 `.gitignore` 排除，不会提交到 GitHub。

---

## 3. GitHub Release 源数据

为方便复现和测试，我们把日线行情导出为压缩 CSV，作为 Release 附件发布：

- **Release**: [v0.3.0-data-csi300](https://github.com/ivyzhi0807/aifa-quant/releases/tag/v0.3.0-data-csi300)
- **文件**: `aifa_quant_daily_quotes_2023_2024.csv.gz`
- **内容**: 沪深 300 成分股 2023-01-03 至 2024-12-31 日线行情

### CSV 列说明

| 列名 | 说明 |
|---|---|
| `symbol` | 股票代码，如 `600519.SH` |
| `trade_date` | 交易日期 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量（股） |
| `amount` | 成交额（元） |

### 导入方式

把 Release 附件放到 `data_store/` 目录后运行：

```bash
python scripts/import_source_data.py data_store/
```

脚本会自动把 `daily_quotes`、`fundamental_data`、`macro_data` 写入 DuckDB。

---

## 4. 重新生成源数据

你也可以使用默认的 AkShare 自行下载：

```bash
# 在项目根目录执行
cd <aifa-quant-project-root>
source .venv/bin/activate          # macOS/Linux
# 或 .venv\Scripts\activate        # Windows

# 下载沪深 300 日线数据
python -m aifa_quant.cli.main data-update \
  --universe 沪深300 \
  --start 20230101 --end 20241231

# 如需基本面/宏观数据（需要 iFind token）
python -m aifa_quant.cli.main data-update \
  --universe 沪深300 \
  --start 20230101 --end 20241231 \
  --fundamental --macro

# 导出压缩 CSV（用于分享或 Release）
python scripts/export_source_data.py
```

导出的文件会保存在 `data_store/` 下。

---

## 5. 模拟交易状态表

除市场数据外，DuckDB 还存储模拟交易状态（不提交到 Git）：

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `paper_positions` | 当前持仓 | `symbol`, `shares`, `cost_basis` |
| `paper_orders` | 历史订单 | `order_id`, `trade_date`, `symbol`, `side`, `quantity`, `fill_price`, `commission`, `stamp_duty`, `status` |
| `paper_nav` | 每日净值 | `trade_date`, `cash`, `market_value`, `total_value` |
