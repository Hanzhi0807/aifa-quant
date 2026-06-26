"""Tushare Pro adapter for A-share market data.

Requires a Tushare Pro token. Set it in `.env` as `TUSHARE_TOKEN=...`.
"""

from typing import Any

import pandas as pd

from ...config.settings import Settings
from ...core.interfaces import BaseDataSource


class TushareAdapter(BaseDataSource):
    """Data source adapter using Tushare Pro.

    Suitable for:
      - A-share daily OHLCV quotes
      - Index daily quotes
      - Index component stock lists
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        try:
            import tushare as ts  # type: ignore

            self._ts = ts
        except ImportError as e:
            raise RuntimeError("Tushare is not installed. Run: pip install tushare") from e

        token = self.settings.tushare_token
        if not token:
            raise RuntimeError("Tushare token is missing. Set TUSHARE_TOKEN in .env")
        self._pro = ts.pro_api(token)

    @staticmethod
    def _to_ts_symbol(symbol: str) -> str:
        """Convert '000001.SZ' -> '000001.SZ' (Tushare ts_code)."""
        symbol = symbol.upper().strip()
        if "." in symbol:
            return symbol
        if len(symbol) == 6 and symbol.isdigit():
            return f"{symbol}.SH" if symbol.startswith(("6", "5", "9")) else f"{symbol}.SZ"
        return symbol

    @staticmethod
    def _to_standard_symbol(ts_code: str) -> str:
        """Convert Tushare ts_code '000001.SZ' -> standard '000001.SZ'."""
        return ts_code.upper().strip()

    @staticmethod
    def _format_date(date: str | None) -> str | None:
        if not date:
            return None
        return pd.to_datetime(date).strftime("%Y%m%d")

    def _clean_daily_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
        column_map = {
            "trade_date": "trade_date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "vol": "volume",
            "volume": "volume",
            "amount": "amount",
        }
        df = df.rename(columns=column_map)
        df["symbol"] = symbol
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        keep = ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"]
        df = df[[c for c in keep if c in df.columns]].copy()
        return df.dropna(subset=["trade_date", "close"])

    def get_daily_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        ts_symbol = self._to_ts_symbol(symbol)
        start_str = self._format_date(start_date)
        end_str = self._format_date(end_date)
        df = self._pro.daily(ts_code=ts_symbol, start_date=start_str, end_date=end_str)
        return self._clean_daily_data(df, self._to_standard_symbol(ts_symbol))

    def get_index_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        ts_symbol = self._to_ts_symbol(symbol)
        start_str = self._format_date(start_date)
        end_str = self._format_date(end_date)
        df = self._pro.index_daily(ts_code=ts_symbol, start_date=start_str, end_date=end_str)
        if df.empty:
            return df
        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns={"trade_date": "trade_date"})
        df["symbol"] = self._to_standard_symbol(ts_symbol)
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
        for col in ["open", "high", "low", "close", "vol", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.rename(columns={"vol": "volume"})
        df = df[[c for c in ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"] if c in df.columns]]
        df = df.dropna(subset=["trade_date", "close"])
        if start_date:
            df = df[df["trade_date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["trade_date"] <= pd.to_datetime(end_date)]
        return df

    def get_stock_universe(self, query: str = "000300.SH") -> list[str]:
        """Fetch index component stock list.

        Args:
            query: Index ts_code like '000300.SH' (CSI 300) or '000016.SH' (SSE 50).
        """
        ts_code = self._to_ts_symbol(query)
        # Use the latest available trade date in the index_weight table
        latest = self._pro.index_weight(index_code=ts_code, limit=1)
        if latest.empty:
            return []
        trade_date = latest.iloc[0]["trade_date"]
        df = self._pro.index_weight(index_code=ts_code, trade_date=trade_date)
        if df.empty or "con_code" not in df.columns:
            return []
        return [self._to_standard_symbol(code) for code in df["con_code"].astype(str).tolist()]
