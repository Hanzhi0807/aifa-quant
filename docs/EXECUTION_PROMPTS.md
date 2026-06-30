# 执行 Prompts（三方意见合并版）

## Prompt 1：选股逻辑 + 组合构建 全面优化

```
项目根目录：d:\kimi\aifa_quant
A 股 AI 量化选股项目，Python 包在 aifa_quant/。当前链路：
  特征工程 → LightGBM binary/LambdaRank → Profile 加权 → TopK-Dropout → 等权/波动率仓位 → ATR 止损

核心矛盾：选股问题的本质不是"预测涨跌"，而是"在约束条件下构建高夏普、可控回撤、低换手、可执行的组合"。
当前模型目标和组合构建是脱节的，下面按优先级分 P0/P1/P2 三层实现。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0 — 必做，收益最大（先做这 5 项）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. 标签体系重构：从"涨跌二分类"到"成本调整横截面超额排序"
- 新建 aifa_quant/features/labels.py
- 实现三种标签，CLI 参数 --label-type {binary,excess_quantile,triple_barrier}，默认 excess_quantile：
  
  (a) excess_quantile（默认）：
      - future_excess = future_5d_return - 当日股票池中位数收益
      - 扣除单边交易成本（佣金 0.03% + 印花税 0.1% + 滑点 0.1%，合计约 5-8 bps）
      - 按每日横截面分 5 桶，top 20% = 2, next 20% = 1, ..., bottom 20% = 0
      - 中间 60% 可选丢弃（--drop-middle 开关，默认不丢弃）
      - 用于 LambdaRank 的 relevance label
  
  (b) triple_barrier：
      - 以入场日 close 为基准，上轨 = close + pt_mult*ATR14，下轨 = close - sl_mult*ATR14
      - 未来 max_holding=10 个交易日内，先触哪个轨：+1（止盈）/ -1（止损）/ 0（超时）
      - LambdaRank 映射：+1→2, 0→1, -1→0
      - 参数 pt_mult=2.0, sl_mult=1.0 可在 CLI 传入
  
  (c) binary：保留原有，作为对照基线

- 修改 rolling_trainer.py 默认调用 excess_quantile
- 验证：对比三种标签在相同回测期的 Sharpe/超额

## 2. 默认启用 LambdaRank + 动态集成权重
- 修改 aifa_quant/models/__init__.py：默认模型改为 LGBLambdaRankModel
- 训练时按 trade_date 分组传 group 参数
- CLI `aifa train` 增加 --model {classifier,lambdarank,xgboost,ensemble} 选项，默认 lambdarank
- 修改 aifa_quant/models/ensemble.py：
  - 现有固定权重 → 改为按最近 N 个滚动窗口的验证 RankIC 做加权
  - 公式：weight_i = softmax(rolling_mean_IC_i / IC_std_i)
  - 每次 rolling 训练自动更新权重，存入 data_store/ensemble_weights.json

## 3. 因子中性化（行业 + 市值）
- 新建 aifa_quant/features/neutralization.py
- 实现 neutralize_cross_section(df, factor_cols, date_col='trade_date')：
  - 每个 trade_date 内，对每个因子做 OLS 回归：factor ~ industry_dummies + log(market_cap)
  - 取残差作为中性化后的因子值
  - 然后做横截面 z-score（winsorize 在 ±3σ）
- FeatureBuilder 增加 neutralize=True 参数，对 alpha101 + momentum + volatility 做中性化
- CLI `aifa train --neutralize/--no-neutralize`

## 4. Profile 打分重构：显式因子族 + 横截面标准化
- 新建 aifa_quant/strategy/factor_groups.yml：
  ```yaml
  momentum:
    columns: [momentum_5d, momentum_20d, momentum_60d]
    direction: 1  # 越大越好
    winsorize: true
    neutralize: true
  value:
    columns: [pe_ttm_inv, pb_ratio_inv]
    direction: 1
    winsorize: true
    neutralize: true
  quality:
    columns: [roe, roa, gross_margin]
    direction: 1
    winsorize: true
    neutralize: false
  low_volatility:
    columns: [volatility_20d, atr_14]
    direction: -1  # 越小越好
    winsorize: true
    neutralize: true
  ```
- 修改 profiles.py：
  - 不再用 factor.lower() in c.lower() 字符串匹配
  - 改为读 factor_groups.yml，每组先横截面 rank → percentile，再按 profile 配置加权
  - profile 配置改为：{ momentum: 0.3, value: 0.2, quality: 0.3, low_volatility: 0.2 }
  - 最终分数 = 0.7 * model_score + 0.3 * profile_factor_score（保持原比例）

## 5. 幸存者偏差修复 + 流动性过滤
- 修改 data 层（aifa_quant/data/ 或 features/ 的数据加载）：
  - 训练和回测使用历史成分股（如果有沪深300/中证500历史成分数据）
  - 如果没有完整成分股数据，至少在 README 中标注"当前使用的是截至运行日的成分股，存在幸存者偏差"
- 新增流动性过滤器（在 TopK 选股前执行）：
  - 最近 20 日日均成交额 < 5000 万 → 排除
  - 持仓目标金额 > 该股日均成交额 * 5% → 排除（大资金冲击约束）
  - 涨跌停/停牌 → 当日不可买入（仅在 paper_trading 和回测中体现）
- CLI `aifa backtest --min-liquidity 5000` 单位万元

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P1 — 中等投入，显著提升（P0 完成后做）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. 带约束的 QP 组合优化器（替代 TopK 等权）
- 新建 aifa_quant/strategy/optimizer.py
- 实现 MeanVarianceOptimizer：
  ```python
  max  μ^T w - λ * w^T Σ w - c * ||w - w_prev||_1
  s.t.
    Σ w_i = 1
    0 ≤ w_i ≤ 0.05           # 单票最大 5%
    Σ w_industry_j ≤ 0.25    # 单行业最大 25%
    ||w - w_prev||_1 ≤ T     # 单次换手率上限（默认 40%）
    target_vol(w) ≤ σ_target # 目标年化波动率（默认 20%）
  ```
  - μ = model_score（归一化后的预期超额）
  - Σ = Ledoit-Wolf 压缩协方差矩阵（过去 60 日收益率）
  - c = 交易成本惩罚系数（默认 0.005）
  - 求解器用 scipy.optimize 或 cvxpy
- 在 backtest/engine.py 和 paper_trading/engine.py 统一接入：
  - CLI --weighting {equal,vol_target,qp_optimize}，默认 qp_optimize
  - 回测和纸交易使用同一套组合构建逻辑
- TopK-Dropout 保留作为"候选池生成器"（选 top_k*2），最终权重由优化器决定

## 7. Purged K-Fold CV + 发布门禁
- 新建 aifa_quant/models/cv.py
- 实现 PurgedKFold(n_splits=5, embargo_pct=0.01)：
  - 训练集中剔除 label horizon 跨越验证集边界的样本
  - 支持 gap 参数（类似 sklearn TimeSeriesSplit 的 gap）
- rolling_trainer 在每个 rolling 窗口内做 purged CV，输出 mean CV score
- 新增发布门禁机制（aifa_quant/analysis/publish_gate.py）：
  - 每次训练后自动计算：RankIC 均值、ICIR、TopK 超额收益、换手率、最大回撤
  - 只有最近 N 个滚动窗口全部通过门槛，才允许推送信号到 Supabase
  - 门槛默认值：RankIC > 0.03, ICIR > 0.5, TopK 年化超额 > 5%, 月换手 < 150%
  - CLI `aifa diagnose --start xxx --end xxx` 输出完整诊断报告

## 8. Meta-Labeling 二阶模型
- 新建 aifa_quant/models/meta_model.py
- 流程：
  1. 一阶模型（LambdaRank）生成预测分数，选 top_k*2 进入候选池
  2. 二阶模型（LightGBM 分类器）判断"在这次信号上做多能否盈利"
  3. 输入特征：一阶模型分数 + 因子特征 + 市场状态特征
  4. 标签：对应时段的 triple_barrier 实际结果（+1 为正样本）
  5. 输出：P(盈利)，用于再筛选或调整仓位权重
- 推理流水线：一阶筛 top_k*2 → 二阶 P(盈利) > 0.5 的保留 → 取 top_k → 送入优化器
- CLI `aifa train --meta-label` 开关

## 9. 因子库扩展 + IC 自动筛选
- 扩展 aifa_quant/features/alpha_factors.py：
  - 从当前 ~21 个 simplified Alpha101 扩展到 50+ 个经验证有效的因子
  - 优先补充：Alpha006, Alpha012, Alpha026, Alpha033, Alpha044, Alpha054, Alpha085 等在 A 股有持续 IC 的因子
  - 补充基本面质量因子：盈利修正(SUE)、Piotroski F-Score、应计项异象
- 新建 aifa_quant/features/factor_selection.py：
  - 实现 select_by_ic(df, threshold=0.02, lookback=252)
  - 计算每个因子过去 lookback 天的 mean |IC|，低于 threshold 的自动剔除
  - 集成到训练流程：每个 rolling 窗口训练前先做因子筛选
- 将 factor_analysis.py 的结果自动反馈到训练：不通过的因子不进入模型

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P2 — 长期增强（P1 完成后做）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Regime-Conditional Ensemble
- 新建 aifa_quant/models/regime.py
- 市场状态判定（多指标）：
  - CSI300 60 日已实现波动率（高/中/低，阈值用分位数）
  - MA20/MA60 趋势（金叉/死叉/缠绕）
  - 信用利差代理变量（如有数据）
  - 综合判定：bull / bear / range 三态
- 每个 regime 训练独立子模型（LambdaRank）
- 推理时按当前 regime 选对应子模型
- backtest/engine.py 已有 regime filter 在 line 173，扩展为完整的 regime 状态机
- CLI `aifa train --regime-aware`

## 11. Walk-Forward 超参搜索
- 新建 aifa_quant/models/hyperparam_search.py
- 对关键超参（learning_rate, num_leaves, min_child_samples, top_k, pt_mult, sl_mult）做 walk-forward grid/random search
- 每个超参组合跑完整的 rolling backtest，选 Sharpe 最优的
- 输出最优超参到 configs/best_params.json，训练时自动加载

## 12. PBO 过拟合概率评估
- 在 cv.py 中实现 compute_pbo(returns_matrix)：
  - 基于 López de Prado 的 Combinatorial Symmetric Cross-Validation
  - 对所有 rolling 窗口的 OOS returns 做排列组合
  - 输出 PBO（Probability of Backtest Overfitting）和 Deflated Sharpe Ratio
- 集成到 `aifa diagnose` 命令中

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
通用要求
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 每个改动配单元测试（tests/ 目录），用 pytest 跑通
- P0 完成后跑 `aifa backtest --profile balanced --start 20230101 --end 20251231` 对比 BEFORE/AFTER
- 不要动 .env，data_store/ 不能 commit
- 完成后写 d:\kimi\aifa_quant\docs\OPTIMIZATION_NOTES.md 记录：
  - 每项改动的原理
  - 回测指标对比表（Sharpe / 年化收益 / 年化超额 / 最大回撤 / 月均换手率 / RankIC）
  - 失败/放弃的尝试及原因

## 验收标准（P0+P1 完成后）
- balanced profile 在 2023-2025 回测期：
  - Sharpe ≥ 1.5
  - 年化超额收益 ≥ 10%（相对沪深 300）
  - 最大回撤 ≤ 25%
  - 月均单边换手率 ≤ 80%
  - 平均 RankIC ≥ 0.04
- 所有单元测试通过
- 发布门禁通过（最近 4 个 rolling 窗口全部达标）
```

