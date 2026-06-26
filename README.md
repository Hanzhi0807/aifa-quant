# AifaQuant - A股 AI 量化研究与回测框架

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
![License](https://img.shields.io/badge/license-MIT-green)
[![Release](https://img.shields.io/github/v/release/ivyzhi0807/aifa-quant)](https://github.com/ivyzhi0807/aifa-quant/releases)

AifaQuant 是一个本地优先的 **A股 AI 量化研究与回测框架**，覆盖数据获取、因子工程、模型训练、策略回测到模拟交易的完整闭环。

- **数据源**：默认 [AkShare](https://www.akshare.xyz/)（免费），日线/指数/成分股无需 token；基本面/宏观/情绪仍走同花顺 iFind MCP。
- **存储**：本地 DuckDB，日线、基本面、宏观数据一次缓存，离线复用。
- **模型**：LightGBM 二分类选股，输出上涨概率。
- **策略**：TopK-Dropout 轮动。
- **回测**：自定义 A股规则引擎（T+1、涨跌停、100 股整数手、佣金、印花税）。
- **模拟交易**：基于训练好的模型每日生成信号，用 `SimulatedBroker` 虚拟成交，状态持久化到 DuckDB。

> ⚠️ 本项目处于研究与框架验证阶段，回测和模拟交易结果**不代表实盘表现**。

---

## 目录

- [快速开始](#快速开始)
- [完整工作流](#完整工作流)
- [CLI 命令速查](#cli-命令速查)
- [项目结构](#项目结构)
- [最新回测结果](#最新回测结果)
- [模拟交易](#模拟交易)
- [前端网站（可选）](#前端网站可选)
- [文档索引](#文档索引)
- [注意事项](#注意事项)

---

## 快速开始

### 1. 环境准备

```bash
cd d:/kimi/aifa_quant

# 安装依赖
pip install -r requirements.txt

# 复制并编辑 .env（填入 iFind MCP token）
cp .env.example .env
```

> `.env` 已加入 `.gitignore`，**不要提交到 Git**。

### 2. 获取数据（二选一）

**推荐：从 GitHub Release 导入测试数据（不消耗 iFind 额度）**

```bash
python scripts/import_source_data.py data_store/
```

 Release 包含沪深 300 成分股 2023–2024 日线 + 基本面 + 宏观数据：
 [v0.4.0-data-full](https://github.com/ivyzhi0807/aifa-quant/releases/tag/v0.4.0-data-full)

**或直接用 AkShare 下载（默认，免费）**

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

**或强制走 iFind MCP 下载（需要 token 和额度）**

```bash
python -m aifa_quant.cli.main data-update \
  --source ifind \
  --symbol-file data_store/csi300_symbols.txt \
  --start 20230101 --end 20241231 \
  --workers 5 --fundamental --macro
```

### 3. 验证数据

```bash
python -m aifa_quant.cli.main db-info
```

---

## 完整工作流

```bash
# 1. 训练选股模型
python -m aifa_quant.cli.main train \
  --start 20230101 --end 20241231 \
  --no-sentiment --cache-only

# 2. 滚动回测（带沪深 300 基准）
python -m aifa_quant.cli.main backtest \
  --start 20240101 --end 20241231 \
  --rolling --benchmark 000300.SH \
  --top-k 5 --freq 5 --no-sentiment --cache-only

# 3. 初始化模拟账户
python -m aifa_quant.cli.main paper-trade reset --cash 1000000

# 4. 模拟交易（dry-run 试跑）
python -m aifa_quant.cli.main paper-trade run --dry-run

# 5. 正式执行模拟交易
python -m aifa_quant.cli.main paper-trade run

# 6. 查看账户状态
python -m aifa_quant.cli.main paper-trade status
```

---

## CLI 命令速查

| 命令 | 作用 |
|------|------|
| `python -m aifa_quant.cli.main --help` | 查看所有命令 |
| `python -m aifa_quant.cli.main test-connection` | 测试 iFind MCP 连接 |
| `python -m aifa_quant.cli.main data-update --start 20230101 --end 20241231` | 用 AkShare 更新日线数据（默认） |
| `python -m aifa_quant.cli.main db-info` | 查看 DuckDB 数据概览 |
| `python -m aifa_quant.cli.main train --start 20230101 --end 20241231` | 训练 LightGBM 模型 |
| `python -m aifa_quant.cli.main backtest --start 20240101 --end 20241231 --top-k 5` | 回测 |
| `python -m aifa_quant.cli.main paper-trade reset --cash 1000000` | 初始化模拟账户 |
| `python -m aifa_quant.cli.main paper-trade run --dry-run` | 试跑模拟交易 |
| `python -m aifa_quant.cli.main paper-trade run` | 执行模拟交易 |
| `python -m aifa_quant.cli.main paper-trade status` | 查看模拟账户 |

常用参数：

- `--no-sentiment`：关闭新闻情绪因子（当前 iFind news MCP 配额紧张，建议关闭）。
- `--source {akshare,ifind}`：数据源，默认 `akshare`。
- `--cache-only`：只使用 DuckDB 缓存，不调用 iFind。
- `--rolling`：滚动窗口训练，避免未来函数。
- `--top-k N`：持仓数量。
- `--freq N`：再平衡周期（天）。

---

## 项目结构

```text
aifa_quant/
├── aifa_quant/               # Python 命名空间包
│   ├── config/               # Pydantic Settings + .env 读取
│   ├── core/                 # 抽象接口（BaseModel / BaseStrategy / BaseBroker / BaseDataSource）
│   ├── data/
│   │   ├── adapters/         # iFind MCP 适配器（stock / index / macro / news）
│   │   ├── pipeline/         # 增量更新 Pipeline
│   │   └── storage/          # DuckDB 封装
│   ├── features/             # 因子工程（技术 / 基本面 / 宏观 / 情绪 / 特征筛选）
│   ├── models/               # LightGBM、模型注册表、滚动训练器
│   ├── strategy/             # TopK-Dropout 策略
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

> 数据：沪深 300 成分股 2023–2024 日线 + 基本面 + 宏观。  
> 策略：滚动训练，TopK=5，调仓频率 5 日，已剔除高相关性特征。

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

![滚动回测净值曲线](docs/images/equity_curve_2023_2024_rolling.png)

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

项目包含一个基于 React + Hono + tRPC + Drizzle + MySQL 的网站，位于 `web/`：

```bash
cd web
npm install
cp .env.example .env
# 编辑 .env 填入 DATABASE_URL
npm run db:push
npm run dev
```

本地开发地址：`http://localhost:3000`

> 线上预览链接当前不可用，请使用本地开发服务器。

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
- **情绪因子**：默认关闭；等 iFind news MCP 恢复后再尝试 `--sentiment`。
- **GitHub Actions**：当前账号被禁用 Actions，CI 徽章不会自动更新。
- **成分股完整性**：沪深 300 成分股通过新浪财经抓取，去重后约 288 只，非完整 300 只。
- **数据与模型不提交 Git**：`data_store/`、`.env`、模型文件已加入 `.gitignore`。
