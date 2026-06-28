# AifaQuant 产品迭代路线图

> 本文档基于与 [AKQuant](https://github.com/akfamily/akquant) 的对比分析，确定 AifaQuant 的差异化定位与分阶段迭代方向。
> 2026-06-26 更新：已根据最近大量改动刷新状态。

---

## 1. 项目定位

**AifaQuant 不是“另一个 AKQuant”。**

AKQuant 是一个面向量化开发者的高性能 SDK（Rust 核心 + AKShare 生态），提供底层工具（表达式引擎、技术指标、实盘网关），但**不解决“选哪只股票”**的问题。

AifaQuant 的定位是：

> **面向“懂投资但不想写代码”的 A股投资者的 AI 选股产品。**

用户打开浏览器就能看到：

- 今天 AI 推荐买哪几只股票（按 5 种投资风格 profile 区分）；
- 为什么推荐这些股票（因子贡献、模型置信度、SHAP 解释）；
- 模拟盘历史表现如何（叠加沪深 300 / 上证指数基准）；
- 每个因子是否真正有效（IC、分层收益）。

**核心壁垒是“选股有效性”，不是“交易执行速度”。**

---

## 2. 与 AKQuant 的对比结论

| 维度 | AKQuant | AifaQuant | 判断 |
|------|---------|-----------|------|
| 选股框架完整度 | 只有空壳适配器 | 端到端 pipeline（数据 → 因子 → 模型 → 策略 → 回测 → 模拟交易） | ✅ 领先 |
| 因子丰富度 | 103 个 TA 指标 + Alpha101 表达式引擎 | 技术/基本面/宏观/Alpha101 风格因子 | ⚠️ 中等，需继续扩展 |
| 模型多样性 | 用户自己接 | LightGBM 二分类 + LambdaRank + Ensemble + XGBoost | ✅ 较完整 |
| 截面 Alpha 因子 | Polars 表达式引擎 | 已实现部分 Alpha101/191 风格因子 | ⚠️ 需持续补充 |
| 基本面 + 宏观因子 | 不涉及 | 已内置 PE/PB/ROE + CPI/PMI/M2 | ✅ 领先 |
| 因子有效性验证 | 无 | `factor-analysis` 已输出 IC/RankIC/ICIR/分层/衰减 | ✅ 已具备 |
| Web 产品化 | 无 | React + Hono + tRPC + DuckDB Dashboard 已可用 | ✅ 领先 |
| 实盘交易 | CTP 网关 | 仅模拟交易（ intentionally ） | — 战略差异 |

**结论**：基础框架与产品化已领先，下一步重点在**因子深度、模型有效性验证、实盘前风控与数据质量**。

---

## 3. 迭代路线

### Phase 1 — 产品可用 + 零配置启动（已基本完成 ✅）

目标：让用户能零配置跑起来，并在 Web 上看到 AI 选股结果和证据。

- [x] **因子有效性分析模块**
  - IC / RankIC / ICIR 计算
  - 分层回测（Quantile Portfolio）及可视化
  - 因子衰减曲线（未来 1/5/10/20 天 IC）
  - 输出位置：`aifa_quant/analysis/factor_analysis.py`

- [x] **Web Dashboard 接真实数据**
  - 后端从 DuckDB 读取 `daily_quotes` / `paper_positions` / `paper_orders` / `paper_nav`
  - 前端展示：今日选股信号、当前持仓、净值曲线、沪深 300 / 上证指数基准
  - 已移除对 MySQL 的依赖，DuckDB 为默认存储

- [x] **零配置启动（部分完成）**
  - 默认不需要 iFind token；日线/指数/成分股走 AkShare
  - `scripts/daily_refresh.py` 自动完成首次拉取后的每日增量更新
  - Docker 配置已提供，但本机构建受网络限制未验证

- [x] **模拟盘可视化**
  - Web 首页展示各 profile 的“今日 AI 推荐”与“历史模拟盘盈亏”
  - 订单明细、持仓成本、每日净值已可通过 DuckDB 查询

### Phase 2 — 因子深度 + 模型可靠性（进行中 ⏳）

目标：显著提升选股有效性，建立模型解释能力。

- [x] **因子库扩展**
  - 已接入 Alpha101/191 风格因子（`features/alpha_factors.py`）
  - 行业因子、市值中性化、流动性因子、波动率因子（部分在技术因子中）
  - 待补充：因子正交化 / 去市值暴露

- [x] **模型升级**
  - 已支持 LambdaRank / LightGBM Ranker（`--model-type lambdarank`）
  - 已支持多模型 Ensemble
  - 已添加 XGBoost 模型适配器
  - 待补充：自动特征选择、模型置信度分位数展示

- [x] **可解释性**
  - SHAP 分析已集成到 CLI（`explain` 命令）
  - 待做：把 SHAP 结果展示到 Web 首页/模型页

- [ ] **交互式因子商店**
  - Web 上勾选/关闭因子组合
  - 实时重新跑回测并对比净值曲线
  - 保存为自定义策略模板

- [x] **舆情因子（免费源）**
  - 已接入东方财富 / AkShare 免费情绪数据（`--sentiment-source free`）
  - iFind news MCP 仍作为可选，不默认开启

### Phase 3 — 增长与社区（待启动 ⏳）

目标：降低使用门槛，建立内容获客能力。

- [ ] **PyPI 发布**
  - `pip install aifa-quant`
  - 包含 CLI 和 Web 启动命令

- [ ] **策略模板市场**
  - 内置 5-10 个选股策略模板：动量、价值、质量、低波、多因子混合
  - 用户一键回测、一键模拟交易

- [ ] **文档站**
  - MkDocs + GitHub Pages
  - 教程风格："如何用 AI 选股"，而非纯 API 文档

- [ ] **每周 AI 选股报告自动化**
  - 已支持 CLI 生成 `weekly-report`
  - 待接入：GitHub Actions 定时跑模型（若 Actions 恢复）并发布到 Discussions/公众号/文档站

- [x] **免费数据源完善**
  - ✅ AkShare 已接入（日线/指数/成分股/免费情绪）
  - ✅ Tushare 适配器已提供（需要用户 token）
  - 基本面数据若 AkShare 稳定，可逐步迁移部分字段，降低对 iFind 的依赖

---

## 4. 红线（不要做）

- **不要用 Rust 重写引擎**：Python 足够，用户不感知回测速度差异。
- **不要支持期货/期权/加密货币**：专注 A股选股。
- **不要做实盘交易接口**：法律风险高，且目标用户群不需要。
- **不要在交易执行层花大量时间**：模拟交易已够用，壁垒在选股。
- **不要追求 star 数量**：追求“有人每天打开 Dashboard 看选股信号”。
- **不要默认开启 iFind**：任何 iFind 调用都必须用户显式确认（已实施 `--yes`）。
- **不要把数据文件提交 Git**：`data_store/` 与 DuckDB 已加入 `.gitignore`。

---

## 5. 下一步建议（按优先级）

1. **模型重训与回测（当务之急）**
   - 用沪深 300 + 中证 500 + 中证 1000 的新 universe 重新训练模型
   - 输出新 universe 下的滚动回测绩效报告
   - 评估各 profile 在真实分布上的差异

2. **Web 可解释性**
   - 在首页/模型页展示每只股票 Top-5 贡献因子
   - 展示全局特征重要性趋势图

3. **因子正交化与去市值暴露**
   - 降低因子共线性，提升模型稳定性
   - 为 `value` / `growth` 等风格 profile 提供更干净的信号

4. **Docker 一键启动验证**
   - 解决本机无法拉取基础镜像的问题
   - 验证 `docker compose up` 能完整跑通数据拉取 + Web 启动

5. **GitHub Actions 恢复**
   - 在仓库设置中启用 Actions
   - 配置自动 lint/test 与每周选股报告生成
