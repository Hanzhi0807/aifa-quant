"""Backtest performance metrics."""

import numpy as np
import pandas as pd


def compute_metrics(equity_curve: pd.DataFrame, risk_free_rate: float = 0.0) -> dict[str, float]:
    """Compute standard performance metrics from an equity curve.

    equity_curve must have a 'total_value' column and a 'trade_date' index or column.
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

    return {
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
