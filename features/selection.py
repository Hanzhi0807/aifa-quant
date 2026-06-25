"""Feature selection utilities to reduce overfitting."""

import numpy as np
import pandas as pd


def drop_highly_correlated(
    df: pd.DataFrame,
    feature_cols: list[str],
    threshold: float = 0.95,
) -> list[str]:
    """Drop one feature from each pair with absolute correlation >= threshold.

    Keeps the first feature in original order to maintain stability.
    """
    cols = [c for c in feature_cols if c in df.columns]
    if len(cols) < 2:
        return cols

    corr = df[cols].corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = set()
    for i, col in enumerate(cols):
        if col in to_drop:
            continue
        for j in range(i + 1, len(cols)):
            other = cols[j]
            if other in to_drop:
                continue
            if upper.loc[col, other] >= threshold:
                to_drop.add(other)
    return [c for c in cols if c not in to_drop]


def select_by_importance(
    importance: pd.Series,
    threshold_ratio: float = 0.01,
    top_k: int | None = None,
) -> list[str]:
    """Select features whose importance >= max_importance * threshold_ratio.

    Args:
        importance: Feature importance series sorted descending.
        threshold_ratio: Minimum importance relative to the most important feature.
        top_k: If provided, also limit to top_k features.

    Returns:
        List of selected feature names.
    """
    if importance.empty:
        return []
    max_imp = importance.max()
    min_imp = max_imp * threshold_ratio
    selected = importance[importance >= min_imp].index.tolist()
    if top_k is not None:
        selected = selected[:top_k]
    return selected
