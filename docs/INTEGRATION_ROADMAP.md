# 外部能力接入路线图

> 说明 AifaQuant 如何以“核心层稳定 + 插件化拼装”的方式，吸收其他量化项目、工具库和数据源的长处。

---

## 1. 核心设计原则

1. **核心层保持稳定**
   - 数据存储 schema（DuckDB 表结构）
   - 数据接口：`aifa_quant.core.interfaces.BaseDataSource`
   - 模型接口：`aifa_quant.models.base.BaseModel`
   - 策略接口：`aifa_quant.strategy.base.BaseStrategy`
   - 回测接口：`aifa_quant.backtest.engine.BacktestEngine`
   - 执行接口：`aifa_quant.core.interfaces.BaseBroker`

   具体定义见：
   - `aifa_quant/core/interfaces.py`
   - `aifa_quant/models/base.py`
   - `aifa_quant/strategy/base.py`

2. **外部长处通过适配器/插件接入**
   - 不直接依赖外部库
   - 通过 `try...except ImportError` 做可选依赖
   - 通过配置文件或注册表选择实现

3. **每个集成必须提供**
   - 适配代码（`contrib/` 或 `plugins/` 下）
   - 使用示例
   - 单元测试（如果可能）

---

## 2. 计划接入的外部能力

### 2.1 数据源（Data Sources）

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **AkShare** | 免费 A 股/基金/宏观数据，接口丰富 | 新增 `AkShareAdapter`，实现 `get_daily_data`、`get_index_data` | 高 | 低 |
| **Tushare** | 高质量财务数据、分钟线、龙虎榜 | 新增 `TushareAdapter`，复用现有存储 schema | 高 | 低 |
| **Baostock** | 免费复权数据、季频财务数据 | 新增 `BaostockAdapter` | 中 | 低 |
| **JoinQuant / RiceQuant** | 更长历史、已清洗因子 | 通过 API 或导出 CSV 导入 DuckDB | 中 | 中 |
| **AbuQuant 数据模块** | 已有数据解析逻辑 | 抽取 Abu 中数据清洗/标准化逻辑，作为可选适配器 | 低 | 中 |

**接口要求**：所有数据源适配器必须实现以下方法：

```python
class BaseDataSource(ABC):
    @abstractmethod
    def get_daily_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_index_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        ...
```

---

### 2.2 因子工程（Factor Engineering）

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **Qlib Alpha158 / Alpha360** | 经典因子库，已被验证 | 新增 `qlib_factors.py`，生成后写入 DuckDB `features` 表 | 高 | 中 |
| **pandas-ta / ta-lib** | 大量技术指标 | 扩展 `features/technical.py` 或新增 `features/ta_lib.py` | 高 | 低 |
| **Alphalens** | 因子分析（IC、分位数收益、换手率） | 新增 `analysis/factor_analysis.py`，调用 Alphalens API | 高 | 中 |
| **AbuQuant 因子模块** | 已有特征组合经验 | 抽取 Abu 的卖出/UMP 特征思路，作为可选因子 | 中 | 中 |

**设计建议**：
- 每个外部因子集封装成一个函数，输入 `daily_df`，输出带新列的 DataFrame。
- 通过 `FeatureBuilder` 注册机制按需调用：

```python
feature_modules = {
    "technical": build_technical_features,
    "qlib_alpha158": build_qlib_alpha158,
    "abuq_ump": build_abuq_ump_features,
}
```

---

### 2.3 模型（Models）

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **Qlib 模型 Zoo** | GBDT、TabNet、Transformer、ALSTM | 实现 `QlibModelAdapter` 继承 `BaseModel` | 中 | 中 |
| **mlfinlab / AFML** | 金融机器学习最佳实践 | 引入样本权重、Purged K-Fold、元标签（meta-labeling） | 中 | 高 |
| **scikit-learn** | 逻辑回归、随机森林、SVM | 新增 `SklearnModelWrapper` | 低 | 低 |
| **XGBoost** | 与 LightGBM 互补 | 新增 `XGBRankerModel` | 低 | 低 |

**模型接口**：

```python
class BaseModel(ABC):
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, feature_names: list[str]) -> None: ...
    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...
    @abstractmethod
    def save(self, path: str) -> None: ...
    @abstractmethod
    def load(self, path: str) -> None: ...
```

---

### 2.4 回测引擎（Backtest）

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **Backtrader** | 成熟事件驱动引擎，支持多品种/期货/期权 | 新增 `BacktraderAdapter`，把 AifaQuant 的策略包装成 Backtrader Strategy | 中 | 中 |
| **Zipline** | pipeline 式量化研究 | 作为可选回测引擎，复用数据层 | 低 | 高 |
| **AbuQuant 回测模块** | A 股规则已有部分实现 | 对比 Abu 的卖出/风控逻辑，反哺 `backtest/engine.py` | 低 | 中 |

**注意**：AifaQuant 自研 A 股回测引擎仍是默认，Backtrader 仅作为复杂场景的可选扩展。

---

### 2.5 绩效分析（Analytics）

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **Pyfolio / Empyrical** | 专业收益/风险指标、回撤分析 | 新增 `analytics/pyfolio_reporter.py`，把权益曲线转成 Pyfolio 格式 | 中 | 中 |
| **Alphalens** | 因子层面的绩效归因 | 新增 `analytics/factor_tearsheet.py` | 中 | 中 |
| **matplotlib / plotly** | 可视化 | 扩展 `reports/` 目录，输出 HTML/PDF 报告 | 高 | 低 |

