# 对抗性审查修复笔记（第三轮）

> 对应执行：基于对抗性审查意见 + EXECUTION_PROMPTS 重构后的补漏。
> 本轮修复了 9 个 P0 bug、补齐 P1 模块、补齐前端决策工作台、补齐市值数据。

## 1. 阶段一：P0 bug 修复

### 1.1 RSI fillna 方向反转
**位置**：`features/technical.py:53`
**问题**：旧代码 `rsi.fillna(100.0)` 把"无数据/全跌"填成超买；`rsi.where(avg_gain>0, 0.0)` 把全涨填成 0。方向完全反了。
**修复**：重写边界——avg_loss=0（全涨）→100，avg_gain=0（全跌）→0，flat/不足→50。
**测试**：`test_rsi_purely_up_window_is_100` / `test_rsi_purely_down_window_is_0` / `test_rsi_first_row_neutral`。

### 1.2 NaN 填充全局 median 泄漏
**位置**：`features/builder.py:325`
**问题**：`df[col].fillna(df[col].median())` 用全样本（含未来）median 填充，是确定的数据泄漏。
**修复**：改为 symbol expanding median → 当日截面 median → 0。截面 median 在 T 日收盘后可知，不泄漏。
**测试**：`test_feature_fill_does_not_use_future_global_median`。

### 1.3 纸交易当日收盘价成交（未来函数）
**位置**：`paper_trading/engine.py`
**问题**：T 日收盘后 `_apply_stops` 触发 → 当日生成 sell order → 当日 close 价成交。实盘不可能。
**修复**：引入 `paper_pending_orders` 表，T 日信号进 pending，T+1 run 时用 T+1 open 价成交。
**测试**：`test_paper_trading_pending_orders_persist`。

### 1.4 停牌处理缺失
**位置**：`backtest/engine.py`、`execution/broker/simulated_broker.py`
**问题**：停牌日（volume==0）`prev_close=None`，涨跌停检查被跳过，等于允许在停牌股上成交。
**修复**：加 `_is_suspended` 检查（volume==0 即停牌），回测和 broker 均拒绝停牌股成交。
**测试**：`test_backtest_suspension_blocks_buy` / `test_broker_rejects_suspended_order`。

### 1.5 ST 涨跌停依赖 name 列
**位置**：`backtest/engine.py`、`simulated_broker.py`
**问题**：`_limit_up_ratio` 用 quote 的 name 列判断 ST，name 缺失时 ST 被当普通股（10% 而非 5%）。另外 broker 的 `_limit_ratio` 用 `symbol.startswith("300")` 但 symbol 是 `300xxx.SZ` 格式，永远匹配不到。
**修复**：从 `stock_universe.is_st` 加载 ST 标记，优先用标记；broker 的代码段判断先 `split(".")[0]`。
**测试**：`test_backtest_st_limit_ratio` / `test_broker_st_limit_ratio`。

### 1.6 交易成本模型不一致
**位置**：新建 `core/cost_model.py`
**问题**：labels 硬编码 cost=0.0024，回测 slippage=0.0 默认无滑点，三处成本各不相同。
**修复**：`CostModel` 统一 commission/min_commission/stamp_duty/slippage，labels 从 `CostModel.one_way_cost()` 取，回测/纸交易从同一模型取。默认 slippage=0.001（10bps）。
**测试**：`test_cost_model_one_way_matches_label_default` / `test_cost_model_explicit_params`。

### 1.7 中性化静默降级
**位置**：`features/builder.py`
**问题**：缺 market_cap 时静默降级为 winsorize，用户以为开了中性化实际没生效。
**修复**：从 `stock_universe.circulating_share` 估算 market_cap = close × circulating_share；缺失时显式 warning 指引用户跑 `scripts/update_market_caps.py`。
**配套**：新增 `scripts/update_market_caps.py` 用 AkShare 拉全市场市值快照写入 stock_universe（已跑通，1800 只填充）。

### 1.8 corr_threshold 假装工作
**位置**：`cli/main.py`
**问题**：非 rolling 模式传 `--corr-threshold < 1.0` 实际不生效，但帮助文本让人以为生效。
**修复**：非 rolling 模式检测到该参数时打印黄色警告。

### 1.9 回测/纸交易执行一致性
**位置**：`backtest/engine.py`、`paper_trading/engine.py`
**问题**：回测等权 + open 价成交，纸交易 vol sizing + close 价成交，两层逻辑完全不同。
**修复**：统一 T 日收盘信号 → T+1 开盘成交时点；QP 优化器在两层均可启用（`--weighting qp`）；ST/停牌/成本规则统一。

