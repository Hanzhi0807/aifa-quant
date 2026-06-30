"""Label construction for stock ranking models.

Supports three label schemes:
- excess_quantile: cost-adjusted cross-sectional excess return binned into ranks.
- triple_barrier: first-touch upper/lower barrier label mapped to 0/1/2.
- binary: original positive/negative future return label.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _compute_future_return(df: pd.DataFrame, horizon: int) -> pd.Series:
    """Return the future N-day close-to-close return per symbol."""
    return df.groupby("symbol")["close"].shift(-horizon) / df["close"] - 1


def _label_excess_quantile(
    df: pd.DataFrame,
    label_horizon: int = 5,
    drop_middle: bool = False,
    cost: float = 0.0008,
) -> pd.DataFrame:
    """Build cost-adjusted cross-sectional excess-return quantile labels.

    For each date:
      1. future_return = close(t+horizon) / close(t) - 1
      2. future_excess = future_return - median(future_return) across stocks
      3. net_excess = future_excess - cost (one-way total cost)
      4. Bin into 5 quantiles then map to label_rank 0..2:
         bottom 20% = 0, middle 60% = 1, top 20% = 2

    The ``label_rank`` column (0..2) is the LambdaRank relevance label.
    ``drop_middle`` removes the middle bucket (``label_rank == 1``), i.e. the
    middle 60% of each cross-section.

    Args:
        df: DataFrame with symbol, trade_date, close columns.
        label_horizon: Forward return horizon in trading days.
        drop_middle: If True, drop the middle quantile of each cross-section.
        cost: Total one-way transaction cost (commission + stamp_duty + slippage).

    Returns:
        DataFrame with added label columns: label_return, label_excess, label_rank.
    """
    result = df.copy()
    result["label_return"] = _compute_future_return(result, label_horizon)
    result["label_excess"] = result.groupby("trade_date")["label_return"].transform(
        lambda x: x - x.median()
    )
    result["label_excess"] = result["label_excess"] - cost

    def _bin_quantile(x: pd.Series) -> pd.Series:
        if len(x) < 5:
            return pd.Series(np.nan, index=x.index)
        # Divide into 5 quantiles (0..4) then map to label_rank 0..2:
        # bottom 20% -> 0, middle 60% -> 1, top 20% -> 2.
        # This matches LambdaRank relevance labels and lets ``drop_middle``
        # remove the middle 60% of each cross-section.
        buckets = pd.qcut(x, q=5, labels=False, duplicates="drop")
        return buckets.map({0: 0, 1: 1, 2: 1, 3: 1, 4: 2})

    result["label_rank"] = result.groupby("trade_date")["label_excess"].transform(_bin_quantile)

    if drop_middle:
        result = result[result["label_rank"] != 1].copy()
        if result.empty:
            logger.warning("drop_middle=True removed all rows; check input cross-section size")

    # Keep binary label as a convenience for binary fallback models.
    result["label_binary"] = (result["label_return"] > 0).astype(int)
    return result


def _first_touch_outcome(
    symbol_df: pd.DataFrame,
    pt_mult: float,
    sl_mult: float,
    max_holding: int,
) -> pd.Series:
    """Return triple-barrier outcome series for a single symbol's time series.

    Outcome values: +1 (upper touched first), -1 (lower touched first), 0 (neither).
    """
    n = len(symbol_df)
    outcomes = np.zeros(n, dtype=int)
    closes = symbol_df["close"].to_numpy()
    highs = symbol_df["high"].to_numpy()
    lows = symbol_df["low"].to_numpy()
    atrs = symbol_df["atr_14"].to_numpy()

    for i in range(n):
        upper = closes[i] + pt_mult * atrs[i]
        lower = closes[i] - sl_mult * atrs[i]
        outcome = 0
        for h in range(1, min(max_holding, n - i - 1) + 1):
            if highs[i + h] >= upper:
                outcome = 1
                break
            if lows[i + h] <= lower:
                outcome = -1
                break
        outcomes[i] = outcome
    return pd.Series(outcomes, index=symbol_df.index)


def _label_triple_barrier(
    df: pd.DataFrame,
    label_horizon: int = 5,
    pt_mult: float = 2.0,
    sl_mult: float = 1.0,
    max_holding: int = 10,
) -> pd.DataFrame:
    """Build triple-barrier labels based on first touch of ATR14 bands.

    For each row, the entry is the close of that day. Upper and lower bounds are
    close +/- pt_mult/sl_mult * ATR14. The outcome is the first touch within the
    next ``max_holding`` days: +1 for upper (take-profit), -1 for lower (stop-loss),
    0 if neither is touched. The outcome is then mapped to LambdaRank relevance
    labels: +1 -> 2, 0 -> 1, -1 -> 0.

    Requires ``atr_14`` column; if missing, falls back to excess_quantile.
    """
    result = df.copy()
    result["label_return"] = _compute_future_return(result, label_horizon)

    if "atr_14" not in result.columns:
        warnings.warn("atr_14 missing; falling back to excess_quantile labels", UserWarning, stacklevel=2)
        return _label_excess_quantile(result, label_horizon=label_horizon)

    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    outcomes = result.groupby("symbol", group_keys=False).apply(
        lambda x: _first_touch_outcome(x, pt_mult, sl_mult, max_holding)
    )
    result["label_outcome"] = outcomes.reindex(result.index).fillna(0).astype(int)
    result["label_rank"] = result["label_outcome"] + 1
    result["label_binary"] = (result["label_return"] > 0).astype(int)
    return result


def _label_binary(df: pd.DataFrame, label_horizon: int = 5) -> pd.DataFrame:
    """Preserve the original binary label behavior."""
    result = df.copy()
    result["label_return"] = _compute_future_return(result, label_horizon)
    result["label_binary"] = (result["label_return"] > 0).astype(int)
    result["label_rank"] = result["label_binary"]
    return result


def compute_labels(
    df: pd.DataFrame,
    label_type: str = "excess_quantile",
    label_horizon: int = 5,
    drop_middle: bool = False,
    pt_mult: float = 2.0,
    sl_mult: float = 1.0,
    max_holding: int = 10,
    cost: float = 0.0008,
) -> pd.DataFrame:
    """Build labels for the requested scheme.

    Args:
        df: Feature DataFrame with at least symbol, trade_date, close.
        label_type: One of 'excess_quantile' (default), 'triple_barrier', 'binary'.
        label_horizon: Forward return horizon in trading days.
        drop_middle: For excess_quantile only; drop middle quantile of cross-section.
        pt_mult: For triple_barrier only; profit-taking ATR multiplier.
        sl_mult: For triple_barrier only; stop-loss ATR multiplier.
        max_holding: For triple_barrier only; maximum holding period in days.
        cost: Total one-way transaction cost for excess_quantile.

    Returns:
        DataFrame with label column(s) attached.
    """
    if label_type == "excess_quantile":
        return _label_excess_quantile(df, label_horizon, drop_middle, cost)
    if label_type == "triple_barrier":
        return _label_triple_barrier(df, label_horizon, pt_mult, sl_mult, max_holding)
    if label_type == "binary":
        return _label_binary(df, label_horizon)
    raise ValueError(f"Unknown label_type: {label_type}. Choose from excess_quantile, triple_barrier, binary")


# Backward-compatible alias.
build_labels = compute_labels
