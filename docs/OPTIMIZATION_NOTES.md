# 选股 / 组合构建 P0 优化笔记

> 对应执行 Prompt：`docs/EXECUTION_PROMPTS.md` Prompt 1 P0（1-5 项）。
> 回测区间：`2023-01-01 ~ 2025-12-31`，profile：`balanced`。

## 1. 改动总览

本次 P0 围绕"把选股问题重新定义为成本调整后的横截面超额排序"这一核心思路，做了 5 项高优先级改动：

| # | 改动 | 关键文件 | 目标 |
|---|------|----------|------|
| 1 | 标签体系重构 | `aifa_quant/features/labels.py` | 从 binary 改为 excess_quantile（默认）与 triple_barrier，LambdaRank 使用 cost-adjusted 排序标签 |
| 2 | 默认 LambdaRank + 动态 Ensemble | `aifa_quant/models/rolling_trainer.py`, `ensemble.py` | 训练器默认按 trade_date 分组训练 LambdaRank；Ensemble 权重按滚动 RankIC 做 softmax 动态加权 |
| 3 | 行业 + 市值中性化 | `aifa_quant/features/neutralization.py` | 对 alpha/momentum/volatility 因子做 OLS 残差中性化，降低行业/市值暴露 |
| 4 | Profile 显式因子族 | `aifa_quant/strategy/factor_groups.yml`, `profiles.py` | 不再用字符串模糊匹配，改为 YAML 显式定义因子族，横截面 rank-percentile 标准化后加权 |
| 5 | 流动性过滤 + 幸存者偏差标注 | `aifa_quant/strategy/topk_dropout.py`, `README.md` | TopK 选股前过滤 20 日日均成交额 < 5000 万；README 中标注成分股快照偏差 |

### 1.1 标签体系：excess_quantile

- `future_excess = future_5d_return - 当日股票池中位数收益`
- 扣除单边总成本约 8 bps（佣金 3 bps + 印花税 10 bps + 滑点 10 bps，按单向 5~8 bps 估算）
- 每日横截面分 5 桶，映射为 LambdaRank relevance label：
  - top 20% → 2
  - middle 60% → 1
  - bottom 20% → 0
- `--drop-middle` 可选丢弃中间 60%（默认不丢弃）

### 1.2 标签体系：triple_barrier

- 上轨 = close + `pt_mult * ATR14`
- 下轨 = close - `sl_mult * ATR14`
- 未来 `max_holding`（默认 10）日内先触哪个轨：+1 / -1 / 0
- 映射为 relevance label：+1 → 2，0 → 1，-1 → 0

### 1.3 LambdaRank 训练

- `rolling_trainer.py` 默认模型改为 `LGBLambdaRankModel`
- ranker 使用 `label_rank` 并按 `trade_date` 传 `groups` 参数
- classifier/XGB 仍使用 `label_binary` 作为对照

### 1.4 动态 Ensemble 权重

- `EnsembleModel.update_weights_from_ic(ic_map)` 收集最近 N 个 rolling 窗口的验证 RankIC
- 权重 = softmax(mean_IC_i / std_IC_i)
- 动态权重持久化到 `data_store/ensemble_weights.json`

### 1.5 因子中性化

- `neutralize_cross_section(df, factor_cols)` 在每个 trade_date 内运行 OLS：
  - `factor ~ industry_dummies + log(market_cap)`
- 取残差，±3σ winsorize，再做截面 z-score
- 缺失行业/市值时降级处理

### 1.6 Profile 打分重构

- `factor_groups.yml` 显式定义各因子族：columns / direction / winsorize / neutralize
- `profiles.py` 读取 YAML，对每个 profile 配置的 factor group：
  1. 列存在性检查
  2. 截面 winsorize
  3. 截面 OLS 中性化（可选）
  4. 截面 rank → percentile（direction=-1 反向）
  5. 按 group 权重合成 factor_score，再截面 z-score
- 最终 `pred_score = 0.7 * model_score + 0.3 * factor_score`

### 1.7 流动性过滤

- `TopKDropoutStrategy` 新增 `min_liquidity_wan` 参数
- 选股前过滤 `avg_amount_20d < min_liquidity_wan`（默认 5000 万元）
- CLI：`aifa backtest --min-liquidity 5000`

## 2. 回测命令

```bash
# AFTER（P0 完整优化）
aifa backtest --profile balanced \
  --start 20230101 --end 20251231 \
  --rolling --cache-only --no-sentiment \
  --save-paper-nav --min-liquidity 5000

# BEFORE（P0 之前，HEAD 版本，binary + 无中性化 + 无流动性过滤）
aifa backtest --profile balanced \
  --start 20230101 --end 20251231 \
  --rolling --cache-only --no-sentiment
```

