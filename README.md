# AifaQuant-爱发量化 - A股 AI 量化研究与回测框架

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
![License](https://img.shields.io/badge/license-MIT-green)
[![Release](https://img.shields.io/github/v/release/ivyzhi0807/aifa-quant)](https://github.com/ivyzhi0807/aifa-quant/releases)

> **⚠️ 免责声明**
>
> AifaQuant 是一个**量化研究与学习框架**，所有代码、示例、回测结果和模拟交易结果**仅供技术研究参考，不构成任何投资建议**。
> 作者不对因使用本项目而产生的任何投资亏损、交易风险或法律责任负责。在将任何策略用于实盘之前，请自行充分回测、风险评估，并遵守所在国家/地区的法律法规。

> **📜 开源与使用声明**
>
> 本项目代码按 [MIT 许可证](LICENSE) 开源，允许自由使用、修改和分发，但需保留版权声明。
> 作者将本项目定位为**个人学习与非商业研究用途**，不推荐直接将其作为商业投顾、资管产品或对外付费服务的一部分。
> 如需用于商业场景，请自行评估合规风险并承担相应责任。

---

AifaQuant 是一个本地优先的 **A股 AI 量化研究与回测框架**，覆盖数据获取、因子工程、模型训练、策略回测到模拟交易的完整闭环。

- **数据源**：默认 [AkShare](https://www.akshare.xyz/)（免费，无需 token）；可选 [Tushare](https://tushare.pro/)（需 token）；基本面/宏观/情绪仍走同花顺 iFind MCP。
- **存储**：本地 DuckDB，日线、基本面、宏观、情绪数据一次缓存，离线复用。
- **特征工程**：技术指标 + Alpha101/191 风格因子 + 基本面（PE/PB/ROE）+ 宏观（CPI/PMI/M2）+ 情绪（iFind / 东方财富免费）+ 高相关性剔除。
- **模型**：LightGBM 二分类 / LambdaRank 排序 / Ensemble 模型集成。
- **可解释性**：SHAP 特征重要性分析。
- **策略**：TopK-Dropout 轮动，支持策略模板（default / aggressive / conservative / momentum）。
- **回测**：自定义 A股规则引擎（T+1、涨跌停、100 股整数手、佣金、印花税）。
- **模拟交易**：基于训练好的模型每日生成信号，用 `SimulatedBroker` 虚拟成交，状态持久化到 DuckDB。
- **自动化**：每周 AI 选股报告自动生成。

---

## 目录

- [复制给你的 Agent（零基础上手）](#复制给你的-agent零基础上手)
- [快速开始](#快速开始)
- [完整工作流](#完整工作流)
- [CLI 命令速查](#cli-命令速查)
- [项目结构](#项目结构)
- [最新回测结果](#最新回测结果)
- [模拟交易](#模拟交易)
- [前端网站（可选）](#前端网站可选)
- [Alpha101/191 因子库](#alpha101191-因子库)
- [LambdaRank 排序模型与 Ensemble](#lambdarank-排序模型与-ensemble)
- [SHAP 可解释性](#shap-可解释性)
- [策略模板](#策略模板)
- [每周 AI 选股报告](#每周-ai-选股报告)
- [MkDocs 文档站](#mkdocs-文档站)
- [Docker 一键启动](#docker-一键启动)
- [文档索引](#文档索引)
- [注意事项](#注意事项)

---

## 复制给你的 Agent（零基础上手）

如果你不熟悉命令行或第一次接触本项目，直接把下面这段话复制给你的 AI Agent，它会按顺序完成环境配置并跑通第一个完整工作流：

> 请帮我完成 AifaQuant 项目的初始配置并跑通完整工作流：
> 1. 进入项目根目录（例如 `D:\workspace\AI QUANT` 或你 clone 到的目录）。
> 2. 确认已安装 Python 3.10、3.11 或 3.12。
> 3. 创建虚拟环境 `.venv`：Windows 运行 `python -m venv .venv` 并激活 `.venv\Scripts\activate`；macOS/Linux 运行 `python3 -m venv .venv` 并激活 `source .venv/bin/activate`。
> 4. 安装依赖：`pip install -r requirements.txt`。
> 5. 复制 `.env.example` 为 `.env`。如果只想使用免费数据，iFind token 可以暂时留空；需要基本面/宏观/情绪数据时再填入你的 iFind MCP token。
> 6. 运行测试确认环境正常：`pytest tests/ -q`。
> 7. 下载沪深 300 日线数据：`python -m aifa_quant.cli.main data-update --universe 沪深300 --start 20230101 --end 20241231`。
> 8. 查看数据概况：`python -m aifa_quant.cli.main db-info`。
> 9. 训练选股模型：`python -m aifa_quant.cli.main train --start 20230101 --end 20241231 --no-sentiment --cache-only`。
> 10. 滚动回测：`python -m aifa_quant.cli.main backtest --start 20240101 --end 20241231 --rolling --benchmark 000300.SH --top-k 5 --freq 5 --no-sentiment --cache-only`。
> 11. 模拟交易：`python -m aifa_quant.cli.main paper-trade reset --cash 1000000`，然后 `python -m aifa_quant.cli.main paper-trade run --dry-run`，再 `python -m aifa_quant.cli.main paper-trade run`，最后 `python -m aifa_quant.cli.main paper-trade status`。
> 每完成一步请向我汇报结果；如果遇到报错，先尝试修复并继续。

---

## 快速开始

### 1. 环境准备

```bash
# 进入项目根目录（换成你本地的实际路径）
cd <aifa-quant-project-root>

# 创建并激活虚拟环境（Windows 示例）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制并编辑 .env（填入 iFind MCP token，可选）
cp .env.example .env
```

> `.env` 已加入 `.gitignore`，**不要提交到 Git**。

### 2. 获取数据（二选一）

**推荐：直接用 AkShare 下载（默认，免费）**

```bash
python -m aifa_quant.cli.main data-update \
  --universe 沪深300 \
  --start 20230101 --end 20241231

# 同时缓存基本面/宏观（需要 iFind token）
python -m aifa_quant.cli.main data-update \
  --universe 沪深300 \
  --start 20230101 --end 20241231 \
  --fundamental --macro
```

**或从 Release 数据包导入（如有）**

如果 GitHub Release 提供了 `aifa_quant_daily_quotes_2023_2024.csv.gz` 等数据包，可放到 `data_store/` 后导入：

```bash
python scripts/import_source_data.py data_store/
```

**使用 Tushare Pro 下载（需 token）**

```bash
# .env 中配置 TUSHARE_TOKEN=...
python -m aifa_quant.cli.main data-update \
  --source tushare \
  --universe 000300.SH \
  --start 20230101 --end 20241231
```

**或强制走 iFind MCP 下载（需要 token 和额度）**

```bash
python -m aifa_quant.cli.main data-update \
  --source ifind \
  --symbol-file data_store/csi300_symbols.txt \
  --start 20230101 --end 20241231 \
  --workers 5 --fundamental --macro \
  --yes  # 跳过 iFind 使用确认
```

> 任何会调用 iFind MCP 的操作都会先提示确认，加 `--yes` 可跳过。

### 3. 验证数据

```bash
python -m aifa_quant.cli.main db-info
```

---

## 完整工作流

```bash
# 1. 训练选股模型（二分类 / LambdaRank）
python -m aifa_quant.cli.main train \
  --start 20230101 --end 20241231 \
  --no-sentiment --cache-only

# 或使用策略模板训练 LambdaRank
python -m aifa_quant.cli.main train \
  --start 20230101 --end 20241231 \
  --template conservative --no-sentiment --cache-only

# 2. 滚动回测（带沪深 300 基准）
python -m aifa_quant.cli.main backtest \
  --start 20240101 --end 20241231 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 --no-sentiment --cache-only

# 或使用 Ensemble 模型回测
python -m aifa_quant.cli.main backtest \
  --start 20240101 --end 20241231 \
  --ensemble data_store/models/ensemble_config.json \
  --top-k 5 --freq 5 --no-sentiment --cache-only

# 3. 初始化模拟账户
python -m aifa_quant.cli.main paper-trade reset --cash 1000000

# 4. 模拟交易（dry-run 试跑）
python -m aifa_quant.cli.main paper-trade run --dry-run

# 5. 正式执行模拟交易
python -m aifa_quant.cli.main paper-trade run

# 6. 查看账户状态
python -m aifa_quant.cli.main paper-trade status

# 7. 生成每周选股报告
python -m aifa_quant.cli.main weekly-report --cache-only

# 8. SHAP 模型解释
python -m aifa_quant.cli.main explain \
  --start 20240101 --end 20241231 \
  --output data_store/reports/shap --cache-only
```

---

## CLI 命令速查

| 命令 | 作用 |
|------|------|
| `python -m aifa_quant.cli.main --help` | 查看所有命令 |
| `python -m aifa_quant.cli.main test-connection --yes` | 测试 iFind MCP 连接 |
| `python -m aifa_quant.cli.main data-update --start 20230101 --end 20241231` | 用 AkShare 更新日线数据（默认） |
| `python -m aifa_quant.cli.main db-info` | 查看 DuckDB 数据概览 |
| `python -m aifa_quant.cli.main train --start 20230101 --end 20241231` | 训练 LightGBM 模型 |
| `python -m aifa_quant.cli.main backtest --start 20240101 --end 20241231 --top-k 5` | 回测 |
| `python -m aifa_quant.cli.main paper-trade reset --cash 1000000` | 初始化模拟账户 |
| `python -m aifa_quant.cli.main paper-trade run --dry-run` | 试跑模拟交易 |
| `python -m aifa_quant.cli.main paper-trade run` | 执行模拟交易 |
| `python -m aifa_quant.cli.main paper-trade status` | 查看模拟账户 |
| `python -m aifa_quant.cli.main factor-analysis --start 20230101 --end 20241231` | 因子有效性分析（IC/RankIC/ICIR/分层/衰减） |
| `python -m aifa_quant.cli.main weekly-report --cache-only` | 生成每周 AI 选股报告 |
| `python -m aifa_quant.cli.main explain --output data_store/reports/shap --cache-only` | SHAP 模型可解释性分析 |
| `python -m aifa_quant.cli.main list-templates` | 查看策略模板 |

常用参数：

- `--no-sentiment`：关闭新闻情绪因子（当前 iFind news MCP 配额紧张，建议关闭）。
- `--source {akshare,tushare,ifind}`：数据源，默认 `akshare`。
- `--cache-only`：只使用 DuckDB 缓存，不调用 iFind。
- `--yes`：跳过 iFind 使用确认。
- `--rolling`：滚动窗口训练，避免未来函数。
- `--top-k N`：持仓数量。
- `--freq N`：再平衡周期（天）。
- `--model-type {binary,lambdarank}`：训练模型类型。
- `--ensemble PATH`：使用 Ensemble 配置文件回测。
- `--template NAME`：使用策略模板覆盖参数。

---

## 项目结构

```text
aifa_quant/
├── aifa_quant/               # Python 包
│   ├── config/               # Pydantic Settings + .env 读取
│   ├── core/                 # 抽象接口（BaseModel / BaseStrategy / BaseBroker / BaseDataSource）
│   ├── data/
│   │   ├── adapters/         # 数据源适配器（AkShare / Tushare / iFind MCP）
│   │   ├── pipeline/         # 增量更新 Pipeline
│   │   └── storage/          # DuckDB 封装
│   ├── features/             # 因子工程（技术 / Alpha101 / 基本面 / 宏观 / 情绪 / 特征筛选）
│   ├── models/               # LightGBM 二分类 / LambdaRank / Ensemble / 注册表 / 滚动训练器
│   ├── strategy/             # TopK-Dropout 策略与策略模板
│   ├── analysis/             # 因子有效性分析 / SHAP 可解释性
│   ├── research/             # 每周选股报告
│   ├── backtest/             # A股规则回测引擎 + 绩效指标
│   ├── execution/            # 模拟/实盘交易执行接口
│   ├── paper_trading/        # 模拟交易引擎
│   └── cli/                  # Typer 命令行入口
├── web/                      # React + Hono + tRPC 前端（可选）
├── scripts/                  # 独立脚本：导出/导入数据、SHAP、参数搜索等
├── tests/                    # 单元测试
├── data_store/               # DuckDB、模型、报告（不提交 Git）
└── docs/                     # 文档
```

---

## 最新回测结果

> 数据：沪深 300 成分股 2023–2024 日线（AkShare 默认数据源）。策略：滚动训练 LightGBM，TopK=5，调仓频率 5 日，已剔除高相关性特征，基准为 000300.SH。

| 指标 | 数值 |
|------|------|
| 总收益率 | 307.43% |
| 年化收益率 | 331.78% |
| 年化波动率 | 28.74% |
| 夏普比率 | 5.265 |
| 最大回撤 | -11.46% |
| 日胜率 | 64.73% |
| 基准总收益 | 16.20% |
| 超额收益 | 291.23% |
| 超额夏普 | 7.408 |

运行滚动回测后查看结果：

```bash
python -m aifa_quant.cli.main backtest \
  --start 20240101 --end 20241231 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 --no-sentiment --cache-only
```

回测同时会输出 `data_store/reports/equity_YYYYMMDD_YYYYMMDD.csv` 与净值 PNG，供前端仪表盘直接读取。

---

## 模拟交易

模拟交易把 DuckDB 中**最新缓存的交易日**当作“今天”，离线生成信号、虚拟下单，不消耗 iFind 额度。

```bash
python -m aifa_quant.cli.main paper-trade reset --cash 1000000
python -m aifa_quant.cli.main paper-trade run --dry-run
python -m aifa_quant.cli.main paper-trade run
python -m aifa_quant.cli.main paper-trade status
```

状态持久化在 DuckDB 的三张表中：

- `paper_positions`：当前持仓
- `paper_orders`：订单明细
- `paper_nav`：每日净值

详细用法见 [`docs/PAPER_TRADING.md`](docs/PAPER_TRADING.md)。

---

## 前端网站（可选）

项目包含一个基于 React + Hono + tRPC + DuckDB 的网站，位于 `web/`，可直接读取本地 DuckDB 数据，无需 MySQL：

```bash
cd web
npm install
npm run dev
```

本地开发地址：`http://localhost:3000`（若 3000 被占用，Vite 会自动切换端口）。

生产构建：

```bash
npm run build
NODE_ENV=production node dist/boot.js
```

---

## Alpha101/191 因子库

`aifa_quant/features/alpha_factors.py` 已注册多个 Alpha101/191 风格因子，特征构建时默认启用：

```bash
python -m aifa_quant.cli.main factor-analysis --start 20230101 --end 20241231
```

可通过 `--corr-threshold 0.95` 自动剔除高相关性因子。

---

## LambdaRank 排序模型与 Ensemble

训练时切换为 LambdaRank（按截面收益排序学习）：

```bash
python -m aifa_quant.cli.main train \
  --start 20230101 --end 20241231 \
  --model-type lambdarank --name lgb_ranker
```

多个模型可用 JSON 配置文件集成 Ensemble：

```json
{
  "method": "weighted_mean",
  "models": [
    {"name": "lgb_binary", "weight": 0.6},
    {"name": "lgb_ranker", "weight": 0.4}
  ]
}
```

```bash
python -m aifa_quant.cli.main backtest \
  --start 20240101 --end 20241231 \
  --ensemble data_store/models/ensemble_config.json
```

---

## SHAP 可解释性

对训练好的模型做 TreeSHAP 分析，输出 summary plot 与特征重要性 CSV：

```bash
python -m aifa_quant.cli.main explain \
  --start 20240101 --end 20241231 \
  --output data_store/reports/shap --cache-only
```

---

## 策略模板

内置 `default`、`aggressive`、`conservative`、`momentum` 四套模板，一键覆盖 top_k / freq / horizon / model_type：

```bash
python -m aifa_quant.cli.main list-templates
python -m aifa_quant.cli.main train --template conservative --cache-only
python -m aifa_quant.cli.main backtest --template momentum --cache-only
```

---

## 每周 AI 选股报告

基于最新训练模型生成 Markdown 选股报告：

```bash
python -m aifa_quant.cli.main weekly-report --cache-only
```

报告保存至 `data_store/reports/weekly_picks_YYYYMMDD.md`。

---

## MkDocs 文档站

文档使用 MkDocs 构建，主题 `readthedocs`：

```bash
mkdocs serve   # 本地预览
mkdocs build   # 输出到 site/
```

---

## Docker 一键启动

已提供 `Dockerfile` 与 `docker-compose.yml`，把 Python CLI 与 Web 服务打包在一起：

```bash
# 构建并启动（需 Docker Desktop / docker daemon 运行中）
docker compose up --build -d
```

访问 `http://localhost:3000` 即可查看由本地 DuckDB 驱动的仪表盘。

默认会把当前目录的 `data_store/` 挂载到容器 `/app/data_store`，因此：

- 先在本地用 CLI 准备好数据，或
- 进入容器运行 CLI：`docker exec -it aifa-quant bash` 后执行 `aifa ...`

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [`HANDOFF.md`](HANDOFF.md) | 开发者交接指南、标准工作流、已知问题 |
| [`docs/PAPER_TRADING.md`](docs/PAPER_TRADING.md) | 模拟交易完整使用说明 |
| [`docs/DATA.md`](docs/DATA.md) | 数据源、DuckDB 表结构、Release 数据导入 |
| [`docs/METRICS.md`](docs/METRICS.md) | 回测绩效指标说明 |
| [`docs/INTEGRATION_ROADMAP.md`](docs/INTEGRATION_ROADMAP.md) | 外部能力接入计划（数据源、模型、实盘等） |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本变更记录 |
| [`AGENTS.md`](AGENTS.md) | 给 AI Agent 的规则手册 |

---

## 注意事项

- **iFind MCP 额度**：当前 news/stock 配额紧张，建议日常回测/训练/模拟交易都加 `--cache-only`，避免意外调用。
- **情绪因子**：默认关闭；需要时可使用 `--sentiment-source free` 通过东方财富/AkShare 获取免费情绪数据。
- **成分股完整性**：沪深 300 成分股通过数据源接口抓取，具体数量取决于源与网络情况。
- **数据与模型不提交 Git**：`data_store/`、`.env`、模型文件、`site/` 已加入 `.gitignore`。
