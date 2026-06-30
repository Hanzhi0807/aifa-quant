# Handoff Guide - AifaQuant

> 本文档面向后续接力的开发者 / Agent，说明项目结构、当前状态、标准工作流、已知问题和推荐下一步。
> 每次有较大改动后，请同步更新本文档，确保下一位接手者能快速上手。

## 1. 项目一句话

AifaQuant 是一个基于 **Python + DuckDB + LightGBM** 的 A股 AI 量化研究与回测框架，默认以 **AkShare** 作为免费数据源，可选 **Tushare / iFind MCP**，支持数据获取、因子工程、模型训练、滚动回测、模拟交易和 Web 可视化的完整闭环。

当前版本：**v0.6.0**。

---

## 2. 当前状态（v0.6.0）

### 2.1 核心能力

- ✅ 代码已重构为 `aifa_quant/` 命名空间包
- ✅ iFind MCP 数据接入：股票日线、财务估值、宏观经济、指数行情
- ✅ AkShare 免费数据源：日线行情、指数行情、成分股列表（默认数据源，无需 token）
- ✅ Tushare Pro 数据源适配器（需 `TUSHARE_TOKEN`）
- ✅ DuckDB 本地存储 + 增量更新
- ✅ 股票池扩展到 **沪深 300 + 中证 500 + 中证 1000**，合计约 **1800 只** A股
- ✅ 日线数据默认从 **2025-01-01** 起增量更新，2024 及以前不再默认补充
- ✅ 技术面因子、基本面因子（PE / PB / ROE）、宏观因子（CPI / PMI / M2）、Alpha101/191 风格因子（Alpha rank 已按日期截面化）
- ✅ 情绪因子模块已接入，但 **iFind news MCP 目前无可用数据**（限流/配额），实际未生效；可使用免费情绪源
- ✅ LightGBM 二分类选股模型 + LambdaRank 排序 + Ensemble 集成
- ✅ 滚动窗口训练 / out-of-sample 预测
- ✅ 滚动训练窗口内特征高相关性剔除（`--corr-threshold`，避免全样本筛选泄漏）
- ✅ SHAP 模型可解释性分析
- ✅ 每周 AI 选股报告

### 2.2 策略与风控

- ✅ 5 种投资者偏好 **profile**：`aggressive` / `balanced` / `conservative` / `growth` / `value`
- ✅ `apply_profile_score()` 按 `factor_weights` 加权特征列前缀，使不同 profile 选股不同
- ✅ TopK-Dropout 策略（`dropout_threshold = top_k × 2`，持仓数可能暂时大于 `top_k`）
- ✅ A股规则回测引擎：T 日收盘信号、T+1 开盘成交、涨跌停、100 股整数手、佣金、印花税
- ✅ ATR 三层风控：止损 / 止盈 / 单日暴跌 / 利润回撤
- ✅ 仓位 sizing：`target_risk_pct / (N × ATR)`，默认 `N = 2`
- ✅ 沪深 300 / 上证指数基准对比 + 超额收益 / 超额夏普

### 2.3 模拟交易与自动化

- ✅ 模拟交易（Paper Trading）：按 `profile` 隔离持仓、DuckDB 持久化
- ✅ CLI `paper-trade reset / run / status`，支持 `--profile` 与 `--all-profiles`
- ✅ 每日自动刷新脚本 `scripts/daily_refresh.py`：增量更新日线 + 指数 + 自动运行所有 profile 模拟交易
- ✅ 指数数据更新脚本 `scripts/update_index_data.py`：同步刷新 `000300.SH` / `000001.SH` / `000905.SH` / `000852.SH`

### 2.4 Web 仪表盘

- ✅ React + Hono + tRPC + DuckDB，位于 `web/`
- ✅ 首页：profile 选择器、独立持仓、历史表现（叠加沪深 300 / 上证指数基准）、FAQ
- ✅ 回测页、模型页、数据页
- ⚠️ 不再依赖 MySQL/Drizzle，直接读取本地 DuckDB

### 2.5 工程与部署

- ✅ `.gitignore` 已排除 `data_store/`、`*.duckdb`、模型等，**不再通过 GitHub Release 分发数据**
- ✅ CLI 统一入口：`python -m aifa_quant.cli.main ...`
- ✅ Docker 配置已提供，但本机构建受网络限制未验证
- ⚠️ GitHub Actions CI（lint + test）—— 目前账号被禁用 Actions，需仓库设置开启
- ⚠️ 当前为研究与框架验证阶段，回测结果不代表实盘表现

---

## 3. 目录速查

