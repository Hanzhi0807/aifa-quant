"""Alpha101/191 style factor library.

This module implements a representative subset of the WorldQuant Alpha101/191
factors adapted for A-share daily OHLCV data. Cross-sectional operators are
computed across all symbols on each trade date, while time-series operators are
computed independently per symbol.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd


def _as_series(values: pd.Series | np.ndarray, index: pd.Index) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.reindex(index)
    return pd.Series(values, index=index)


def _rank(df: pd.DataFrame, values: pd.Series | np.ndarray) -> pd.Series:
    """Cross-sectional percentile rank across all symbols on each trade date."""
    series = _as_series(values, df.index)
    return series.groupby(df["trade_date"]).rank(pct=True, method="average")


def _delta(df: pd.DataFrame, values: pd.Series | np.ndarray, period: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.diff(period))


def _delay(df: pd.DataFrame, values: pd.Series | np.ndarray, period: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.shift(period))


def _ts_corr(
    df: pd.DataFrame,
    x: pd.Series | np.ndarray,
    y: pd.Series | np.ndarray,
    window: int,
) -> pd.Series:
    tmp = pd.DataFrame(
        {
            "symbol": df["symbol"],
            "x": _as_series(x, df.index),
            "y": _as_series(y, df.index),
        },
        index=df.index,
    )
    result = tmp.groupby("symbol", group_keys=False).apply(lambda g: g["x"].rolling(window).corr(g["y"]))
    if isinstance(result.index, pd.MultiIndex):
        result = result.droplevel(0)
    return result.reindex(df.index)


def _ts_cov(
    df: pd.DataFrame,
    x: pd.Series | np.ndarray,
    y: pd.Series | np.ndarray,
    window: int,
) -> pd.Series:
    tmp = pd.DataFrame(
        {
            "symbol": df["symbol"],
            "x": _as_series(x, df.index),
            "y": _as_series(y, df.index),
        },
        index=df.index,
    )
    result = tmp.groupby("symbol", group_keys=False).apply(lambda g: g["x"].rolling(window).cov(g["y"]))
    return result.reindex(df.index)


def _ts_std(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.rolling(window).std())


def _ts_mean(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.rolling(window).mean())


def _ts_sum(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.rolling(window).sum())


def _ts_min(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.rolling(window).min())


def _ts_max(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(lambda x: x.rolling(window).max())


def _ts_argmax(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(
        lambda x: x.rolling(window).apply(lambda y: np.argmax(y) + 1, raw=True)
    )


def _ts_argmin(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(
        lambda x: x.rolling(window).apply(lambda y: np.argmin(y) + 1, raw=True)
    )


def _ts_rank(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    return series.groupby(df["symbol"], group_keys=False).transform(
        lambda x: x.rolling(window).apply(lambda y: pd.Series(y).rank(pct=True).iloc[-1], raw=False)
    )


def _sign(series: pd.Series) -> pd.Series:
    return np.sign(series)


def _scale(df: pd.DataFrame, values: pd.Series | np.ndarray) -> pd.Series:
    """Cross-sectional scale with zero-denominator protection."""
    series = _as_series(values, df.index)
    denom = series.abs().groupby(df["trade_date"]).transform("sum")
    return series.div(denom).where(denom.notna() & denom.ne(0), 0.0)


def _signed_power(series: pd.Series, exp: float) -> pd.Series:
    return np.sign(series) * (series.abs() ** exp)


def _decay_linear(df: pd.DataFrame, values: pd.Series | np.ndarray, window: int) -> pd.Series:
    series = _as_series(values, df.index)
    weights = np.arange(1, window + 1)
    weights = weights / weights.sum()
    return series.groupby(df["symbol"], group_keys=False).transform(
        lambda x: x.rolling(window).apply(lambda y: np.dot(y, weights), raw=True)
    )


# ---------------------------------------------------------------------------
# Alpha factor implementations
# ---------------------------------------------------------------------------


def alpha002(df: pd.DataFrame) -> pd.Series:
    """(-1 * correlation(rank(delta(log(volume), 2)), rank((close - open) / open), 6))"""
    log_volume_delta = _delta(df, np.log(df["volume"].replace(0, np.nan)), 2)
    intraday_return = (df["close"] - df["open"]) / df["open"].replace(0, np.nan)
    return -_ts_corr(
        df,
        _rank(df, log_volume_delta),
        _rank(df, intraday_return),
        6,
    )


def alpha003(df: pd.DataFrame) -> pd.Series:
    """(-1 * correlation(rank(open), rank(volume), 10))"""
    return -_ts_corr(df, _rank(df, df["open"]), _rank(df, df["volume"]), 10)


def alpha004(df: pd.DataFrame) -> pd.Series:
    """(-1 * Ts_Rank(rank(low), 9))"""
    return -_ts_rank(df, _rank(df, df["low"]), 9)


def alpha005(df: pd.DataFrame) -> pd.Series:
    """(rank(open - sum(vwap, 10) / 10) * (-1 * abs(rank(close - vwap))))"""
    if "amount" in df.columns:
        vwap = df["amount"] / df["volume"].replace(0, np.nan)
    else:
        vwap = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    vwap_ma10 = _ts_mean(df, vwap, 10)
    return -_rank(df, df["open"] - vwap_ma10) * _rank(df, (df["close"] - vwap).abs())


def alpha006(df: pd.DataFrame) -> pd.Series:
    """(-1 * correlation(open, volume, 10))"""
    return -_ts_corr(df, df["open"], df["volume"], 10)


def alpha008(df: pd.DataFrame) -> pd.Series:
    """-rank(delta(close, 5))"""
    return -_rank(df, _delta(df, df["close"], 5))


def alpha009(df: pd.DataFrame) -> pd.Series:
    """Simplified: -rank((close - open) / (high - low + 1e-6))"""
    return -_rank(df, (df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6))


def alpha012(df: pd.DataFrame) -> pd.Series:
    """sign(delta(volume, 1)) * (-1 * delta(close, 1))"""
    return _sign(_delta(df, df["volume"], 1)) * (-1 * _delta(df, df["close"], 1))


def alpha014(df: pd.DataFrame) -> pd.Series:
    """(-1 * rank(correlation(open, volume, 10))) * rank(close - open)"""
    return -_rank(df, _ts_corr(df, df["open"], df["volume"], 10)) * _rank(df, df["close"] - df["open"])


def alpha015(df: pd.DataFrame) -> pd.Series:
    """-sum(rank(correlation(rank(high), rank(volume), 3)), 3)"""
    corr = _ts_corr(df, _rank(df, df["high"]), _rank(df, df["volume"]), 3)
    return -_ts_sum(df, _rank(df, corr), 3)


def alpha018(df: pd.DataFrame) -> pd.Series:
    """-rank((open - ts_sum(open, 5) / 5) * (close - open))"""
    return -_rank(df, (df["open"] - _ts_mean(df, df["open"], 5)) * (df["close"] - df["open"]))


def alpha020(df: pd.DataFrame) -> pd.Series:
    """-rank(open - high) * rank(open - close)"""
    return -_rank(df, df["open"] - df["high"]) * _rank(df, df["open"] - df["close"])


def alpha024(df: pd.DataFrame) -> pd.Series:
    """Simplified: rank(close - open) / (high - low + 1e-6)"""
    return _rank(df, df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)


def alpha032(df: pd.DataFrame) -> pd.Series:
    """scale(((close - open) / (high - low + 1e-6)) * volume)"""
    return _scale(df, ((df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-6)) * df["volume"])


def alpha034(df: pd.DataFrame) -> pd.Series:
    """rank((close - ts_mean(close, 12)) / close)"""
    return _rank(df, (df["close"] - _ts_mean(df, df["close"], 12)) / df["close"].replace(0, np.nan))


def alpha041(df: pd.DataFrame) -> pd.Series:
    """rank(power(high * low, 0.5) - close)"""
    return _rank(df, np.power(df["high"] * df["low"], 0.5) - df["close"])


def alpha043(df: pd.DataFrame) -> pd.Series:
    """Alpha191#43: 6-day signed volume sum."""
    prev_close = _delay(df, df["close"], 1)
    signed_volume = np.where(
        df["close"] > prev_close,
        df["volume"],
        np.where(df["close"] < prev_close, -df["volume"], 0),
    )
    return _ts_sum(df, pd.Series(signed_volume, index=df.index), 6)