---

### 2.6 实盘/模拟交易（Execution）

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **QMT** | 国内主流量化交易终端 | 新增 `execution/qmt_broker.py` 实现 `BaseBroker` | 高 | 中 |
| **easytrader** | 券商客户端自动化 | 新增 `execution/easytrader_broker.py` | 中 | 中 |
| **Ptrade** | 恒生量化平台 | 新增 `execution/ptrade_broker.py` | 低 | 高 |

**执行接口**：

```python
class BaseBroker(ABC):
    @abstractmethod
    def query_positions(self) -> dict[str, int]: ...

    @abstractmethod
    def submit_order(self, symbol: str, side: str, quantity: int, order_type: str = "market") -> dict: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...
```

---

### 2.7 参数优化与自动化

| 来源 | 长处 | 接入方式 | 优先级 | 难度 |
|---|---|---|---|---|
| **Optuna** | 贝叶斯超参优化 | 新增 `optimization/optuna_search.py`，优化 top_k/freq/模型参数 | 中 | 中 |
| **Ray Tune** | 分布式超参搜索 | 在大数据集或复杂模型时使用 | 低 | 高 |
| **Weights & Biases / MLflow** | 实验追踪 | 记录每次回测/训练的参数和指标 | 中 | 低 |

---

## 3. 推荐目录结构

```
aifa_quant/
├── core/                       # 核心接口与配置
│   ├── interfaces.py           # BaseModel, BaseStrategy, BaseBroker, BaseDataSource
│   └── settings.py
├── plugins/                    # 外部能力插件
│   ├── datasources/
│   │   ├── akshare_adapter.py
│   │   ├── tushare_adapter.py
│   │   └── baostock_adapter.py
│   ├── factors/
│   │   ├── qlib_alpha158.py
│   │   └── abuq_ump.py
│   ├── models/
│   │   ├── xgb_ranker.py
│   │   └── sklearn_wrapper.py
│   ├── backtest/
│   │   └── backtrader_adapter.py
│   └── execution/
│       ├── qmt_broker.py
│       └── easytrader_broker.py
├── contrib/                    # 社区贡献示例
│   └── example_strategy.py
└── docs/
    └── INTEGRATION_ROADMAP.md  # 本文档
```

---

## 4. 接入步骤模板

以接入 **AkShare** 为例：

1. **新增可选依赖**
   ```toml
   [project.optional-dependencies]
   akshare = ["akshare>=1.12.0"]
   ```

2. **实现适配器**
   ```python
   # plugins/datasources/akshare_adapter.py
   try:
       import akshare as ak
   except ImportError:
       ak = None

   class AkShareAdapter(BaseDataSource):
       def get_daily_data(self, symbol, start_date, end_date):
           ...
   ```

3. **注册到数据源工厂**
   ```python
   # data/adapters/factory.py
   SOURCES = {
       "ifind": StockMCPAdapter,
       "akshare": AkShareAdapter,
       "tushare": TushareAdapter,
   }
   ```

4. **配置切换**
   ```env
   DATA_SOURCE=akshare
   ```

5. **添加测试**
   - mock AkShare 返回，验证清洗后的 DataFrame 列名与 schema 一致。

6. **更新文档**
   - 在本文档对应表格中标记状态为 ✅ 并补充使用示例。

---

## 5. 优先级排序（建议执行顺序）

### 第一阶段：夯实数据与因子
1. AkShare / Tushare 数据源适配
2. pandas-ta / ta-lib 技术指标扩展
3. Alphalens 因子分析

### 第二阶段：模型与回测
4. XGBoost / sklearn 模型适配
5. Backtrader 回测引擎适配
6. mlfinlab 样本权重与 Purged CV

### 第三阶段：实盘与优化
7. QMT / easytrader 执行适配
8. Optuna 参数优化
9. W&B / MLflow 实验追踪

---

## 6. 注意事项

- **不要破坏核心接口**：任何插件修改都必须兼容 `BaseModel` / `BaseStrategy` / `BaseBroker`。
- **可选依赖**：核心 `requirements.txt` 保持精简，外部能力通过 `pip install aifa-quant[akshare,qlib]` 安装。
- **单元测试**：每个插件至少有一个 mock 测试，避免因为外部 API 不稳定导致 CI 失败。
- **文档同步**：每接入一个外部能力，同步更新 `HANDOFF.md`、本文件和 `CHANGELOG.md`。

---

## 7. 状态追踪

| 外部能力 | 状态 | 负责人 | 备注 |
|---|---|---|---|
| AkShare 数据源 | ⏳ 待接入 | - | 优先级高 |
| Tushare 数据源 | ⏳ 待接入 | - | 优先级高 |
| Qlib Alpha158 | ⏳ 待接入 | - | 优先级高 |
| Alphalens 因子分析 | ⏳ 待接入 | - | 优先级高 |
| XGBoost 模型 | ⏳ 待接入 | - | 优先级低 |
| Backtrader 回测 | ⏳ 待接入 | - | 优先级中 |
| QMT 实盘 | ⏳ 待接入 | - | 优先级高（实盘阶段） |
| Optuna 优化 | ⏳ 待接入 | - | 优先级中 |