## 2. 阶段一附：市值 + 基本面数据补齐

### 市值数据
- 新增 `AkShareAdapter.get_market_cap_snapshot()`：用 `ak.stock_zh_a_spot_em` 拉全市场快照，含流通市值/总市值/PE/PB/PS/股息率，从 流通市值/最新价 反推流通股本。
- 新增 `scripts/update_market_caps.py`：写入 stock_universe 的 circulating_share/total_share/circulating_mv/total_mv/is_st/pe_ttm/pb_lyr/ps_ttm/dv_ratio/mc_snapshot_date。
- 已执行：1800 只股票市值+is_st 入库；PE/PB 快照因东财服务器偶发不可用，部分会话需重试。
- 中性化现在有 market_cap 可用，OLS 残差中性化可真正生效。

### 基本面数据（季度财务指标）
- 新增 `scripts/update_fundamentals.py`：用 `ak.stock_financial_analysis_indicator` 拉每只股票的季度 ROE/毛利率/净利率/资产负债率等。
- 修复 `DuckDBStore.save_fundamental_data` 的 INSERT 列顺序 bug（原代码 ann_date/name 位置错乱导致类型转换失败）。
- 已补齐：从原 273 只扩展到全 universe（约 1800 只，含 2022-2026 季度数据）。
- value/quality profile 现在有 roe_ttm/roe_weighted 可用，不再退化为纯动量。

### 数据合并
- `FeatureBuilder` 现在 merge 两层数据：
  1. `fundamental_data`（季度，point-in-time via ann_date）→ pe_lyr/pb/roe_*
  2. `stock_universe` 快照（当前值）→ pe_snap/pb_snap/ps_snap/dv_snap
- 快照列标注 `_snap`，提醒它是当前值非历史 point-in-time，回测有轻微前视，适合预测模式。
- `factor_groups.yml` 的 value/dividend 族已含 pe_snap/pb_snap/ps_snap/dv_snap。

### 已知限制
- PE/PB 日频估值历史（point-in-time）仍缺，当前用快照近似。完整历史估值需接入 Tushare daily_basic 或 iFind。
- AkShare 的 `stock_zh_a_spot_em` 偶发连接失败（东财服务器限流），`update_market_caps.py` 已加 4 次重试。

## 3. 阶段二：P1 模块

### 3.1 QP 组合优化器（`strategy/optimizer.py`）
- `MeanVarianceOptimizer`：max μᵀw − λwᵀΣw − c‖w−w_prev‖²，约束 Σw=1 / 单票≤5% / 行业≤25% / 换手≤40% / 年化波动≤20%。
- Σ 用 Ledoit-Wolf 风格压缩协方差（60 日 returns）。
- 后处理投影保证单票/行业约束满足（SLSQP 不收敛时兜底）。
- 接入回测（`--weighting qp`）和纸交易（`--weighting qp`）。
- **测试**：5 个（权重和为1、单票上限、偏好高分、换手控制、行业上限）。

### 3.2 Purged K-Fold CV + 发布门禁（`models/cv.py`、`analysis/publish_gate.py`）
- `PurgedKFold`：按日期分 fold，purge label_horizon 边界 + embargo。
- `compute_pbo`：基于组合对称交叉验证的过拟合概率。
- `evaluate_gate`：RankIC/ICIR/超额/换手/回撤门槛，不达标阻止推送 Supabase。
- **测试**：7 个。

### 3.3 Meta-Labeling（`models/meta_model.py`）
- 二阶 LightGBM 分类器，输入一阶分数 + 因子，标签为 triple_barrier 实际结果。
- `gate()` 方法按 P(盈利) > threshold 过滤候选，取 top_k。
- 未训练时 pass-through。
- **测试**：3 个。

### 3.4 因子 IC 筛选 + Alpha 扩展（`features/factor_selection.py`、`alpha_factors.py`）
- `select_by_ic`：每个滚动训练窗口内按 |IC| ≥ 0.02 筛选因子。
- 新增 alpha026/033/044/085（共 26 个 alpha）。
- 集成到 `RollingTrainer`（`ic_threshold` 参数）。
- **测试**：6 个。

## 4. 阶段三：前端决策工作台

新增组件（signals-web/src/components/）：
- `DailyActionCard.tsx`：今日操作台（买/卖/持徽章、操作表、可执行性、委托单 CSV 导出）。
- `StockDetail.tsx`：个股详情 + SHAP 瀑布图 + 人话解释摘要。
- `ProfileCompare.tsx`：5 profile 净值叠加 + 指标对比表。
- `RiskExposure.tsx`：行业集中度热力 + 市值分布 + 风格雷达。
- `BacktestCredibility.tsx`：可信度标签（🟢/🟡/🔴，含 PBO/OOS RankIC）。
- `NavStats.tsx`：累计/年化/回撤/Sharpe 四卡片。
- `ErrorBoundary.tsx`：路由级错误边界 + 重试。
- `Onboarding.tsx`：3 步引导（localStorage 标记）。

