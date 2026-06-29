"""Fundamental / valuation factor calculations."""

import pandas as pd

FUNDAMENTAL_FALLBACK_DELAY_DAYS = 90


def merge_fundamental_to_daily(df_daily: pd.DataFrame, df_financial: pd.DataFrame) -> pd.DataFrame:
    """Merge financial ratios using the date when data was publicly available.

    If an announcement date is present, it is used. Otherwise report_date is
    delayed by a conservative 90 days to avoid using unreleased filings.
    """
    if df_financial.empty:
        return df_daily

    daily = df_daily.copy()
    financial = df_financial.copy()

    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    financial["report_date"] = pd.to_datetime(financial["report_date"])
    if "ann_date" in financial.columns:
        financial["ann_date"] = pd.to_datetime(financial["ann_date"], errors="coerce")
        financial["_available_date"] = financial["ann_date"].fillna(
            financial["report_date"] + pd.Timedelta(days=FUNDAMENTAL_FALLBACK_DELAY_DAYS)
        )
    else:
        financial["_available_date"] = financial["report_date"] + pd.Timedelta(days=FUNDAMENTAL_FALLBACK_DELAY_DAYS)

    useful_cols = [
        "symbol",
        "report_date",
        "ann_date",
        "_available_date",
        "pe_lyr",
        "pb",
        "pb_mrq",
        "roe_deducted",
        "roe_ttm",
        "roe_weighted",
        "roe_diluted",
    ]
    financial = financial[[c for c in useful_cols if c in financial.columns]].copy()
    financial = financial.dropna(subset=["symbol", "_available_date"])

    merged_frames = []
    for symbol, daily_part in daily.groupby("symbol", sort=False):
        fin_part = financial[financial["symbol"] == symbol].sort_values("_available_date")
        if fin_part.empty:
            merged_frames.append(daily_part.copy())
            continue
        merged_frames.append(
            pd.merge_asof(
                daily_part.sort_values("trade_date"),
                fin_part,
                left_on="trade_date",
                right_on="_available_date",
                by="symbol",
                direction="backward",
            )
        )

    if not merged_frames:
        return daily
    merged = pd.concat(merged_frames, ignore_index=True)
    return merged.drop(columns=["report_date", "ann_date", "_available_date"], errors="ignore")
