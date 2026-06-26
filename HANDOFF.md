# Handoff Guide - AifaQuant

> 本文档面向后续接力的开发者 / Agent，说明项目结构、当前状态、标准工作流、已知问题和推荐下一步。
> 每次有较大改动后，请同步更新本文档，确保下一位接手者能快速上手。

## 1. 项目一句话

AifaQuant 是一个基于 **Python + DuckDB + LightGBM** 的 A股 AI 量化研究与回测框架，以 **同花顺 iFind MCP** 为主要数据源，支持数据获取、因子工程、模型训练、滚动回测和结果可视化的完整闭环。

## 2. 当前状态（v0.3.0）

- ✅ 代码已重构为 `aifa_quant/` 命名空间包
- ✅ iFind MCP 数据接入：股票日线、财务估值、宏观经济、指数行情
- ✅ DuckDB 本地存储 + 增量更新（并发下载 + 5 req/s 限速）
- ✅ 技术面因子、基本面因子（PE / PB / ROE，已持久化到 DuckDB）、宏观因子（CPI / PMI / M2，已持久化到 DuckDB）
- ✅ 情绪因子模块已接入，但 **iFind news MCP 目前无可用数据**（限流/配额），实际未生效
- ✅ LightGBM 二分类选股模型 + 正则化
- ✅ 滚动窗口训练 / out-of-sample 预测
- ✅ 特征高相关性剔除（`--corr-threshold`）
- ✅ TopK-Dropout 策略 + A股规则回测引擎（T+1、涨跌停、100 股手、手续费、印花税）
- ✅ 沪深 300 基准对比 + 超额收益 / 超额夏普
- ✅ CLI 入口
- ✅ GitHub Actions CI（lint + test）—— 目前账号被禁用 Actions，需仓库设置开启
- ✅ 前后端网站（React + Hono + tRPC + Drizzle + MySQL，位于 `web/`）
- ✅ 数据源通过 GitHub Release 分发：`v0.3.0-data-csi300`
- ⚠️ 当前为研究与框架验证阶段，回测结果不代表实盘表现

## 3. 目录速查

```
aifa_quant/
├── aifa_quant/               # Python 命名空间包
│   ├── config/               # Pydantic Settings，读取 .env
│   ├── data/
│   │   ├── adapters/         # iFind MCP 适配器（stock / index / macro / news）
│   │   ├── pipeline/         # ETL / 增量更新
│   │   └── storage/          # DuckDB 封装
│   ├── features/             # 因子工程（technical / fundamental / macro / sentiment / selection）
│   ├── models/               # LightGBM、模型注册表、滚动训练器
│   ├── strategy/             # TopK-Dropout 策略
│   ├── backtest/             # 事件驱动回测引擎 + 绩效指标
│   ├── execution/            # 模拟/实盘执行接口（待完善）
│   └── cli/                  # 命令行入口
├── web/                      # 前后端网站
├── scripts/                  # 独立脚本：取成分股、导出/导入数据、SHAP、参数搜索、建样例 DB
├── tests/                    # 单元测试
├── data_store/               # DuckDB、成分股列表、导出的报告/图表（不提交 Git）
├── docs/                     # 文档、指标说明、网站任务书、集成路线图
└── notebooks/                # 研究 notebook
```

## 4. 环境准备

```bash
cd d:/kimi/aifa_quant

# 1. 确认 .env 已配置（仓库根目录，不提交 Git）
cat .env
# 必须包含：
#   IFIND_STOCK_MCP_URL / IFIND_STOCK_MCP_TOKEN
#   IFIND_INDEX_MCP_URL / IFIND_INDEX_MCP_TOKEN
#   IFIND_NEWS_MCP_URL  / IFIND_NEWS_MCP_TOKEN（news 目前不可用，但需占位）
#   DUCKDB_PATH=./data_store/aifa_quant.duckdb

# 2. 安装依赖
pip install -r requirements.txt

# 3. 代码检查
ruff check aifa_quant scripts tests
pytest tests/ -v
```

**注意**：所有 `python -m aifa_quant.cli.main ...` 命令必须在项目根目录 `d:/kimi/aifa_quant` 下执行，否则模块找不到。

## 5. 标准工作流

### 5.1 测试数据连接

```bash
python -m aifa_quant.cli.main test-connection
```

### 5.2 获取沪深 300 成分股

```bash
python scripts/fetch_csi300_symbols.py
# 输出：data_store/csi300_symbols.txt
```

> 当前新浪页面去重后约 288 只唯一成分股，非完整 300 只。

### 5.3 下载日线数据

```bash
# 全量沪深 300（286 只，2023-2024，约 600 次请求，10-30 分钟）
python -m aifa_quant.cli.main data-update \
  --symbol-file data_store/csi300_symbols.txt \
  --start 20230101 --end 20241231 --workers 5

# 同时缓存基本面和宏观数据（后续回测不再调用 iFind）
python -m aifa_quant.cli.main data-update \
  --symbol-file data_store/csi300_symbols.txt \
  --start 20230101 --end 20241231 \
  --workers 5 --fundamental --macro

# 只测试前 5 只
python -m aifa_quant.cli.main data-update \
  --symbol-file data_store/csi300_symbols.txt --sample 5 \
  --start 20240101 --end 20241231
```

下载过程会逐只股票写入 DuckDB，失败自动跳过。日志可重定向到文件查看进度。

### 5.4 训练模型

```bash
python -m aifa_quant.cli.main train \
  --start 20230101 --end 20231231 --horizon 5 \
  --corr-threshold 0.95
```

模型会保存到 `data_store/models/`。

### 5.5 滚动回测

