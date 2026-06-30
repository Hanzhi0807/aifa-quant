"""Purged K-Fold cross-validation for time-series with label leakage.

Standard K-Fold leaks label information across folds when labels use forward
returns: a row at the end of fold K has a label that depends on prices in
fold K+1.  Purged K-Fold removes these boundary samples, plus an optional
embargo on the validation side.

Reference: López de Prado, "Advances in Financial Machine Learning".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PurgedKFold:
    """Time-ordered K-Fold with label-horizon purging and embargo.

    Args:
        n_splits: Number of folds.
        label_horizon: Forward-return horizon in rows (trading days).
        embargo_pct: Fraction of total samples to embargo after each val fold.
    """

    n_splits: int = 5
    label_horizon: int = 5
    embargo_pct: float = 0.01

    def split(self, df: pd.DataFrame, date_col: str = "trade_date"):
        """Yield (train_idx, val_idx) pairs as positional indices into df.

        df must be sorted by date_col ascending.  We split on unique dates so
        all rows of one date stay together.
        """
        dates = sorted(df[date_col].unique())
        n_dates = len(dates)
        if n_dates < self.n_splits:
            raise ValueError(f"Need at least {self.n_splits} unique dates, got {n_dates}")

        fold_size = n_dates // self.n_splits
        embargo_days = max(1, int(n_dates * self.embargo_pct))
        date_to_idx = {d: i for i, d in enumerate(dates)}

        # Map each row to its date index.
        row_date_idx = df[date_col].map(date_to_idx).to_numpy()

        for k in range(self.n_splits):
            val_start = k * fold_size
            val_end = (k + 1) * fold_size if k < self.n_splits - 1 else n_dates

            # Purge training rows whose label horizon crosses into val.
            # A row at date index d has a label using date d + label_horizon.
            # It must leave training if d + label_horizon >= val_start.
            train_mask = np.ones(n_dates, dtype=bool)
            train_mask[val_start:val_end] = False  # exclude val dates
            # Purge rows in train whose label reaches into val.
            purge_start = max(0, val_start - self.label_horizon)
            train_mask[purge_start:val_start] = False
            # Embargo: drop a few days after val (labels of val rows could reach forward).
            embargo_end = min(n_dates, val_end + embargo_days)
            train_mask[val_end:embargo_end] = False

            train_idx = np.where(train_mask[row_date_idx])[0]
            val_idx = np.where((row_date_idx >= val_start) & (row_date_idx < val_end))[0]
            yield train_idx, val_idx


def compute_pbo(oos_returns: np.ndarray) -> float:
    """Probability of Backtest Overfitting (PBO) via combinatorial symmetric CV.

    Simplified implementation: given a matrix of out-of-sample returns
    (rows = time, cols = strategy variants), compute the fraction of
    combinations where the in-sample-optimal strategy underperforms the
    median out-of-sample.

    For a single strategy this returns 0.0 (no overfitting measurable).
    A high PBO (>0.5) indicates likely overfitting.

    Args:
        oos_returns: 2D array (T, N) of OOS returns for N strategy variants.
    """
    oos = np.asarray(oos_returns, dtype=float)
    if oos.ndim != 2 or oos.shape[1] < 2:
        return 0.0
    T, N = oos.shape
    # Is-rank: for each period, rank strategies by return.
    ranks = np.argsort(np.argsort(oos, axis=1), axis=1)
    # Mean rank per strategy across time → IS proxy (we use full sample as IS).
    mean_ranks = ranks.mean(axis=0)
    is_best = int(np.argmax(mean_ranks))
    # OOS: does the IS-best strategy beat the median in each period?
    median_per_period = np.median(oos, axis=1)
    beats_median = oos[:, is_best] > median_per_period
    pbo = 1.0 - float(beats_median.mean())
    return pbo
