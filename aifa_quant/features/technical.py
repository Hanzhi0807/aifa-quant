"""Technical indicator factor calculations."""

import numpy as np
import pandas as pd


def compute_returns(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """Compute forward and backward returns for given windows."""
    if windows is None:
        windows = [1, 5, 10, 20]
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    for w in windows:
        df[f"return_{w}d"] = df["close"].pct_change(w)
        df[f"future_return_{w}d"] = df["close"].shift(-w) / df["close"] - 1
    return df


def compute_moving_averages(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """Compute moving average ratios and distance."""
    if windows is None:
        windows = [5, 10, 20, 60]
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    for w in windows:
        df[f"ma_{w}"] = df["close"].rolling(window=w, min_periods=1).mean()
        df[f"close_to_ma_{w}"] = df["close"] / df[f"ma_{w}"] - 1
    # Cross-sectional MA relationships
    if "ma_5" in df.columns and "ma_20" in df.columns:
        df["ma5_to_ma20"] = df["ma_5"] / df["ma_20"] - 1
    if "ma_10" in df.columns and "ma_60" in df.columns:
        df["ma10_to_ma60"] = df["ma_10"] / df["ma_60"] - 1
    return df


def compute_volatility(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """Compute rolling volatility."""
    if windows is None:
        windows = [10, 20, 60]
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    for w in windows:
        df[f"volatility_{w}d"] = df["close"].pct_change().rolling(window=w, min_periods=1).std()
    return df


def compute_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Compute Relative Strength Index."""
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100.0)
    rsi = rsi.where(avg_gain > 0, 0.0)
    df[f"rsi_{window}"] = rsi
    return df


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD indicators."""
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def compute_volume_features(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """Compute volume-based features."""
    if windows is None:
        windows = [5, 20]
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    for w in windows:
        df[f"volume_ma_{w}"] = df["volume"].rolling(window=w, min_periods=1).mean()
        df[f"volume_ratio_{w}"] = df["volume"] / df[f"volume_ma_{w}"]
    df["amount_close_ratio"] = df["amount"] / df["close"]
    if "avg_amount_20d" not in df.columns:
        df["avg_amount_20d"] = df["amount"].rolling(window=20, min_periods=1).mean() / 10_000.0
    return df


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Compute Average True Range."""
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").copy()
    else:
        df = df.copy()
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df[f"atr_{window}"] = tr.rolling(window=window, min_periods=1).mean()
    df["atr_ratio"] = df[f"atr_{window}"] / df["close"]
    return df
