"""Backtest performance metrics."""

import numpy as np
import pandas as pd


def compute_rankic(
    features: pd.DataFrame,
    pred_col: str = "pred_score",
    return_col: str = "label_return",
) -> dict[str, float]:
    """Compute mean RankIC, ICIR and related statistics.

    For each trade_date, compute the Spearman correlation between the model
    score (``pred_col``) and the forward return (``return_col``). Returns the
    mean, standard deviation and annualized ICIR.
    """
    if features.empty or pred_col not in features.columns or return_col not in features.columns:
        return {"mean_rankic": 0.0, "rankic_std": 0.0, "icir": 0.0, "rankic_win_rate": 0.0}

    df = features[["trade_date", pred_col, return_col]].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.dropna()

    def _spearman(g: pd.DataFrame) -> float:
        if len(g) < 5:
            return np.nan
        return g[pred_col].corr(g[return_col], method="spearman")

    ic_series = df.groupby("trade_date").apply(_spearman, include_groups=False)
    ic_series = ic_series.dropna()
    if ic_series.empty:
        return {"mean_rankic": 0.0, "rankic_std": 0.0, "icir": 0.0, "rankic_win_rate": 0.0}

    mean_ic = float(ic_series.mean())
    std_ic = float(ic_series.std())
    icir = mean_ic / std_ic * np.sqrt(len(ic_series)) if std_ic != 0 else 0.0
    win_rate = float((ic_series > 0).mean())
    return {
        "mean_rankic": mean_ic,
        "rankic_std": std_ic,
        "icir": icir,
        "rankic_win_rate": win_rate,
    }


def compute_turnover(
    trades: list,
    equity_curve: pd.DataFrame,
) -> dict[str, float]:
    """Compute monthly single-side turnover from trade history.

    Single-side monthly turnover is defined as total buy amount in a month
    divided by the average portfolio NAV in that month, averaged across all
    months with data.
    """
    if not trades or equity_curve.empty:
        return {"monthly_turnover": 0.0, "avg_annual_turnover": 0.0}

    trades_df = pd.DataFrame(
        [
            {
                "trade_date": pd.to_datetime(t.trade_date),
                "action": t.action,
                "amount": float(t.amount),
            }
            for t in trades
        ]
    )
    equity = equity_curve.copy()
    equity["trade_date"] = pd.to_datetime(equity["trade_date"])
    equity = equity.set_index("trade_date").sort_index()

    buys = trades_df[trades_df["action"] == "BUY"].copy()
    buys = buys.set_index("trade_date").resample("ME")["amount"].sum()
    nav = equity["total_value"].resample("ME").mean()

    common = nav.index.intersection(buys.index)
    if common.empty:
        return {"monthly_turnover": 0.0, "avg_annual_turnover": 0.0}

    monthly = (buys.reindex(common) / nav.reindex(common)).dropna()
    avg_monthly = float(monthly.mean())
    annual = avg_monthly * 12
    return {"monthly_turnover": avg_monthly, "avg_annual_turnover": annual}


def compute_metrics(
    equity_curve: pd.DataFrame,
    benchmark_curve: pd.DataFrame | None = None,
    risk_free_rate: float = 0.0,
    trades: list | None = None,
    features: pd.DataFrame | None = None,
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
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days >= 5 else 0.0

    # Standard excess-return Sharpe ratio
    excess_returns = returns - risk_free_rate / 252
    volatility = excess_returns.std() * np.sqrt(252)
    if len(excess_returns) < 30 or excess_returns.std() == 0:
        sharpe = 0.0
    else:
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

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

    if features is not None and not features.empty:
        metrics.update(compute_rankic(features))
    if trades is not None:
        metrics.update(compute_turnover(trades, equity_curve))

    return metrics
