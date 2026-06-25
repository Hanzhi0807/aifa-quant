"""Backtest performance metrics."""

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: pd.DataFrame,
    benchmark_curve: pd.DataFrame | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """Compute standard performance metrics from an equity curve.

    equity_curve must have a 'total_value' column and a 'trade_date' index or column.
    benchmark_curve, if provided, must have 'trade_date' and 'close' columns.
    """
    if equity_curve.empty:
        return {}

    df = equity_curve.copy().sort_values("trade_date").reset_index(drop=True)
    df["daily_return"] = df["total_value"].pct_change()
    returns = df["daily_return"].dropna()

    total_return = df["total_value"].iloc[-1] / df["total_value"].iloc[0] - 1
    n_days = len(df)
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0.0
    volatility = returns.std() * np.sqrt(252)
    sharpe = (annual_return - risk_free_rate) / volatility if volatility != 0 else 0.0

    # Max drawdown
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    max_drawdown = drawdown.min()

    # Win rate (positive daily returns)
    win_rate = (returns > 0).mean()

    metrics = {
        "total_return": total_return,
        "annual_return": annual_return,
        "annual_volatility": volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "start_value": df["total_value"].iloc[0],
        "end_value": df["total_value"].iloc[-1],
        "trading_days": n_days,
    }

    if benchmark_curve is not None and not benchmark_curve.empty:
        bench = benchmark_curve.copy().sort_values("trade_date").reset_index(drop=True)
        bench["daily_return"] = bench["close"].pct_change()
        bench = bench[["trade_date", "daily_return"]].rename(columns={"daily_return": "bench_return"})
        merged = df.merge(bench, on="trade_date", how="inner")
        if not merged.empty:
            merged["excess_return"] = merged["daily_return"] - merged["bench_return"]
            bench_total = (1 + merged["bench_return"].dropna()).prod() - 1
            metrics["benchmark_total_return"] = bench_total
            metrics["excess_return"] = total_return - bench_total
            metrics["excess_sharpe"] = (
                merged["excess_return"].mean() / merged["excess_return"].std() * np.sqrt(252)
                if merged["excess_return"].std() != 0
                else 0.0
            )
            metrics["bench_win_rate"] = (merged["excess_return"] > 0).mean()

    return metrics
