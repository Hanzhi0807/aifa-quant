"""Automatic factor selection by rolling Information Coefficient.

Computes per-factor Spearman IC against the forward-return label over a
lookback window and drops factors whose mean |IC| falls below a threshold.
This runs inside each rolling training window so the surviving factor set
adapts to regime changes and never sees future data.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


def compute_factor_ic(
    df: pd.DataFrame,
    factor_cols: list[str],
    label_col: str = "label_return",
    method: str = "spearman",
) -> pd.DataFrame:
    """Compute per-factor mean IC, IC std, and ICIR across the sample.

    Returns a DataFrame indexed by factor with columns: mean_ic, ic_std, icir, n_periods.
    """
    rows = []
    for col in factor_cols:
        if col not in df.columns:
            continue
        ic_vals: list[float] = []
        for _, group in df.groupby("trade_date"):
            sub = group[[col, label_col]].dropna()
            if len(sub) < 5:
                continue
            try:
                if method == "spearman":
                    ic = spearmanr(sub[col], sub[label_col]).correlation
                else:
                    ic = np.corrcoef(sub[col], sub[label_col])[0, 1]
                if not pd.isna(ic):
                    ic_vals.append(float(ic))
            except Exception:
                continue
        if not ic_vals:
            rows.append({"factor": col, "mean_ic": 0.0, "ic_std": 1e-9, "icir": 0.0, "n_periods": 0})
            continue
        mean_ic = float(np.mean(ic_vals))
        ic_std = float(np.std(ic_vals)) + 1e-9
        rows.append({
            "factor": col,
            "mean_ic": mean_ic,
            "ic_std": ic_std,
            "icir": mean_ic / ic_std,
            "n_periods": len(ic_vals),
        })
    return pd.DataFrame(rows).set_index("factor")


def select_by_ic(
    df: pd.DataFrame,
    factor_cols: list[str],
    label_col: str = "label_return",
    threshold: float = 0.02,
    lookback: int | None = None,
    date_col: str = "trade_date",
    method: str = "spearman",
) -> list[str]:
    """Return factors whose mean |IC| >= threshold over the lookback window.

    Args:
        df: Full feature DataFrame.
        factor_cols: Candidate factor columns.
        label_col: Forward-return label column.
        threshold: Minimum mean |IC| to keep a factor.
        lookback: If set, only use the last `lookback` unique dates.
        date_col: Date column for lookback slicing.
        method: 'spearman' or 'pearson'.
    """
    if lookback is not None:
        dates = sorted(df[date_col].unique())
        if len(dates) > lookback:
            cutoff = dates[-lookback]
            df = df[df[date_col] >= cutoff]

    ic_df = compute_factor_ic(df, factor_cols, label_col, method)
    survivors = ic_df[ic_df["mean_ic"].abs() >= threshold].index.tolist()

    dropped = [c for c in factor_cols if c not in survivors and c in ic_df.index]
    if dropped:
        logger.info("IC筛选剔除 %d 个因子 (|IC| < %s): %s", len(dropped), threshold, dropped[:10])
    return survivors
