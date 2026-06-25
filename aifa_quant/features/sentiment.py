"""Sentiment factor construction from iFind news MCP data."""

import pandas as pd

from ..config.settings import Settings
from ..data.adapters import NewsMCPAdapter


def build_sentiment_features(
    symbols: list[str],
    name_map: dict[str, str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    settings: Settings | None = None,
    size_per_symbol: int = 50,
) -> pd.DataFrame:
    """Build daily sentiment features for a list of symbols.

    Args:
        symbols: List of stock symbols, e.g. ["600519.SH"].
        name_map: Optional mapping symbol -> company name to improve news recall.
        start_date: Start date (YYYYMMDD).
        end_date: End date (YYYYMMDD).
        settings: Project settings.
        size_per_symbol: Max news articles per symbol query.

    Returns:
        DataFrame with columns: symbol, trade_date, news_score, news_positive_ratio,
        news_negative_ratio, news_neutral_ratio, news_polarity, news_article_count.
    """
    adapter = NewsMCPAdapter(settings)
    name_map = name_map or {}
    frames = []
    for i, symbol in enumerate(symbols, 1):
        print(f"  [{i}/{len(symbols)}] {symbol} 情绪因子")
        try:
            df = adapter.get_sentiment_for_symbol(
                symbol,
                name=name_map.get(symbol),
                start_date=start_date,
                end_date=end_date,
                size_per_symbol=size_per_symbol,
            )
            if not df.empty:
                df["symbol"] = symbol
                frames.append(df)
        except Exception as e:
            print(f"  [WARN] {symbol} 情绪数据获取失败: {e}")

    if not frames:
        return pd.DataFrame(
            columns=[
                "symbol",
                "trade_date",
                "news_score",
                "news_positive_ratio",
                "news_negative_ratio",
                "news_neutral_ratio",
                "news_polarity",
                "news_article_count",
            ]
        )

    return pd.concat(frames, ignore_index=True)


def merge_sentiment_to_daily(
    daily_df: pd.DataFrame,
    sentiment_df: pd.DataFrame,
    date_col: str = "trade_date",
) -> pd.DataFrame:
    """Merge daily sentiment features into a daily quote DataFrame."""
    if sentiment_df.empty or daily_df.empty:
        return daily_df

    sentiment_df = sentiment_df.copy()
    sentiment_df[date_col] = pd.to_datetime(sentiment_df[date_col]).dt.normalize()
    daily_df[date_col] = pd.to_datetime(daily_df[date_col]).dt.normalize()

    merged = daily_df.merge(
        sentiment_df,
        on=["symbol", date_col],
        how="left",
    )

    # Forward-fill sentiment within each symbol up to a reasonable window
    sentiment_cols = [
        "news_score",
        "news_positive_ratio",
        "news_negative_ratio",
        "news_neutral_ratio",
        "news_polarity",
        "news_article_count",
    ]
    for col in sentiment_cols:
        if col in merged.columns:
            merged[col] = merged.groupby("symbol")[col].transform(
                lambda x: x.fillna(method="ffill", limit=5)
            )

    return merged
