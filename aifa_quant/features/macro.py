"""Macroeconomic factor calculations."""

import pandas as pd

MACRO_PUBLICATION_DELAY_DAYS = 30


def merge_macro_to_daily(daily_df: pd.DataFrame, macro_df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """Merge a macro time series after a conservative publication delay.

    If a data source later provides an actual publication date, that field
    should replace this fixed delay.
    """
    if macro_df.empty:
        daily_df[col_name] = float("nan")
        return daily_df

    daily = daily_df.copy()
    macro = macro_df.copy().sort_values("trade_date").rename(columns={"value": col_name})

    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    macro["trade_date"] = pd.to_datetime(macro["trade_date"]) + pd.Timedelta(days=MACRO_PUBLICATION_DELAY_DAYS)

    daily = daily.sort_values("trade_date").reset_index(drop=True)
    macro = macro.sort_values("trade_date").reset_index(drop=True)
    merged = pd.merge_asof(
        daily,
        macro[["trade_date", col_name]],
        on="trade_date",
        direction="backward",
    )
    return merged