```
aifa_quant/
├── aifa_quant/               # Python 命名空间包
│   ├── config/               # Pydantic Settings，读取 .env
│   ├── core/                 # 抽象接口
│   ├── data/
│   │   ├── adapters/         # iFind MCP / AkShare / Tushare 适配器
│   │   ├── constants.py      # 指数代码常量，防止指数被选股
│   │   ├── pipeline/         # ETL / 增量更新
│   │   └── storage/          # DuckDB 封装
│   ├── features/             # 因子工程（technical / fundamental / macro / sentiment / selection / alpha）
│   ├── models/               # LightGBM、模型注册表、滚动训练器、Ensemble、XGBoost
│   ├── risk/                 # ATR 止损/止盈/回撤/暴跌
│   ├── strategy/             # TopK-Dropout 策略、策略模板、profiles
│   ├── analysis/             # 因子分析 / SHAP
│   ├── research/             # 每周选股报告
│   ├── backtest/             # 事件驱动回测引擎 + 绩效指标
│   ├── execution/            # 模拟/实盘执行接口
│   ├── paper_trading/        # 模拟交易引擎与状态持久化
│   └── cli/                  # 命令行入口
├── web/                      # 前后端网站（React + Hono + tRPC + DuckDB）
├── scripts/                  # 独立脚本：取成分股、导出/导入、SHAP、参数搜索、每日刷新、指数更新
├── tests/                    # 单元测试
├── data_store/               # DuckDB、成分股列表、导出的报告/图表（不提交 Git）
├── docs/                     # 文档、指标说明、网站任务书、集成路线图
└── notebooks/                # 研究 notebook
```

---

## 4. 环境准备

```bash
cd <aifa-quant-project-root>

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
pytest tests/ -q
```

**注意**：所有 `python -m aifa_quant.cli.main ...` 命令必须在项目根目录下执行，否则模块找不到。

---

## 5. 本地数据工作流（核心）

### 5.1 首次部署：全量拉取

```bash
python scripts/daily_refresh.py --force --skip-paper-trade
```

该脚本会：

1. 合并沪深 300 / 中证 500 / 中证 1000 成分股，去重后约 1800 只；
2. 写入/更新 `stock_universe` 股票名称表；
3. 从 `20250101` 起拉取日线行情；
4. 同步拉取 4 个指数日线；
5. 尽力缓存基本面数据（失败不中断；合并时优先公告日，缺失时按报告期 +90 天可用）；
6. `--skip-paper-trade` 跳过模拟交易（此时通常还没有训练好的模型）。

### 5.2 每日增量刷新

```bash
python scripts/daily_refresh.py
```

- 工作日自动增量更新股票日线和指数日线；
- 周末默认跳过日线更新，只刷新成分股列表和股票名称；
- 最后自动执行 `paper-trade run --all-profiles`。

常用选项：

- `--force`：忽略周末跳过逻辑，强制刷新；
- `--skip-paper-trade`：只更新数据，不运行模拟交易。

### 5.3 单独更新指数

```bash
python scripts/update_index_data.py
```

### 5.4 数据备份与迁移

数据文件不提交 Git。迁移环境时直接复制 DuckDB：

```bash
# 备份
cp data_store/aifa_quant.duckdb backup/aifa_quant_$(date +%Y%m%d).duckdb

# 恢复
cp backup/aifa_quant_YYYYMMDD.duckdb data_store/aifa_quant.duckdb
```

---

### 5.5 Point-in-time 保护

- 基本面数据合并优先使用 `ann_date`；如果数据源没有公告日，则按 `report_date + 90 天` 才允许进入日线特征。
- 宏观数据按指标日期后 30 天才允许进入日线特征；若后续接入真实发布日期，应替换固定延迟。
- 滚动回测的高相关性筛选在每个训练窗口内部执行，不能在 `FeatureBuilder` 全样本阶段提前筛选。

---

## 6. 标准工作流

### 6.1 测试数据连接

```bash
python -m aifa_quant.cli.main test-connection
```

### 6.2 训练模型

```bash
python -m aifa_quant.cli.main train \
  --start 20250101 --end 20260626 \
  --corr-threshold 0.95 --no-sentiment --cache-only
```

模型会保存到 `data_store/models/`。

> 股票池已扩展，建议用 2025 年以来的新 universe 重新训练。

### 6.3 滚动回测

```bash
python -m aifa_quant.cli.main backtest \
  --start 20250101 --end 20260626 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 \
  --corr-threshold 0.95 --no-sentiment --cache-only
```

### 6.4 模拟交易（Paper Trading）

```bash
# 初始化所有 profile 账户
python -m aifa_quant.cli.main paper-trade reset --cash 1000000 --all-profiles

# 单个 profile 试跑
python -m aifa_quant.cli.main paper-trade run --profile balanced --dry-run

# 正式执行所有 profile
python -m aifa_quant.cli.main paper-trade run --all-profiles

# 查看状态
python -m aifa_quant.cli.main paper-trade status
```

