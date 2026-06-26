"""Weekly AI stock pick report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config.settings import Settings
from ..data.adapters import AkShareAdapter
from ..data.storage import DuckDBStore
from ..features import FeatureBuilder
from ..models import LGBRankerModel
from ..models.registry import ModelRegistry
from ..strategy import TopKDropoutStrategy


def _format_pct(value: float) -> str:
    return f"{value:+.2%}"


def generate_weekly_report(
    model_name: str = "lgb_stock_selector",
    top_k: int = 10,
    lookback_days: int = 60,
    output_dir: str | Path | None = None,
    benchmark: str = "000300.SH",
    cache_only: bool = True,
) -> Path:
    """Generate a weekly stock pick report based on the latest trained model.

    Returns:
        Path to the generated markdown report.
    """
    settings = Settings()
    store = DuckDBStore(settings)
    registry = ModelRegistry(settings)
    model_path = registry.path(model_name)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}. Run train first.")

    model = LGBRankerModel()
    model.load(str(model_path))

    # Determine latest available trade date in DuckDB
    all_quotes = store.load_daily_quotes(None, start_date="20230101", end_date=datetime.now().strftime("%Y%m%d"))
    if all_quotes.empty:
        raise RuntimeError("No daily quote data available.")
    latest_date = pd.to_datetime(all_quotes["trade_date"].max())
    start_date = (latest_date - pd.Timedelta(days=lookback_days)).strftime("%Y%m%d")
    end_date = latest_date.strftime("%Y%m%d")

    print(f"[yellow]正在为 {end_date} 生成选股报告...[/yellow]")
    builder = FeatureBuilder(settings)
    features = builder.build_features(
        start_date=start_date,
        end_date=end_date,
        label_horizon=5,
        include_fundamental=True,
        include_macro=True,
        include_sentiment=False,
        cache_only=cache_only,
        prediction_mode=True,
    )
    if features.empty:
        raise RuntimeError("No features available for prediction.")

    feature_cols = builder.feature_columns(features)
    latest_features = features[features["trade_date"] == latest_date].dropna(subset=feature_cols)
    if latest_features.empty:
        raise RuntimeError("No valid features for the latest date.")

    latest_features["pred_score"] = model.predict(latest_features[feature_cols])
    strategy = TopKDropoutStrategy(top_k=top_k, rebalance_freq=1)
    signals = strategy.generate_signals(latest_features, current_date=latest_date)
    picks = signals[signals["selected"]].sort_values("score", ascending=False).reset_index(drop=True)

    # Fetch latest close prices for context
    symbols = picks["symbol"].tolist()
    quotes = store.load_daily_quotes(symbols, start_date=end_date, end_date=end_date)
    price_map = {}
    if not quotes.empty:
        price_map = quotes.set_index("symbol")["close"].to_dict()

    # Benchmark context
    bench_df = AkShareAdapter(settings).get_index_data(benchmark, start_date=end_date, end_date=end_date)
    bench_close = bench_df["close"].iloc[-1] if not bench_df.empty else None

    output_dir = Path(output_dir or settings.data_dir_path / "reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"weekly_picks_{end_date}.md"

    lines = [
        "# AifaQuant 每周 AI 选股报告\n",
        f"**生成日期**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"**模型**: `{model_name}`\n",
        f"**预测日期**: {latest_date.strftime('%Y-%m-%d')}\n",
        f"**基准指数**: {benchmark}{f' (收盘价 {bench_close:.2f})' if bench_close else ''}\n",
        "\n## 选股结果\n\n",
        "| 排名 | 股票代码 | 预测得分 | 最新收盘价 |\n",
        "|------|----------|----------|------------|\n",
    ]
    for i, row in picks.iterrows():
        symbol = row["symbol"]
        score = row["score"]
        price = price_map.get(symbol, float("nan"))
        price_str = f"{price:.2f}" if not pd.isna(price) else "-"
        lines.append(f"| {i + 1} | {symbol} | {score:.4f} | {price_str} |\n")

    lines.extend(
        [
            "\n## 模型特征\n\n",
            "Top 10 重要特征:\n\n",
        ]
    )
    for feat, score in model.feature_importance.head(10).items():
        lines.append(f"- {feat}: {score:.0f}\n")

    lines.extend(
        [
            "\n## 说明\n\n",
            "- 本报告基于最新训练好的 LightGBM 模型，对 A 股股票进行打分并选取 TopK。\n",
            "- 预测得分越高，模型认为未来 5 个交易日上涨概率越大。\n",
            "- 仅供参考，不构成投资建议。\n",
        ]
    )

    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"[green]报告已保存: {report_path}[/green]")
    return report_path
