"""Macroeconomic factor calculations."""

import pandas as pd


def merge_macro_to_daily(daily_df: pd.DataFrame, macro_df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """Merge a single macro time series into daily data using forward fill.

    Args:
        daily_df: DataFrame with 'trade_date' column.
        macro_df: DataFrame with 'trade_date' and 'value' columns.
        col_name: Name for the merged macro feature column.
    """
    if macro_df.empty:
        daily_df[col_name] = float("nan")
        return daily_df

    daily = daily_df.copy()
    macro = macro_df.copy().sort_values("trade_date").rename(columns={"value": col_name})

    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    macro["trade_date"] = pd.to_datetime(macro["trade_date"])

    # Use merge_asof to attach latest macro value as of each trade_date
    daily = daily.sort_values("trade_date").reset_index(drop=True)
    macro = macro.sort_values("trade_date").reset_index(drop=True)
    merged = pd.merge_asof(
        daily,
        macro[["trade_date", col_name]],
        on="trade_date",
        direction="backward",
    )
    return merged
