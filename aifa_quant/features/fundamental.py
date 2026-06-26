"""Fundamental / valuation factor calculations."""

import pandas as pd


def merge_fundamental_to_daily(daily_df: pd.DataFrame, financial_df: pd.DataFrame) -> pd.DataFrame:
    """Merge quarterly/annual financial ratios into daily data using forward fill.

    Args:
        daily_df: DataFrame with columns [symbol, trade_date, ...]
        financial_df: DataFrame with columns [symbol, report_date, pe_lyr, pb, roe_ttm, ...]
    """
    if financial_df.empty:
        return daily_df

    daily = daily_df.copy()
    financial = financial_df.copy()

    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    financial["report_date"] = pd.to_datetime(financial["report_date"])

    # Keep only useful columns to avoid bringing metadata (e.g. created_at) into features.
    useful_cols = [
        "symbol",
        "report_date",
        "pe_lyr",
        "pb",
        "pb_mrq",
        "roe_deducted",
        "roe_ttm",
        "roe_weighted",
        "roe_diluted",
    ]
    financial = financial[[c for c in useful_cols if c in financial.columns]].copy()

    # Single merge_asof by symbol is equivalent to the previous per-symbol loop
    # but avoids O(n_symbols) DataFrame slices and is significantly faster.
    merged = pd.merge_asof(
        daily.sort_values("trade_date"),
        financial.sort_values("report_date"),
        left_on="trade_date",
        right_on="report_date",
        by="symbol",
        direction="backward",
    )
    return merged.drop(columns=["report_date"], errors="ignore")