状态存储在 DuckDB 的三张表中，按 `profile` 隔离：

- `paper_positions` - 当前持仓
- `paper_orders` - 订单明细
- `paper_nav` - 每日净值

### 6.5 报告与可解释性

```bash
# 每周选股报告
python -m aifa_quant.cli.main weekly-report --cache-only

# SHAP 分析
python -m aifa_quant.cli.main explain \
  --start 20250101 --end 20260626 \
  --output data_store/reports/shap --cache-only
```

---

## 7. Profile 与风控细节

### 7.1 Profile 差异化

不同 profile 不能仅靠 `top_k` 区分。最终分数由 `apply_profile_score()` 计算：

```
final_score = 0.7 × model_score + 0.3 × profile_factor_score
```

其中 `profile_factor_score` 按 `factor_weights` 加权匹配的特征列前缀。

例如 `value` profile 会加权 `pe` / `pb` / `ps` / `dividend` / `roe` 等低估值因子；`aggressive` profile 会加权 `momentum` / `return` / `alpha` 等动量因子。

### 7.2 风控与仓位

- 每只股票仓位 = `target_risk_pct / (N × ATR)`，`N` 默认 2；
- ATR 需要至少 15 条 K 线，模拟交易已单独加载 60 天 OHLCV；
- 三层 ATR 信号：止损、止盈、单日暴跌、利润回撤；
- 大盘震荡时会跳过新买入（`market_choppy`）。

---

## 8. Web 首页说明

`web/` 启动后访问 `http://localhost:3000`：

- **策略选择器**：切换 5 个 profile；
- **独立持仓**：每个 profile 的当前持仓、成本、最新市值、当日收益；
- **历史表现**：组合净值面积图，叠加沪深 300、上证指数归一化折线；
- **FAQ**：解释 profile 含义、数据来源、风险提示。

Web 后端通过 `web/api/queries/duckdb.ts` 读取 DuckDB，每次查询新建只读连接并在 `finally` 中关闭。

---

## 9. 已有数据与回测结果

### 9.1 数据

- **选股池**：沪深 300 + 中证 500 + 中证 1000，去重后约 **1800 只**
- **日线范围**：2025-01-01 至 2026-06-26（随每日刷新自动扩展）
- **指数**：`000300.SH` / `000001.SH` / `000905.SH` / `000852.SH`
- **存储**：`data_store/aifa_quant.duckdb`

> 数据文件较大，**不再通过 GitHub Release 分发**。新环境首次运行 `scripts/daily_refresh.py --force --skip-paper-trade` 即可。

### 9.2 回测结果

股票池与数据范围已变更，**旧版沪深 300 2023–2024 回测结果不再代表当前策略表现**。建议用新 universe 重新训练并回测：

```bash
python -m aifa_quant.cli.main backtest \
  --start 20250101 --end 20260626 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 --no-sentiment --cache-only
```

旧结果如需查看，可在 `CHANGELOG.md` 历史版本中找到。

---

## 10. 重要脚本说明

| 脚本 | 用途 |
|------|------|
| `scripts/daily_refresh.py` | 每日自动刷新：成分股、日线、指数、模拟交易 |
| `scripts/update_index_data.py` | 从 AkShare 拉取指数日线并写入 DuckDB |
| `scripts/fetch_csi300_symbols.py` | 从新浪财经抓取沪深 300 成分股 |
| `scripts/export_source_data.py` | 导出 DuckDB 日线到 gzip CSV（本地备份） |
| `scripts/import_source_data.py` | 从 gzip CSV 导入到 DuckDB（本地备份） |
| `scripts/export_backtest_to_web.py` | 把回测结果同步到 web 前端 |
| `scripts/create_sample_db.py` | 抽取部分股票生成临时 DuckDB，方便做对照实验 |
| `scripts/shap_analysis.py` | 对训练好的模型做 SHAP 可解释性分析 |
| `scripts/parameter_search.py` | 网格搜索 `top_k` 和 `rebalance_freq` |
| `scripts/update_stock_names.py` | 从 AkShare 拉取 A股名称并写入 `stock_universe` |

---

## 11. 前端网站

```bash
cd web
npm install
npm run dev
```

本地开发预览：`http://localhost:3000`

构建检查：

```bash
npm run check
npm run test
npm run build
```

> 网站直接读取本地 DuckDB，不再依赖 MySQL/Drizzle。确保项目根目录已有 `data_store/aifa_quant.duckdb`。

---

## 12. 已知问题与坑

