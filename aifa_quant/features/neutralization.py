"""Cross-sectional factor neutralization against industry and market cap."""

import warnings
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def neutralize_cross_section(
    df: pd.DataFrame,
    factor_cols: Iterable[str],
    date_col: str = "trade_date",
    industry_col: str = "industry",
    market_cap_col: str = "market_cap",
    winsorize_sigma: float = 3.0,
) -> pd.DataFrame:
    """Neutralize factors cross-sectionally per trade date.

    For each factor, run an OLS regression ``factor ~ C(industry) + log(market_cap)``
    within each ``trade_date`` and replace the factor with the residual. The residual
    is then winsorized at ``±winsorize_sigma`` standard deviations and z-scored within
    the same cross-section.

    If ``industry_col`` is missing, only ``log(market_cap)`` is used. If
    ``market_cap_col`` is missing, OLS neutralization is skipped (with a warning) and
    only winsorization + z-scoring is applied.

    Args:
        df: DataFrame containing factor columns, ``date_col``, and optionally
            ``industry_col`` / ``market_cap_col``.
        factor_cols: Columns to neutralize.
        date_col: Date column used for cross-section grouping.
        industry_col: Industry column. Categorical dummies are created automatically.
        market_cap_col: Market-capitalization column.
        winsorize_sigma: Number of standard deviations used for winsorizing residuals.

    Returns:
        DataFrame with neutralized factor columns replaced in place.
    """
    df = df.copy()
    if df.empty:
        return df

    factor_cols = [c for c in factor_cols if c in df.columns]
    if not factor_cols:
        return df

    if date_col not in df.columns:
        raise ValueError(f"date_col '{date_col}' not found in DataFrame")

    has_market_cap = market_cap_col in df.columns
    has_industry = industry_col in df.columns

    if not has_market_cap:
        warnings.warn(
            f"{market_cap_col} not found; skipping OLS neutralization, "
            "applying winsorize + z-score only.",
            stacklevel=2,
        )
        has_industry = False
    elif not has_industry:
        warnings.warn(
            f"{industry_col} not found; neutralizing against log({market_cap_col}) only.",
            stacklevel=2,
        )

    log_mc_col = "_log_market_cap"
    if has_market_cap:
        df[market_cap_col] = pd.to_numeric(df[market_cap_col], errors="coerce")
        df[log_mc_col] = np.log(df[market_cap_col].where(df[market_cap_col] > 0))

    for col in factor_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        neutralized = pd.Series(np.nan, index=df.index, dtype=float)

        for date, group in df.groupby(date_col, sort=False):
            y = series.loc[group.index].to_numpy(dtype=float)
            mask = np.isfinite(y)
            if mask.sum() < 2:
                continue

            x_parts: list[pd.DataFrame] = []
            if has_industry:
                industry = df.loc[group.index, industry_col]
                dummies = pd.get_dummies(industry, prefix="ind", drop_first=True).astype(float)
                if not dummies.empty:
                    x_parts.append(dummies)

            if has_market_cap:
                x_parts.append(
                    pd.DataFrame({log_mc_col: df.loc[group.index, log_mc_col].to_numpy(dtype=float)}, index=group.index)
                )

            if not x_parts:
                resid = y.copy()
            else:
                X = pd.concat(x_parts, axis=1)
                valid = mask & np.all(np.isfinite(X.to_numpy(dtype=float)), axis=1)
                if valid.sum() < 2:
                    resid = y.copy()
                else:
                    xv = X.loc[group.index[valid]].to_numpy(dtype=float)
                    yv = y[valid]
                    model = LinearRegression()
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            model.fit(xv, yv)
                            preds = model.predict(X.to_numpy(dtype=float))
                    except Exception:  # pragma: no cover - defensive fallback
                        preds = np.full(len(group), np.nan, dtype=float)
                    resid = y - preds

            # Winsorize within the cross-section, then z-score.
            std = np.nanstd(resid[mask])
            if std is not None and std > 0 and np.isfinite(std):
                clipped = np.clip(resid[mask], -winsorize_sigma * std, winsorize_sigma * std)
                mean_clip = np.nanmean(clipped)
                std_clip = np.nanstd(clipped)
                if std_clip is not None and std_clip > 0 and np.isfinite(std_clip):
                    z = (clipped - mean_clip) / std_clip
                else:
                    z = np.zeros_like(clipped)
                neutralized.loc[group.index[mask]] = z
            else:
                neutralized.loc[group.index[mask]] = 0.0

        df[col] = neutralized

    if log_mc_col in df.columns:
        df = df.drop(columns=[log_mc_col])

    return df
