"""Factor effectiveness analysis: IC, RankIC, ICIR, quantile portfolios, decay."""

from __future__ import annotations

from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ICMethod = Literal["pearson", "spearman"]


def _forward_returns(
    df: pd.DataFrame,
    horizons: list[int],
    price_col: str = "close",
) -> pd.DataFrame:
    """Add forward return columns for multiple horizons."""
    df = df.copy()
    df = df.sort_values(["symbol", "trade_date"])
    for h in horizons:
        df[f"future_return_{h}d"] = (
            df.groupby("symbol")[price_col].shift(-h) / df[price_col] - 1
        )
    return df


def compute_ic(
    df: pd.DataFrame,
    feature_col: str,
    forward_return_col: str = "label_return",
    method: ICMethod = "spearman",
    min_obs: int = 10,
) -> pd.Series:
    """Compute cross-sectional IC time series for a single factor.

    Args:
        df: DataFrame with trade_date, symbol, feature and forward return columns.
        feature_col: Factor column name.
        forward_return_col: Column holding future returns to predict.
        method: 'pearson' for IC, 'spearman' for RankIC.
        min_obs: Minimum observations per date to compute correlation.

    Returns:
        Series indexed by trade_date with IC values.
    """
    df = df.dropna(subset=[feature_col, forward_return_col])
    if df.empty:
        return pd.Series(dtype=float)

    def _corr(group: pd.DataFrame) -> float | None:
        if len(group) < min_obs:
            return None
        return group[feature_col].corr(group[forward_return_col], method=method)

    ic = df.groupby("trade_date").apply(_corr, include_groups=False)
    return ic.dropna()


def compute_ic_summary(
    df: pd.DataFrame,
    feature_col: str,
    forward_return_col: str = "label_return",
    method: ICMethod = "spearman",
    min_obs: int = 10,
) -> dict[str, float]:
    """Return IC/RankIC summary statistics for a factor."""
    ic = compute_ic(df, feature_col, forward_return_col, method, min_obs)
    if ic.empty:
        return {}

    mean_ic = ic.mean()
    std_ic = ic.std()
    ir = mean_ic / std_ic if std_ic != 0 else 0.0
    return {
        "feature": feature_col,
        "method": method,
        "mean_ic": mean_ic,
        "std_ic": std_ic,
        "icir": ir,
        "win_rate": (ic > 0).mean(),
        "t_stat": mean_ic / (std_ic / np.sqrt(len(ic))) if std_ic != 0 else 0.0,
        "n_periods": len(ic),
    }


def compute_quantile_returns(
    df: pd.DataFrame,
    feature_col: str,
    forward_return_col: str = "label_return",
    n_quantiles: int = 10,
    min_obs: int = 20,
) -> pd.DataFrame:
    """Compute equal-weight mean forward return per quantile per date.

    Returns:
        DataFrame with columns [trade_date, quantile, mean_return].
    """
    df = df.dropna(subset=[feature_col, forward_return_col]).copy()
    if df.empty:
        return pd.DataFrame(columns=["trade_date", "quantile", "mean_return"])

    def _quantile_return(group: pd.DataFrame) -> pd.DataFrame:
        if len(group) < min_obs:
            return pd.DataFrame(columns=["trade_date", "quantile", "mean_return"])
        group["quantile"] = pd.qcut(
            group[feature_col], q=n_quantiles, labels=False, duplicates="drop"
        )
        return (
            group.groupby("quantile", as_index=False)[forward_return_col]
            .mean()
            .rename(columns={forward_return_col: "mean_return"})
            .assign(trade_date=group["trade_date"].iloc[0])
        )

    frames = []
    for _, group in df.groupby("trade_date"):
        frames.append(_quantile_return(group))
    if not frames:
        return pd.DataFrame(columns=["trade_date", "quantile", "mean_return"])
    return pd.concat(frames, ignore_index=True)


def compute_factor_decay(
    df: pd.DataFrame,
    feature_col: str,
    horizons: list[int] | None = None,
    price_col: str = "close",
    method: ICMethod = "spearman",
    min_obs: int = 10,
) -> pd.DataFrame:
    """Compute IC at multiple forward horizons to show factor decay."""
    horizons = horizons or [1, 5, 10, 20, 60]
    df = _forward_returns(df, horizons, price_col)

    records = []
    for h in horizons:
        col = f"future_return_{h}d"
        ic = compute_ic(df, feature_col, col, method, min_obs)
        if not ic.empty:
            records.append(
                {
                    "horizon": h,
                    "mean_ic": ic.mean(),
                    "icir": ic.mean() / ic.std() if ic.std() != 0 else 0.0,
                    "win_rate": (ic > 0).mean(),
                    "n_periods": len(ic),
                }
            )
    return pd.DataFrame(records)


def plot_ic_distribution(
    ic: pd.Series,
    title: str = "IC Distribution",
    figsize: tuple[int, int] = (8, 4),
    output_path: str | None = None,
) -> None:
    """Plot histogram of IC values."""
    plt.figure(figsize=figsize)
    plt.hist(ic.dropna(), bins=30, edgecolor="black")
    plt.axvline(ic.mean(), color="red", linestyle="--", label=f"Mean={ic.mean():.3f}")
    plt.title(title)
    plt.xlabel("IC")
    plt.ylabel("Frequency")
    plt.legend()
    plt.grid(True, alpha=0.3)
    if output_path:
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def plot_quantile_returns(
    quantile_df: pd.DataFrame,
    title: str = "Quantile Portfolio Mean Returns",
    figsize: tuple[int, int] = (10, 5),
    output_path: str | None = None,
) -> None:
    """Plot average forward return by quantile."""
    summary = quantile_df.groupby("quantile")["mean_return"].mean().reset_index()
    plt.figure(figsize=figsize)
    plt.bar(summary["quantile"].astype(str), summary["mean_return"])
    plt.title(title)
    plt.xlabel("Quantile (0=lowest factor score)")
    plt.ylabel("Mean Forward Return")
    plt.grid(True, alpha=0.3)
    if output_path:
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
    else:
        plt.show()
