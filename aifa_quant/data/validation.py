"""Data validation helpers for raw market data."""

from __future__ import annotations

import pandas as pd


class DataValidator:
    """Validate and clean daily quote data before feature engineering."""

    @staticmethod
    def validate_daily_quotes(df: pd.DataFrame) -> pd.DataFrame:
        """Clean daily quotes and flag obvious data quality issues.

        Checks performed:
          - Drop rows with missing symbol/trade_date/close.
          - Drop rows where open/high/low/close <= 0 or volume < 0.
          - Add ``is_suspended`` flag for volume == 0.
          - Remove duplicate (symbol, trade_date) rows, keeping the first.
        """
        if df.empty:
            return df

        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")

        required = ["symbol", "trade_date", "close"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Drop rows with invalid key fields or non-positive close
        df = df.dropna(subset=required)
        df = df[df["close"] > 0]

        for col in ["open", "high", "low"]:
            if col in df.columns:
                df = df[df[col] > 0]

        if "volume" in df.columns:
            df["is_suspended"] = df["volume"] <= 0
            df = df[df["volume"] >= 0]
        else:
            df["is_suspended"] = False

        # Remove exact duplicates by symbol + date
        df = df.drop_duplicates(subset=["symbol", "trade_date"], keep="first")
        return df.reset_index(drop=True)

    @staticmethod
    def check_price_consistency(df: pd.DataFrame) -> pd.DataFrame:
        """Flag rows where high < low or close outside [low, high]."""
        if df.empty or not {"high", "low", "close"}.issubset(df.columns):
            return df

        df = df.copy()
        df["price_inconsistent"] = (df["high"] < df["low"]) | (df["close"] < df["low"]) | (df["close"] > df["high"])
        return df
