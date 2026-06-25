"""Grid search over strategy and model hyperparameters.

Usage:
    python scripts/parameter_search.py --start 20240101 --end 20241231 --rolling
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd  # noqa: E402

from aifa_quant.backtest import BacktestEngine, compute_metrics  # noqa: E402
from aifa_quant.config.settings import Settings  # noqa: E402
from aifa_quant.data.storage import DuckDBStore  # noqa: E402
from aifa_quant.features.builder import FeatureBuilder  # noqa: E402
from aifa_quant.models import LGBRankerModel  # noqa: E402
from aifa_quant.models.rolling_trainer import RollingTrainer  # noqa: E402
from aifa_quant.strategy import TopKDropoutStrategy  # noqa: E402


def run_single_backtest(
    features: pd.DataFrame,
    quotes: pd.DataFrame,
    top_k: int,
    freq: int,
    rolling: bool,
    initial_cash: float = 1_000_000.0,
) -> dict[str, float]:
    """Run one backtest configuration and return key metrics."""
    df = features.copy()
    feature_cols = [c for c in df.columns if c not in {"symbol", "name", "trade_date", "open", "high", "low", "close", "volume", "amount", "label_return", "label_binary"}]

    if rolling:
        trainer = RollingTrainer(train_window_days=252 * 2, min_train_samples=500, settings=Settings())
        all_dates = sorted(df["trade_date"].unique())
        rebalance_dates = all_dates[::freq]
        preds = trainer.predict_rolling(df, rebalance_dates=rebalance_dates)
        df = df.merge(preds, on=["symbol", "trade_date"], how="inner")
    else:
        model = LGBRankerModel()
        pred_df = df.dropna(subset=feature_cols).copy()
        pred_df["pred_score"] = model.predict(pred_df[feature_cols])
        df = pred_df

    strategy = TopKDropoutStrategy(top_k=top_k, rebalance_freq=freq)
    engine = BacktestEngine(initial_cash=initial_cash, rebalance_freq=freq)
    equity = engine.run(quotes, df, LGBRankerModel(), strategy)
    if equity.empty:
        return {"sharpe_ratio": -999.0, "total_return": -1.0, "max_drawdown": -1.0}

    metrics = compute_metrics(equity)
    return {
        "sharpe_ratio": metrics.get("sharpe_ratio", -999.0),
        "total_return": metrics.get("total_return", -1.0),
        "annual_return": metrics.get("annual_return", -1.0),
        "max_drawdown": metrics.get("max_drawdown", -1.0),
    }


def main(
    start: str = "20240101",
    end: str = "20241231",
    rolling: bool = True,
    output_dir: str | None = None,
) -> None:
    """Grid search over top_k, rebalance_freq and a few LightGBM params."""
    settings = Settings()
    builder = FeatureBuilder(settings)
    print("[yellow]正在构建特征...[/yellow]")
    features = builder.build_features(start_date=start, end_date=end, corr_threshold=0.95)
    if features.empty:
        print("[red]没有可用特征数据[/red]")
        sys.exit(1)

    store = DuckDBStore(settings)
    symbols = features["symbol"].unique().tolist()
    print("[yellow]正在加载行情数据...[/yellow]")
    quotes = store.load_daily_quotes(symbols, start_date=start, end_date=end)

    # Search space
    top_k_values = [3, 5, 7]
    freq_values = [3, 5, 10]

    results = []
    print("[yellow]开始参数搜索...[/yellow]")
    for top_k, freq in itertools.product(top_k_values, freq_values):
        print(f"  测试 top_k={top_k}, freq={freq}")
        metrics = run_single_backtest(features, quotes, top_k, freq, rolling=rolling)
        results.append({"top_k": top_k, "freq": freq, **metrics})

    results_df = pd.DataFrame(results)
    # Rank by Sharpe ratio
    results_df = results_df.sort_values("sharpe_ratio", ascending=False).reset_index(drop=True)

    out_dir = Path(output_dir or settings.data_dir_path / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"parameter_search_{start}_{end}.csv"
    results_df.to_csv(csv_path, index=False)
    print(f"[green]参数搜索结果已保存: {csv_path}[/green]")

    print("\n[bold]Top 5 参数组合（按夏普比率）:[/bold]")
    print(results_df.head().to_string(index=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parameter search for AifaQuant")
    parser.add_argument("--start", default="20240101", help="Backtest start date YYYYMMDD")
    parser.add_argument("--end", default="20241231", help="Backtest end date YYYYMMDD")
    parser.add_argument("--rolling", action="store_true", help="Use rolling window training")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    main(
        start=args.start,
        end=args.end,
        rolling=args.rolling,
        output_dir=args.output_dir,
    )
