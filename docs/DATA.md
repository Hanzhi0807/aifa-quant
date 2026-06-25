# 数据源与测试数据

> 说明 AifaQuant 项目的数据来源、本地 DuckDB 存储，以及 GitHub Release 上托管的测试/回测用源数据。

---

## 1. 数据来源

- **主要数据源**：同花顺 iFind MCP（Streamable HTTP）
- **数据类型**：
  - 股票日线行情（OHLCV）
  - 财务/估值指标（PE、PB、ROE）
  - 宏观指标（CPI、PMI、M2 同比）
  - 指数行情（沪深 300、上证 50 等）

---

## 2. 本地存储

所有数据默认存储在本地 DuckDB：

```
D:\kimi\data_store\aifa_quant.duckdb
```

该文件通过 `.gitignore` 排除，不会提交到 GitHub。

---

## 3. GitHub Release 源数据

为方便复现和测试，我们把日线行情导出为压缩 CSV，作为 Release 附件发布：

- **Release**: [v0.2.0-data](https://github.com/ivyzhi0807/aifa-quant/releases/tag/v0.2.0-data)
- **文件**: `aifa_quant_daily_quotes_2023_2024.csv.gz`
- **内容**: 上证 50 成分股 2023-01-03 至 2024-12-31 日线行情
- **规模**: 49 只股票，约 21,942 条记录，压缩后约 430KB

### CSV 列说明

| 列名 | 说明 |
|---|---|
| `symbol` | 股票代码，如 `600519.SH` |
| `name` | 证券简称 |
| `trade_date` | 交易日期 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量（股） |
| `amount` | 成交额（元） |
| `created_at` | 数据写入时间 |

### 下载方式

#### 手动下载
访问 Release 页面，点击 `aifa_quant_daily_quotes_2023_2024.csv.gz` 下载。

#### 脚本下载

```bash
cd d:/kimi/data_store
curl -L -o aifa_quant_daily_quotes_2023_2024.csv.gz \
  https://github.com/ivyzhi0807/aifa-quant/releases/download/v0.2.0-data/aifa_quant_daily_quotes_2023_2024.csv.gz
```

#### Python 加载示例

```python
import gzip
import pandas as pd

with gzip.open("data_store/aifa_quant_daily_quotes_2023_2024.csv.gz", "rt", encoding="utf-8") as f:
    df = pd.read_csv(f, parse_dates=["trade_date"])

print(df.head())
```

---

## 4. 重新生成源数据

如果你有 iFind MCP token，也可以自己拉取并导出：

```bash
cd d:/kimi
source .venv/Scripts/activate

# 拉取数据
python -m aifa_quant.cli.main data-update --start 20230101 --end 20241231

# 导出压缩 CSV
python aifa_quant/scripts/export_source_data.py
```

导出的文件会保存在 `data_store/aifa_quant_daily_quotes_2023_2024.csv.gz`。

---

## 5. 注意事项

- `.env` 文件包含 iFind MCP token，**不要提交到 Git**。
- DuckDB 文件较大且可能更新频繁，**不要提交到 Git**。
- Release 附件中的 CSV 仅用于本地回测和复现，**不构成投资建议**。
