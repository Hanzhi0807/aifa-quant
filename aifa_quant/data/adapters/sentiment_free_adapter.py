"""Free sentiment data adapter using Eastmoney data via AkShare.

Uses the Eastmoney "千股千评" historical score endpoint to build a daily
sentiment score without consuming iFind MCP quota.
"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd

from ...config.settings import Settings


class FreeSentimentAdapter:
    """Fetch free sentiment scores from Eastmoney (AkShare)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        try:
            import akshare as ak  # type: ignore

            self._ak = ak
        except ImportError as e:
            raise RuntimeError("AkShare is not installed. Run: pip install akshare") from e

    @staticmethod
    def _to_ak_code(symbol: str) -> str:
        """Convert '000001.SZ' -> '000001'."""
        return symbol.split(".")[0]

    @staticmethod
    def _to_standard_symbol(code: str) -> str:
        """Convert '000001' -> '000001.SZ'."""
        code = str(code).strip()
        if len(code) == 6 and code.isdigit():
            return f"{code}.SH" if code.startswith(("6", "5", "9")) else f"{code}.SZ"
        return code.upper()

    def get_historical_scores(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return historical Eastmoney comment score for a single symbol.

        Columns: symbol, trade_date, news_score, news_positive_ratio,
                 news_negative_ratio, news_neutral_ratio, news_polarity,
                 news_article_count.
        """
        code = self._to_ak_code(symbol)
        try:
            df = self._ak.stock_comment_detail_zhpj_lspf_em(symbol=code)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch sentiment for {symbol}: {e}") from e

        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
        # Columns: 交易日, 评分
        date_col = "交易日" if "交易日" in df.columns else df.columns[0]
        score_col = "评分" if "评分" in df.columns else df.columns[1]
        df = df.rename(columns={date_col: "trade_date", score_col: "score"})
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        df = df.dropna(subset=["trade_date", "score"])

        if start_date:
            df = df[df["trade_date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["trade_date"] <= pd.to_datetime(end_date)]

        if df.empty:
            return pd.DataFrame()

        # Normalize score to [0, 1] assuming Eastmoney score is 0-100
        df["news_score"] = df["score"].clip(0, 100) / 100.0
        df["news_polarity"] = (df["news_score"] - 0.5) * 2.0
        df["news_positive_ratio"] = df["news_score"].clip(0, 1)
        df["news_negative_ratio"] = (1 - df["news_score"]).clip(0, 1)
        df["news_neutral_ratio"] = 0.0
        df["news_article_count"] = 1
        df["symbol"] = self._to_standard_symbol(code)

        return df[
            [
                "symbol",
                "trade_date",
                "news_score",
                "news_positive_ratio",
                "news_negative_ratio",
                "news_neutral_ratio",
                "news_polarity",
                "news_article_count",
            ]
        ]

    def get_sentiment_for_symbols(
        self,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        sleep_seconds: float = 0.3,
    ) -> pd.DataFrame:
        """Fetch historical sentiment scores for multiple symbols."""
        frames: list[pd.DataFrame] = []
        for i, symbol in enumerate(symbols, 1):
            try:
                df = self.get_historical_scores(symbol, start_date, end_date)
                if not df.empty:
                    frames.append(df)
            except Exception as e:
                print(f"  [WARN] {symbol} 免费情绪数据获取失败: {e}")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
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

    def get_latest_scores(self) -> pd.DataFrame:
        """Fetch the latest available scores for all A-shares from stock_comment_em."""
        df = self._ak.stock_comment_em()
        df = df.copy()
        df.columns = [c.strip() for c in df.columns]
        if "代码" not in df.columns or "综合得分" not in df.columns:
            return pd.DataFrame()
        df["symbol"] = df["代码"].astype(str).apply(self._to_standard_symbol)
        df["news_score"] = pd.to_numeric(df["综合得分"], errors="coerce").clip(0, 100) / 100.0
        df["trade_date"] = pd.to_datetime("today").normalize()
        df["news_polarity"] = (df["news_score"] - 0.5) * 2.0
        df["news_positive_ratio"] = df["news_score"]
        df["news_negative_ratio"] = 1 - df["news_score"]
        df["news_neutral_ratio"] = 0.0
        df["news_article_count"] = 1
        return df[
            [
                "symbol",
                "trade_date",
                "news_score",
                "news_positive_ratio",
                "news_negative_ratio",
                "news_neutral_ratio",
                "news_polarity",
                "news_article_count",
            ]
        ]


def build_free_sentiment_features(
    symbols: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    settings: Settings | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Convenience function matching the iFind sentiment builder signature."""
    adapter = FreeSentimentAdapter(settings)
    return adapter.get_sentiment_for_symbols(symbols, start_date, end_date, **kwargs)
