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

    # For each symbol, merge asof forward fill
    merged_frames = []
    for symbol in daily["symbol"].unique():
        d_sub = daily[daily["symbol"] == symbol].sort_values("trade_date").copy()
        f_sub = financial[financial["symbol"] == symbol].sort_values("report_date").copy()

        if f_sub.empty:
            merged_frames.append(d_sub)
            continue

        # Use merge_asof to attach latest reported fundamental as of each trade_date
        d_sub = pd.merge_asof(
            d_sub,
            f_sub,
            left_on="trade_date",
            right_on="report_date",
            by="symbol",
            direction="backward",
        )
        merged_frames.append(d_sub)

    return pd.concat(merged_frames, ignore_index=True)