def alpha046(df: pd.DataFrame) -> pd.Series:
    """(ts_mean(close, 20) < close) ? (-1 * ts_delta(close, 2)) : 0"""
    return pd.Series(
        np.where(
            _ts_mean(df, df["close"], 20) < df["close"],
            -1 * _delta(df, df["close"], 2),
            0.0,
        ),
        index=df.index,
    )


def alpha050(df: pd.DataFrame) -> pd.Series:
    """Simplified: -ts_sum(rank(correlation(rank(high), rank(volume), 5)), 5)"""
    corr = _ts_corr(df, _rank(df, df["high"]), _rank(df, df["volume"]), 5)
    return -_ts_sum(df, _rank(df, corr), 5)


def alpha054(df: pd.DataFrame) -> pd.Series:
    """(-1 * rank(stddev(abs(close - open), 10) + (close - open)) * ts_corr(close, open, 10))"""
    return (
        -1
        * _rank(df, _ts_std(df, (df["close"] - df["open"]).abs(), 10) + (df["close"] - df["open"]))
        * _ts_corr(df, df["close"], df["open"], 10)
    )


def alpha060(df: pd.DataFrame) -> pd.Series:
    """scale(((close - ts_min(low, 9)) / (ts_max(high, 9) - ts_min(low, 9) + 1e-6)) * 100)"""
    return _scale(
        df,
        (df["close"] - _ts_min(df, df["low"], 9)) / (_ts_max(df, df["high"], 9) - _ts_min(df, df["low"], 9) + 1e-6),
    )


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
        DataFrame with the same rows plus alpha factor columns.
    """
    df = df.copy()
    selected = selected or list(ALPHA_REGISTRY.keys())
    df["_alpha_input_order"] = np.arange(len(df))
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["symbol", "trade_date"]).copy()

    for name in selected:
        if name not in ALPHA_REGISTRY:
            continue
        _, func = ALPHA_REGISTRY[name]
        df[name] = func(df)
    return df.sort_values("_alpha_input_order").drop(columns=["_alpha_input_order"]).reset_index(drop=True)


def list_alpha_factors() -> dict[str, str]:
    """Return a mapping of alpha factor name -> group."""
    return {name: group for name, (group, _) in ALPHA_REGISTRY.items()}