---

## Prompt 2：前端 UX 全面优化（从"信号展示"升级为"决策工作台"）

```
项目根目录：d:\kimi\aifa_quant\signals-web
React 19 + TypeScript + Vite + Tailwind v4 + Supabase 前端，部署在 Vercel。
后端在 d:\kimi\aifa_quant\aifa_quant（Python，CLI 工具 aifa）。
Supabase 表：daily_signals / portfolio / paper_nav / shap_summary / weekly_reports。

核心设计原则：Dashboard 的目标是让用户一眼得到可行动信息——"今天该买什么、卖什么、为什么、风险在哪"，而不是"这里有一堆图表让你自己探索"。

请按 P0/P1/P2 优先级实现，每项完成后 pnpm build 验证通过。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0 — 必做，体验收益最大
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. 引入 URL 路由（react-router-dom v7）
- 安装：pnpm add react-router-dom
- 改造 src/App.tsx：替换 useState<Page> 为 BrowserRouter + Routes
- 路由结构：
  - `/` → 重定向到 /dashboard
  - `/dashboard` → Dashboard（支持 ?profile=balanced&tab=holdings query）
  - `/stock/:symbol` → StockDetail 个股详情
  - `/explain` → ShapView 全局因子重要性
  - `/reports` → ReportsView 列表
  - `/reports/:date` → 直接展开某份报告
  - `/compare` → ProfileCompare 策略对比（新增）
- nav buttons 改为 NavLink，active 样式保留
- 浏览器前进/后退正常工作
- Vercel 配 rewrites：所有路径 → /index.html

## 2. 今日操作台（Daily Action Card）— 第一屏核心
- 新建 src/components/DailyActionCard.tsx，置于 Dashboard 最顶部
- 顶部状态条（一行）：
  - 信号日期 | 最后推送时间 | 数据新鲜度指示器（如"数据至 2026-06-27，3天前更新"）
  - 模型版本（从 signal_runs 表读，如无则显示 shap_summary 的 model_date）
  - 当前 profile 名 | 市场状态（bull/bear/range，如后端有）
- 主体内容：
  - 大字 NAV 数值 + 当日涨跌% + 累计涨跌%（从 paper_nav 算）
  - 三色操作徽章：🟢 买入 N 只 / 🔴 卖出 N 只 / ⚪ 持有 N 只
  - 操作指令表（不是简单的"持仓卡片"）：
    | 动作 | 代码/名称 | 目标权重 | 当前权重 | 模型分 | 风险标记 | 原因摘要 |
    点击行 → 跳转 /stock/:symbol
  - "下载今日委托单 CSV" 按钮：导出 symbol, action, target_weight, shares
  - "查看完整持仓 →" 链接
- 数据来源：对比 portfolio 表最新两天的持仓，diff 出 to_buy / to_sell / hold
  - 前端做两次查询 portfolio 表（latest date 和 previous date），自行 diff
  - 或后端新建 Supabase view daily_diff

## 3. 个股详情页 + 个股 SHAP 瀑布图
- 后端需要：
  1. Supabase 新建表 stock_shap (symbol, feature, shap_value, prediction_date, profile)
  2. 修改 scripts/push_to_supabase.py 增加 push_stock_shap()
  3. CLI explain 增加 --per-stock 模式输出每只股票的 SHAP
- 前端 src/components/StockDetail.tsx（路由 /stock/:symbol）：
  - 顶部卡片：股票代码 + 名称 + 当前价 + 模型评分 + 持仓状态 + 风险标记
  - 中部 SHAP 瀑布图：
    - 用 recharts ComposedChart 模拟 waterfall
    - 正贡献红色向上、负贡献绿色向下，按 |shap| 降序
    - 特征名显示中文（见第 7 项映射表）
    - 底部显示 base value → final prediction 的累积
  - 解释摘要（翻译成人话）：
    - 不要暴露原始特征名
    - 翻译为"动量强 / 波动偏高 / 估值偏低 / 盈利质量较好"等自然语言
    - 用 top 3 正贡献和 top 2 负贡献生成一句话：
      "该股入选主因：20日动量强(+0.12)、ROE 优(+0.08)；潜在风险：波动率偏高(-0.05)"
  - 底部：近 60 日收盘价折线 + ATR 止损位标注线 + RSI 指标
  - 补充信息：所属行业、日均成交额、是否涨跌停/停牌
- Dashboard 持仓行点击 → useNavigate 到 /stock/:symbol

## 4. 空状态人话化 + Onboarding
- 所有空状态（ShapView:60-66、ReportsView:173-180、Dashboard）：
  - 删掉"运行 aifa xxx"的 CLI 提示
  - 改为友好文案：「模型数据正在生成中，通常每周一更新。下次更新预计 [next_monday]」
  - 用 dayjs 计算最近的未来周一
  - 如果信号超过 7 天未更新，显示黄色警告："数据可能已过期，请联系管理员"
- 新建 src/components/Onboarding.tsx：
  - 首次访问（localStorage 标记 onboarding_done）弹出 3 步引导：
    1. "选择适合你的投资风格"（5 个 profile 卡片简介 + 风险收益特征）
    2. "查看 AI 每日推荐操作"（指向操作台）
    3. "了解模型为何这样选"（指向 SHAP / 报告）
  - 最后一步「开始使用」关闭，写入 localStorage

## 5. 报告里股票代码可点击
- 修改 ReportsView.tsx 的 Markdown 渲染逻辑：
  - 正则 `/(\d{6}\.S[HZ])/g` 匹配股票代码
  - 渲染为 `<Link to={'/stock/' + code}>{code}</Link>`
  - 加 hover 效果：蓝色下划线 + 光标变手型
  - 表格内的代码同样处理

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P1 — 体验进阶
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. 净值曲线统计面板
- Dashboard equity chart 下方增加 4 个 stat 卡片（横排 grid）：
  - 累计收益 | 年化收益 | 最大回撤 | Sharpe
  - 数据从 paper_nav 全期数据前端计算：
    ```ts
    cumReturn = (lastNav / firstNav) - 1
    annualReturn = (1 + cumReturn) ^ (252 / tradingDays) - 1
    maxDrawdown = max(1 - nav[i] / runningMax[i])
    sharpe = mean(dailyReturns) / std(dailyReturns) * sqrt(252)
    ```
  - glass-card 风格，正值绿色 / 负值红色

## 7. 因子中文名映射 + Tooltip
- 新建 src/lib/feature_names.ts：
  ```ts
  export const FEATURE_LABELS: Record<string, { cn: string; desc: string; formula?: string }> = {
    rsi_14: { cn: "14日相对强弱指数", desc: "衡量超买超卖状态", formula: "100 - 100/(1+RS)" },
    macd_signal: { cn: "MACD信号线", desc: "趋势跟踪指标的信号线" },
    pe_ttm: { cn: "市盈率(TTM)", desc: "股价/近12个月每股收益" },
    pb_ratio: { cn: "市净率", desc: "股价/每股净资产" },
    roe: { cn: "净资产收益率", desc: "净利润/股东权益" },
    volume_ratio: { cn: "成交量比", desc: "当日成交量/过去N日均量" },
    momentum_20d: { cn: "20日动量", desc: "过去20个交易日涨跌幅" },
    volatility_20d: { cn: "20日波动率", desc: "日收益率标准差×√252" },
    alpha006: { cn: "Alpha#6 量价相关", desc: "成交量与收益率负相关度" },
    // ... 覆盖所有出现在 shap_summary 和 stock_shap 中的特征
  }
  ```
- ShapView 和 StockDetail 中：特征名优先显示中文，英文原名以小字注释
- 鼠标悬停显示 tooltip：因子含义 + 计算公式

## 8. Profile 横向对比页
- 新建 src/components/ProfileCompare.tsx，路由 /compare
- 展示 5 个 profile 的并排对比：
  - 净值曲线叠加在同一张图上（不同颜色）
  - 对比表格：年化收益 / Sharpe / 最大回撤 / 月均换手率 / 当前持仓只数
  - 持仓重叠分析：Venn 或表格展示各 profile 共同持仓 / 独有持仓
  - 今日调仓差异：各 profile 的 to_buy / to_sell 数量
- 数据来源：paper_nav 表 + portfolio 表，按 profile 字段分组查询

## 9. 数据新鲜度指示器 + 错误边界
- 全局顶部 bar 或 footer 小字：
  - "数据至 YYYY-MM-DD | N 分钟前同步 | 模型 vX.X"
  - 超过 3 天未更新 → 黄色警告
  - 超过 7 天 → 红色 "数据已过期"
- 路由级 Error Boundary（src/components/ErrorBoundary.tsx）：
  - 捕获组件渲染错误，显示友好错误页
  - 提供"重试"按钮（重新 mount 组件）
  - Supabase 连接失败时显示"网络连接异常，请检查网络后重试"

## 10. 后端新增 Supabase 表支撑前端
- 在 supabase/schema.sql 新增：
  ```sql
  -- 模型运行元数据
  CREATE TABLE signal_runs (
    id bigint generated always as identity primary key,
    run_date date not null,
    model_version text,
    profile text,
    status text default 'success',  -- success / partial / failed
    metrics jsonb,  -- { rank_ic, sharpe, turnover, ... }
    created_at timestamptz default now()
  );
  
  -- 个股 SHAP
  CREATE TABLE stock_shap (
    id bigint generated always as identity primary key,
    symbol text not null,
    feature text not null,
    shap_value double precision not null,
    prediction_date date not null,
    profile text not null default 'balanced'
  );
  
  -- 净值指标快照（可选，也可前端算）
  CREATE TABLE paper_metrics (
    id bigint generated always as identity primary key,
    profile text not null,
    calc_date date not null,
    cumulative_return double precision,
    annual_return double precision,
    max_drawdown double precision,
    sharpe double precision,
    monthly_turnover double precision
  );
  ```
- 配 RLS：authenticated 可 SELECT，service_role 可 INSERT/UPDATE
- 修改 scripts/push_to_supabase.py 增加对应 push 函数

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P2 — 精致化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 11. 日期输入组件化
- 回测/报告页的日期输入：
  - 替换原始 text input 为日期选择器（pnpm add react-day-picker）
  - 显示可用数据范围（灰掉无数据的日期）
  - 支持快捷选择：最近 1 月 / 3 月 / 6 月 / 1 年 / 全部

## 12. 导出功能
- 持仓表 / 操作指令表 / 净值数据：均提供"下载 CSV"按钮
- 实现通用 exportToCSV(data, filename) 工具函数
- 操作台的"委托单"导出格式：symbol, name, action, target_weight, shares, price, amount

## 13. 移动端适配强化
- 操作台表格在移动端改为卡片列表（每只股票一张卡）
- 瀑布图在窄屏横向滚动
- nav 在移动端改为底部 tab bar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
通用要求
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 沿用现有 glass-card 风格（背景模糊 + 半透明边框）
- 主色继续用 var(--cyan)，正值绿 / 负值红 / 警告黄
- 暗色背景 #0a0e1a 不变
- 所有新页面支持移动端（max-w-[1200px] mx-auto + responsive grid）
- TypeScript 严格模式，不许 any
- pnpm build && pnpm tsc --noEmit 都要通过
- 新增的 Supabase 表要在 supabase/schema.sql 中有 DDL

## 验收标准（P0+P1 完成后）
- 刷新页面不丢状态（URL 路由生效）
- 首屏是"今日操作台"，一眼能看到"该买什么、该卖什么"
- 点击持仓行 → 个股详情 → 能看到 SHAP 瀑布图 + 人话解释
- 报告里 600519.SH 可点击跳转
- /compare 页面能看到 5 个 profile 并排净值曲线
- 首次访问有 onboarding
- 数据过期时有明显警告
- Lighthouse Performance ≥ 85
```

---

## 执行顺序建议

1. **选股 P0**（1-5 项）→ 跑回测确认不退化 → merge
2. **前端 P0**（1-5 项）→ 前端个股 SHAP 可先用 mock 数据，等选股侧 stock_shap 表有数据后切换
3. **选股 P1**（6-9 项）→ 跑回测对比指标 → merge
4. **前端 P1**（6-10 项）→ Vercel preview 验证
5. **两侧 P2** 按需推进

关键依赖：前端第 3 项（个股 SHAP）依赖后端 stock_shap 表和 push 脚本；前端第 8 项（Profile 对比）依赖 paper_nav 有多 profile 数据。
