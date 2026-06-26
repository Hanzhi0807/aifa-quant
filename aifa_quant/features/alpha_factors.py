"""Alpha101/191 style factor library.

This module implements a representative subset of the WorldQuant Alpha101/191
factors adapted for A-share daily OHLCV data. Factors are computed per symbol
and registered in ALPHA_REGISTRY so the feature builder can iterate over them.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd


def _rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average")


def _delta(series: pd.Series, period: int) -> pd.Series:
    return series.diff(period)


def _delay(series: pd.Series, period: int) -> pd.Series:
    return series.shift(period)


def _ts_corr(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    return x.rolling(window).corr(y)


def _ts_cov(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    return x.rolling(window).cov(y)


def _ts_std(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).std()


def _ts_mean(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def _ts_sum(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).sum()


def _ts_min(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).min()


def _ts_max(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).max()


def _ts_argmax(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).apply(lambda x: np.argmax(x) + 1, raw=True)


def _ts_argmin(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).apply(lambda x: np.argmin(x) + 1, raw=True)


def _sign(series: pd.Series) -> pd.Series:
    return np.sign(series)


def _scale(series: pd.Series) -> pd.Series:
    return series / series.abs().sum()


def _signed_power(series: pd.Series, exp: float) -> pd.Series:
    return np.sign(series) * (series.abs() ** exp)


def _decay_linear(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1)
    weights = weights / weights.sum()
    return series.rolling(window).apply(lambda x: np.dot(x, weights), raw=True)


# ---------------------------------------------------------------------------
# Alpha factor implementations
# ---------------------------------------------------------------------------


def alpha002(df: pd.DataFrame) -> pd.Series:
    """(-1 * correlation(rank(delta(log(volume), 2)), rank((close - open) / open), 6))"""
    return -_ts_corr(
        _rank(_delta(np.log(df["volume"].replace(0, np.nan)), 2)),
        _rank((df["close"] - df["open"]) / df["open"].replace(0, np.nan)),
        6,
    )


def alpha003(df: pd.DataFrame) -> pd.Series:
    """(-1 * correlation(rank(open), rank(volume), 10))"""
    return -_ts_corr(_rank(df["open"]), _rank(df["volume"]), 10)


def alpha004(df: pd.DataFrame) -> pd.Series:
    """(-1 * Ts_Rank(rank(low), 9))"""
    return -_rank(df["low"]).rolling(9).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)


def alpha005(df: pd.DataFrame) -> pd.Series:
    """(rank(open - sum(vwap, 10) / 10) * (-1 * abs(rank(close - vwap))))"""
    vwap = (df["close"] * df["volume"]).cumsum() / df["volume"].replace(0, np.nan).cumsum()
    return _rank(df["open"] - _ts_mean(vwap, 10)) * (-1 * (_rank(df["close"] - vwap).abs()))


def alpha006(df: pd.DataFrame) -> pd.Series:
    """(-1 * correlation(open, volume, 10))"""
    return -_ts_corr(df["open"], df["volume"], 10)


def alpha008(df: pd.DataFrame) -> pd.Series:
    """-rank(delta(close, 5))"""
    return -_rank(_delta(df["close"], 5))


def alpha009(df: pd.DataFrame) -> pd.Series:
    """Simplified: -rank((close - open) / (high - low + 1e-6))"""
    return -_rank((df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6))


def alpha012(df: pd.DataFrame) -> pd.Series:
    """sign(delta(volume, 1)) * (-1 * delta(close, 1))"""
    return _sign(_delta(df["volume"], 1)) * (-1 * _delta(df["close"], 1))


def alpha014(df: pd.DataFrame) -> pd.Series:
    """(-1 * rank(correlation(open, volume, 10))) * rank(close - open)"""
    return -_rank(_ts_corr(df["open"], df["volume"], 10)) * _rank(df["close"] - df["open"])


def alpha015(df: pd.DataFrame) -> pd.Series:
    """-sum(rank(correlation(rank(high), rank(volume), 3)), 3)"""
    return -_ts_sum(_rank(_ts_corr(_rank(df["high"]), _rank(df["volume"]), 3)), 3)


def alpha018(df: pd.DataFrame) -> pd.Series:
    """-rank((open - ts_sum(open, 5) / 5) * (close - open))"""
    return -_rank((df["open"] - _ts_mean(df["open"], 5)) * (df["close"] - df["open"]))


def alpha020(df: pd.DataFrame) -> pd.Series:
    """-rank(open - high) * rank(open - close)"""
    return -_rank(df["open"] - df["high"]) * _rank(df["open"] - df["close"])


def alpha024(df: pd.DataFrame) -> pd.Series:
    """Simplified: rank(close - open) / (high - low + 1e-6)"""
    return _rank(df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)


def alpha032(df: pd.DataFrame) -> pd.Series:
    """scale(((close - open) / (high - low + 1e-6)) * volume)"""
    return _scale(((df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)) * df["volume"])


def alpha034(df: pd.DataFrame) -> pd.Series:
    """rank((close - ts_mean(close, 12)) / close)"""
    return _rank((df["close"] - _ts_mean(df["close"], 12)) / df["close"].replace(0, np.nan))


def alpha041(df: pd.DataFrame) -> pd.Series:
    """rank(power(high * low, 0.5) - close)"""
    return _rank(np.power(df["high"] * df["low"], 0.5) - df["close"])


def alpha043(df: pd.DataFrame) -> pd.Series:
    """Simplified: rank(close - open) / (high - low + 1e-6)"""
    return _rank(df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)


def alpha046(df: pd.DataFrame) -> pd.Series:
    """(ts_mean(close, 20) < close) ? (-1 * ts_delta(close, 2)) : 0"""
    return pd.Series(
        np.where(
            _ts_mean(df["close"], 20) < df["close"],
            -1 * _delta(df["close"], 2),
            0.0,
        ),
        index=df.index,
    )


def alpha050(df: pd.DataFrame) -> pd.Series:
    """Simplified: -ts_sum(rank(correlation(rank(high), rank(volume), 5)), 5)"""
    return -_ts_sum(_rank(_ts_corr(_rank(df["high"]), _rank(df["volume"]), 5)), 5)


def alpha054(df: pd.DataFrame) -> pd.Series:
    """(-1 * rank(stddev(abs(close - open), 10) + (close - open)) * ts_corr(close, open, 10))"""
    return -1 * _rank(_ts_std((df["close"] - df["open"]).abs(), 10) + (df["close"] - df["open"])) * _ts_corr(
        df["close"], df["open"], 10
    )


def alpha060(df: pd.DataFrame) -> pd.Series:
    """scale(((close - ts_min(low, 9)) / (ts_max(high, 9) - ts_min(low, 9) + 1e-6)) * 100)"""
    return _scale((df["close"] - _ts_min(df["low"], 9)) / (_ts_max(df["high"], 9) - _ts_min(df["low"], 9) + 1e-6))


def alpha101(df: pd.DataFrame) -> pd.Series:
    """Simplified proxy: ((close - open) / (high - low + 1e-6))"""
    return (df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)


ALPHA_REGISTRY: dict[str, tuple[str, Callable[[pd.DataFrame], pd.Series]]] = {
    "alpha002": ("momentum", alpha002),
    "alpha003": ("momentum", alpha003),
    "alpha004": ("momentum", alpha004),
    "alpha005": ("momentum", alpha005),
    "alpha006": ("momentum", alpha006),
    "alpha008": ("momentum", alpha008),
    "alpha009": ("momentum", alpha009),
    "alpha012": ("volume", alpha012),
    "alpha014": ("volume", alpha014),
    "alpha015": ("volume", alpha015),
    "alpha018": ("momentum", alpha018),
    "alpha020": ("momentum", alpha020),
    "alpha024": ("momentum", alpha024),
    "alpha032": ("volume", alpha032),
    "alpha034": ("mean_reversion", alpha034),
    "alpha041": ("mean_reversion", alpha041),
    "alpha043": ("momentum", alpha043),
    "alpha046": ("mean_reversion", alpha046),
    "alpha050": ("volume", alpha050),
    "alpha054": ("volatility", alpha054),
    "alpha060": ("momentum", alpha060),
    "alpha101": ("momentum", alpha101),
}


def compute_alpha_factors(df: pd.DataFrame, selected: list[str] | None = None) -> pd.DataFrame:
    """Compute registered alpha factors for a DataFrame of OHLCV quotes.

    Args:
        df: DataFrame with columns [symbol, open, high, low, close, volume, amount, trade_date].
        selected: Optional list of alpha names to compute. If None, compute all.

    Returns:
        DataFrame with the same index plus alpha factor columns.
    """
    df = df.copy()
    selected = selected or list(ALPHA_REGISTRY.keys())

    def _add_factor(sub_df: pd.DataFrame, factor_func: Callable, factor_name: str) -> pd.DataFrame:
        sub_df = sub_df.copy()
        sub_df[factor_name] = factor_func(sub_df)
        return sub_df

    for name in selected:
        if name not in ALPHA_REGISTRY:
            continue
        _, func = ALPHA_REGISTRY[name]
        df = df.groupby("symbol", group_keys=False).apply(
            lambda sub, f=func, n=name: _add_factor(sub, f, n)
        )
    return df


def list_alpha_factors() -> dict[str, str]:
    """Return a mapping of alpha factor name -> group."""
    return {name: group for name, (group, _) in ALPHA_REGISTRY.items()}