```bash
python -m aifa_quant.cli.main backtest \
  --start 20230101 --end 20241231 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 \
  --corr-threshold 0.95

# 不带情绪因子（当前推荐，因为 news MCP 无数据）
python -m aifa_quant.cli.main backtest \
  --start 20230101 --end 20241231 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 --no-sentiment
```

回测结果输出在 `data_store/reports/`：
- `equity_YYYYMMDD_YYYYMMDD.csv`：净值曲线
- `equity_YYYYMMDD_YYYYMMDD_rolling.png`：净值图

### 5.6 数据分发（Release）

```bash
# 导出当前 DuckDB 日线数据为 gzip CSV
python scripts/export_source_data.py
# 输出：data_store/aifa_quant_daily_quotes_2023_2024.csv.gz

# 新环境下载 Release 后导入
python scripts/import_source_data.py path/to/aifa_quant_daily_quotes_2023_2024.csv.gz
```

## 6. 已有数据与回测结果

### 6.1 数据

- **沪深 300 日线 2023-2024**：286 只成分股，129,231 条日线
- **缺失**：`001280.SZ`、`600930.SH` 无日线数据
- **Release**：https://github.com/ivyzhi0807/aifa-quant/releases/tag/v0.3.0-data-csi300

### 6.2 回测结果

沪深 300 成分股，全因子，滚动训练，TopK=5，调仓频率 5 日，2023-01-01 至 2024-12-31：

| 指标 | 数值 |
|------|------|
| 总收益率 | 336.37% |
| 年化收益率 | 115.35% |
| 年化波动率 | 49.21% |
| 夏普比率 | 2.344 |
| 最大回撤 | -27.40% |
| 日胜率 | 55.69% |
| 沪深 300 基准收益 | 1.21% |
| 超额收益 | 335.16% |
| 超额夏普 | 1.940 |

> ⚠️ 高收益主要来自小样本 + 参数选择，存在过拟合风险，不代表实盘表现。

## 7. 重要脚本说明

| 脚本 | 用途 |
|------|------|
| `scripts/fetch_csi300_symbols.py` | 从新浪财经抓取沪深 300 成分股 |
| `scripts/export_source_data.py` | 导出 DuckDB 日线到 gzip CSV，用于 Release |
| `scripts/import_source_data.py` | 从 Release CSV 导入到 DuckDB |
| `scripts/export_backtest_to_web.py` | 把回测结果同步到 web 前端 |
| `scripts/create_sample_db.py` | 抽取部分股票生成临时 DuckDB，方便做对照实验 |
| `scripts/shap_analysis.py` | 对训练好的模型做 SHAP 可解释性分析 |
| `scripts/parameter_search.py` | 网格搜索 `top_k` 和 `rebalance_freq` |

## 8. 前端网站

```bash
cd web
npm install
cp .env.example .env
# 编辑 .env 填入 DATABASE_URL
npm run db:push
npm run dev
```

线上预览：https://h6lwpd6rnrixk.ok.kimi.link

本地开发预览：`http://localhost:3000`

构建检查：

```bash
npm run check
npm run test
npm run build
```

> 线上预览链接已移除，目前只支持本地运行或自行部署。

## 9. 已知问题与坑

| 问题 | 说明 | 建议 |
|------|------|------|
| GitHub Actions 被禁用 | `gh workflow run` 报 `Actions has been disabled for this user` | 在 GitHub 账号/仓库设置里启用 Actions |
| iFind MCP 配额耗尽 | 股票/新闻 MCP 均可能报限流或无法返回数据 | 先用 Release 导入日线；基本面/宏观可通过 `data-update --fundamental --macro` 一次性缓存，之后回测不再调用 iFind |
| iFind news MCP 无数据 | 返回 `用户使用过于频繁`，情绪因子当前为空 | 暂时关闭 `--sentiment`；等配额恢复后重试 |
| 沪深 300 成分股不完整 | 新浪财经去重后约 288 只 | 可接入 iFind 指数成分股工具或上交所/深交所官方列表做补充 |
| 幸存者偏差 | 使用当前成分股回测历史区间 | 获取历史调仓记录，按真实成分股选股 |
| 过拟合风险 | 高收益伴随高波动 | 增加样本量、做样本外验证、降低模型复杂度 |
| 前收盘价维护 | 涨跌停判断目前用成本价近似 | 维护 `prev_close` 字段 |

## 10. 给下一位 Agent 的建议

1. **先跑测试再改代码**：`pytest tests/ -q` 应全部通过。
2. **不要提交 `.env` 和 DuckDB**：已在 `.gitignore` 中排除。
3. **做对照实验时使用临时 DB**：
   ```bash
   python scripts/create_sample_db.py
   DUCKDB_PATH=./data_store/aifa_quant_sample.duckdb python -m aifa_quant.cli.main backtest ...
   ```
4. **情绪因子目前不要默认开启**：news MCP 无数据，打开 `--sentiment` 不会报错但也不会提升效果。
5. **扩大股票池前检查配额**：iFind 5000 次/月，沪深 300 两年日线约 600 次请求。
6. **更新 HANDOFF.md**：如果你改了架构、工作流或重要状态，请同步本文档。

## 11. 代码规范

- Lint：`ruff check aifa_quant scripts tests`
- Format：`ruff format aifa_quant scripts tests`
- 测试：`pytest tests/ -v`
- Python 版本：3.10 / 3.11 / 3.12 / 3.13

## 12. 参考资料

- 仓库：https://github.com/ivyzhi0807/aifa-quant
- 指标说明：`docs/METRICS.md`
- 网站任务书：`docs/WEBSITE_TASK.md`
- 集成路线图：`docs/INTEGRATION_ROADMAP.md`
- 测试数据源 Release：https://github.com/ivyzhi0807/aifa-quant/releases/tag/v0.4.0-data-full
- 创建者：ivyzhi0807 / jiangjas@gmail.com