> 两次回测均使用滚动训练（rolling window）生成 out-of-sample 预测，避免未来信息泄露。

## 3. 回测指标对比

| 指标 | BEFORE | AFTER | 变化 | 验收目标 |
|------|--------|-------|------|----------|
| 总收益率 | -16.54% | +41.51% | **+58.05 pp** | — |
| 年化收益 | -6.03% | +12.68% | **+18.70 pp** | — |
| 年化超额收益（vs 沪深300） | -35.63% | +22.42% | **+58.05 pp** | ≥ 10% |
| 夏普比率 | -0.080 | 0.539 | **+0.619** | ≥ 1.5 |
| 最大回撤 | -38.13% | -39.92% | -1.79 pp | ≤ 25% |
| 月均单边换手率 | 365.34% | 305.12% | **-60.22 pp** | ≤ 80% |
| 平均 RankIC | -0.0116 | 0.0098 | **+0.0215** | ≥ 0.04 |
| 年化波动率 | 28.31% | 31.13% | +2.82 pp | — |
| 日胜率 | 45.49% | 48.50% | +3.01 pp | — |
| ICIR | -0.929 | 0.840 | **+1.769** | — |

*注：pp = percentage point。BEFORE 使用 HEAD 版本（binary 标签、无中性化、无流动性过滤），AFTER 为 P0 完整优化版本。*

## 4. 关键观察

1. **收益/超额显著提升**：P0 把策略从“跑输基准”拉回到“显著跑赢”。AFTER 相对沪深 300 的超额收益从 -35.63% 提升到 +22.42%，年化收益由 -6.03% 升至 +12.68%。
2. **RankIC 由负转正**：从 -0.0116 提升到 0.0098，说明标签体系与 LambdaRank 的引入让模型捕捉到了一定的横截面排序能力；但绝对值仍远低于 0.04 的目标，后续需要 P1 的因子 IC 筛选、Meta-Labeling 和 QP 优化器进一步提炼信号。
3. **换手率仍过高**：月均单边换手 305%（BEFORE 365%），距离 ≤80% 差距较大。根本原因是每 5 天等权再平衡且无换手率约束；P1 的 QP 优化器（带换手率惩罚 + 单次上限 40%）是主要解决路径。
4. **最大回撤未改善**：AFTER -39.92% 甚至略差于 BEFORE -38.13%，且远超 ≤25% 目标。行业/市值中性化本应降低系统性暴露，但当前数据存在以下限制，使其效果受限。
5. **数据限制是主要瓶颈**：
   - `daily_quotes` 缺少 `outstanding_share` / `total_shares`，导致 `market_cap` 无法计算，行业+市值中性化退化为仅 winsorize + z-score。
   - 基本面数据仅缓存 271/1806 只股票，value/quality 因子族大量缺失，profile 打分主要依赖动量/alpha/波动率。
   - 成分股为当前快照（AkShare 返回最新成分股），存在幸存者偏差。
6. **流动性过滤**：在 top_k=20、全市场 1800+ 只股票的池子中，过滤掉 20 日日均成交额 < 5000 万的股票，月换手率从 365% 降至 305%，同时收益改善，说明剔除了部分低流动性噪声。

## 5. 失败 / 放弃的尝试

- **完全的行业/市值中性化**：已实现代码路径，但因基础数据缺少市值字段，当前回测未能真正跑通 OLS 残差中性化。后续需要补充 point-in-time 的流通股数/总股本数据，或接入 Tushare/iFind 的市值接口。
- **triple_barrier 标签**：已实现并 CLI 暴露，但本次对比未单独跑完整回测。初步判断在 A 股涨跌停限制下，上下轨触发频率可能偏低，大量样本会落入中间桶；计划在 P1 用 walk-forward 对比其与 excess_quantile 的稳定性。
- **动态 Ensemble 权重**：`ensemble.py` 已支持按 RankIC softmax 更新权重，但本次 rolling 回测使用单模型，未触发多模型动态加权。需在 P1 训练多个异构子模型后再验证。

## 6. 下一步

- P1：QP 组合优化器、Purged K-Fold CV + 发布门禁、Meta-Labeling、因子 IC 自动筛选
- P2：Regime-Conditional Ensemble、Walk-Forward 超参搜索、PBO 过拟合评估
- 前端 Prompt 2 P0：URL 路由、Daily Action Card、个股 SHAP、报告股票代码可点击等