| 问题 | 说明 | 建议 |
|------|------|------|
| GitHub Actions 被禁用 | `gh workflow run` 报 `Actions has been disabled for this user` | 在 GitHub 账号/仓库设置里启用 Actions |
| iFind MCP 配额耗尽 | 股票/新闻 MCP 均可能报限流或无法返回数据 | 日线/指数/成分股默认走 AkShare；基本面已改用 `scripts/update_fundamentals.py`（AkShare）补齐；宏观可走 `data-update --macro` |
| iFind news MCP 无数据 | 返回 `用户使用过于频繁`，情绪因子当前为空 | 暂时关闭 `--sentiment`；使用 `--sentiment-source free` 获取免费情绪数据 |
| DuckDB 锁库 | Web 已优化关闭逻辑，但孤儿 Node/Python 进程仍可能锁库 | 第三轮已加 `_WRITE_LOCK`（进程内）+ 只读连接支持；跨进程仍需手动结束 PID |
| Docker 构建失败 | 本机无法拉取 `python:3.12-slim` / `node:22-slim` | 配置 Docker 镜像源或离线导入基础镜像 |
| 成分股非历史真实 | AkShare 返回当前最新成分股 | 长周期回测存在幸存者偏差，谨慎解读 |
| 模型需重新训练 | 现有模型基于沪深 300 训练，扩大到中证 500/1000 后性能未知 | 用新 universe 和 2025 年以来的数据重新训练 |
| TopK-Dropout 持仓数波动 | `dropout_threshold = top_k × 2`，缓冲期内持仓可能暂时大于 `top_k` | 这是策略设计的降仓缓冲，非 bug |
| PE/PB 日频历史缺失 | `stock_universe.pe_ttm/pb_lyr` 是当前快照，非 point-in-time 历史 | 回测用 `pe_snap/pb_snap` 有轻微前视；完整历史估值需接入 Tushare daily_basic |
| 东财 spot 接口偶发不可用 | `stock_zh_a_spot_em` 偶尔 `RemoteDisconnected` | `update_market_caps.py` 已加 4 次重试；失败时稍后重跑即可 |
| 前收盘价维护 | 回测引擎用成本价近似；模拟交易已加载前收盘价 | 继续完善数据源，确保 `prev_close` 准确 |

---

## 13. 给下一位 Agent 的建议

1. **先跑测试再改代码**：`pytest tests/ -q` 应全部通过。
2. **不要提交 `.env`、DuckDB、模型**：已在 `.gitignore` 中排除。
3. **做对照实验时使用临时 DB**：
   ```bash
   python scripts/create_sample_db.py
   DUCKDB_PATH=./data_store/aifa_quant_sample.duckdb python -m aifa_quant.cli.main backtest ...
   ```
4. **情绪因子目前不要默认开启**：news MCP 无数据，打开 `--sentiment` 不会报错但也不会提升效果；优先用 `--sentiment-source free`。
5. **扩大股票池后检查数据**：当前约 1800 只，日线从 2025 年起，确保硬盘和下载时间可接受。
6. **模型与股票池匹配**：改 universe 后应重新训练模型，否则选股分数可能偏离。
7. **更新 HANDOFF.md / README.md / AGENTS.md**：如果你改了架构、工作流或重要状态，请同步这些文档。
8. **改 profile 或因子权重后观察持仓差异**：不要只看 `top_k`，要确认 `apply_profile_score()` 加权后不同 profile 选出的股票确实不同。

---

## 14. 近期关键改动清单

- 股票池从沪深 300 扩展到沪深 300 + 中证 500 + 中证 1000（约 1800 只）。
- 日线默认从 2025-01-01 起，旧数据不再通过默认脚本补充。
- 新增 5 个投资者偏好 profile，通过 `factor_weights` 实现持仓差异化。
- 新增 ATR 三层风控和 `target_risk / (N × ATR)` 仓位 sizing。
- 新增 `scripts/daily_refresh.py` 与 `scripts/update_index_data.py`。
- Web 首页改造：profile 选择器、独立持仓、基准叠加权益曲线、FAQ。
- Web 后端改为直接读取 DuckDB，移除 MySQL/Drizzle 依赖。
- 数据文件改为本地存储，不再通过 GitHub Release 分发。
- 修复 Windows 控制台 `¥` 符号 UnicodeEncodeError。
- 修复 DuckDB 长期锁库问题（Web 查询后正确关闭连接）。

---

## 15. 代码规范

- Lint：`ruff check aifa_quant scripts tests`
- Format：`ruff format aifa_quant scripts tests`
- 测试：`pytest tests/ -q`
- Python 版本：3.10 / 3.11 / 3.12 / 3.13

---

## 16. 参考资料

- 仓库：https://github.com/ivyzhi0807/aifa-quant
- 快速开始：`README.md`
- 指标说明：`docs/METRICS.md`
- 网站任务书：`docs/WEBSITE_TASK.md`
- 集成路线图：`docs/INTEGRATION_ROADMAP.md`
- 创建者：ivyzhi0807 / jiangjas@gmail.com