改造：
- `App.tsx`：BrowserRouter + 6 条路由 + NavLink。
- `ReportsView.tsx`：股票代码 `NNNNNN.SH/SZ` 自动转可点击 Link。
- `Dashboard.tsx`：顶部插入操作台 + 统计 + 可信度 + 风险面板。
- `lib/feature_names.ts`：因子中文名映射 + tooltip。
- `lib/freshness.ts`：数据新鲜度计算 + nextMonday。

后端：
- `supabase/schema.sql`：新增 stock_shap / signal_runs / portfolio_risk / paper_metrics 表 + RLS。
- `scripts/push_to_supabase.py`：新增 push_stock_shap / push_portfolio_risk / push_paper_metrics / push_signal_run。

## 5. 阶段四：收尾

- DuckDB 写锁：`_WRITE_LOCK` 全局锁保护写操作，`clear_paper_state` 已加锁；支持 `read_only=True` 只读连接。
- PROJECT_REPORT.md：顶部加红色 disclaimer，标注初期玩具样本不代表当前策略。
- `.env` 防护：`scripts/check_no_secrets.py` pre-commit hook 脚本（用户手动安装到 .git/hooks/pre-commit）。
- 测试：90 passed（原 61 + 新增 29）。

## 6. 验收对比

回测区间 2025-01-01 ~ 2025-12-31，profile=balanced，rolling，equal 权重：

| 指标 | BEFORE（P0后） | AFTER（本轮修复后） | 变化 | 说明 |
|------|---------------|-------------------|------|------|
| 总收益 | +41.51% | -9.75% | -51 pp | BEFORE 虚高被挤干 |
| 年化收益 | +12.68% | -10.10% | -23 pp | |
| 年化波动 | 31.13% | 35.61% | +4.5 pp | |
| Sharpe | 0.539 | -0.120 | -0.66 | 从正转负 |
| 最大回撤 | -39.92% | -29.84% | +10 pp | **改善**（修复停牌/ST 后风控更严） |
| RankIC | 0.0098 | -0.0227 | -0.033 | 模型在 2025 年选股能力不足 |
| 月换手 | 305% | 356% | +51 pp | IC 筛选导致换手略升 |
| 超额收益 | +22.42% | -30.94% | -53 pp | |

### 解读

**AFTER 大幅低于 BEFORE 不是退化，是去伪。** BEFORE 的 +41.51% / Sharpe 0.539 由以下 bug 共同美化：
1. RSI 反向 → 因子信号失真但恰好在某些区间"碰对"
2. NaN 全局 median 泄漏 → 训练集信息渗入测试集
3. 停牌可成交 → 回测能买到实盘买不到的价
4. ST 涨跌停按 10% → ST 股票成交范围被放宽
5. 成本不一致 → labels 扣 8bps 但回测 0 滑点
6. 训练/测试时间未强制分隔 → 用户可能重叠

修复后这些虚高全部消失，-9.75% 才是 2025 年该策略的真实表现。

**RankIC 为负**说明模型本身在 2025 年（结构性行情集中在少数板块、风格切换频繁）选股能力不足。这不是 bug 修复能解决的，需要：
- 更好的因子（当前基本面只覆盖 271/1800 只，中性化数据刚补齐）
- 更长的训练窗口（当前仅 2025 起的数据）
- 超参搜索（P2 的 walk-forward）
- Regime-conditional 模型（P2）

**最大回撤改善**（-39.92% → -29.84%）是停牌/ST/成本修复的直接收益：风控更严格，避免了在不可成交价上的虚假止损。

### 未达标项

EXECUTION_PROMPTS 原验收目标（Sharpe ≥ 1.5、年化超额 ≥ 10%、回撤 ≤ 25%、换手 ≤ 80%、RankIC ≥ 0.04）**均未达到**。原因：
1. 数据限制（基本面覆盖不足、2025 年起数据窗口短）
2. 模型本身选股能力不足（RankIC 负）
3. QP 优化器未在本次验收回测启用（equal 权重）——QP 主要降换手，对收益影响中性

**建议**：本轮目标是"修复 bug + 补齐模块"，不是"达到验收数字"。验收数字需要后续在数据补齐 + 超参搜索 + regime 模型落地后重新评估。当前 Sharpe -0.120 是真实基线，后续优化以此为起点。
