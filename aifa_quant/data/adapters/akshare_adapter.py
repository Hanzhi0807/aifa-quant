"""AkShare adapter for free A-share market data.

AkShare is used as the default data source for daily quotes and index data.
Fundamental / macro / sentiment data still relies on iFind MCP.
"""

import re
import time
from typing import Any

import pandas as pd

from ...config.settings import Settings
from ...core.interfaces import BaseDataSource


class AkShareAdapter(BaseDataSource):
    """Free data source adapter using AkShare.

    Suitable for:
      - A-share daily OHLCV quotes
      - Index daily quotes (CSI 300, SSE 50, etc.)
      - Index component stock lists

    Not suitable for:
      - Quarterly fundamental ratios (use iFind)
      - Macroeconomic indicators (use iFind)
      - News sentiment (use iFind)
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        try:
            import akshare as ak  # type: ignore

            self._ak = ak
        except ImportError as e:
            raise RuntimeError(
                "AkShare is not installed. Run: pip install akshare"
            ) from e

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _to_akshare_symbol(symbol: str) -> str:
        """Convert '000001.SZ' -> 'sz000001' used by AkShare Sina interfaces."""
        if "." in symbol:
            code, exchange = symbol.upper().split(".")
            prefix = "sh" if exchange == "SH" else "sz"
            return f"{prefix}{code}"
        return symbol

    @staticmethod
    def _to_standard_symbol(symbol: str) -> str:
        """Convert '000001' / 'sz000001' -> '000001.SZ'."""
        symbol = symbol.lower().strip()
        if symbol.startswith("sh"):
            return f"{symbol[2:]}.SH"
        if symbol.startswith("sz"):
            return f"{symbol[2:]}.SZ"
        # Pure 6-digit code: infer exchange by first digit
        if len(symbol) == 6 and symbol.isdigit():
            if symbol.startswith(("6", "5", "9")):
                return f"{symbol}.SH"
            return f"{symbol}.SZ"
        return symbol.upper()

    @staticmethod
    def _format_date(date: str | None) -> str | None:
        """Accept YYYYMMDD and return YYYYMMDD; return None if empty."""
        if not date:
            return None
        return pd.to_datetime(date).strftime("%Y%m%d")

    @staticmethod
    def _clean_daily_data(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Normalize AkShare daily quote DataFrame to standard schema."""
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        # AkShare Sina daily columns:
        # date, open, high, low, close, volume, amount, outstanding_share, turnover
        column_map = {
            "date": "trade_date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "amount": "amount",
        }
        df = df.rename(columns=column_map)

        df["symbol"] = symbol
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        keep = ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"]
        df = df[[c for c in keep if c in df.columns]].copy()
        return df.dropna(subset=["trade_date", "close"])

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def get_daily_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV data for a single A-share symbol."""
        ak_symbol = self._to_akshare_symbol(symbol)
        start_str = self._format_date(start_date)
        end_str = self._format_date(end_date)

        if not start_str or not end_str:
            # Fetch all available data if no date range
            df = self._ak.stock_zh_a_daily(symbol=ak_symbol, adjust="qfq")
        else:
            df = self._ak.stock_zh_a_daily(
                symbol=ak_symbol,
                start_date=start_str,
                end_date=end_str,
                adjust="qfq",
            )

        return self._clean_daily_data(df, symbol)

    def get_index_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch daily index quotes (e.g., 000300.SH -> sh000300)."""
        ak_symbol = self._to_akshare_symbol(symbol)
        df = self._ak.stock_zh_index_daily(symbol=ak_symbol)
        if df.empty:
            return df

        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns={"date": "trade_date"})
        df["symbol"] = symbol
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df[["symbol", "trade_date", "open", "high", "low", "close", "volume"]].copy()
        df = df.dropna(subset=["trade_date", "close"])

        if start_date:
            df = df[df["trade_date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["trade_date"] <= pd.to_datetime(end_date)]
        return df

    @staticmethod
    def _extract_symbols(df: pd.DataFrame) -> list[str]:
        """Extract standard '000001.SZ' symbols from AkShare index component DataFrame."""
        if df.empty:
            return []

        # Robust column detection: code column contains 6-digit strings,
        # exchange column contains "Stock Exchange".
        code_col = None
        exchange_col = None
        for col in df.columns:
            sample = str(df[col].dropna().iloc[0]).strip()
            if re.fullmatch(r"\d{6}", sample):
                code_col = col
            if "Stock Exchange" in sample:
                exchange_col = col

        if code_col is None or exchange_col is None:
            return []

        exchange_map = {
            "Shanghai Stock Exchange": "SH",
            "Shenzhen Stock Exchange": "SZ",
        }
        symbols = []
        for _, row in df.iterrows():
            code = str(row[code_col]).strip()
            exchange = str(row[exchange_col]).strip()
            suffix = exchange_map.get(exchange)
            if suffix and len(code) == 6:
                symbols.append(f"{code}.{suffix}")
        return symbols

    def get_stock_universe(self, query: str = "沪深300") -> list[str]:
        """Fetch index component stock list.

        Args:
            query: Friendly name like "沪深300", "上证50", or raw index code "000300".
        """
        universe_map = {
            "上证50": "000016",
            "沪深300": "000300",
            "中证500": "000905",
            "中证1000": "000852",
        }
        symbol = universe_map.get(query, query)

        df = self._ak.index_stock_cons_weight_csindex(symbol=symbol)
        if df.empty:
            # Fallback to non-weight version
            df = self._ak.index_stock_cons_csindex(symbol=symbol)
        return self._extract_symbols(df)

    def get_daily_data_many(
        self,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        sleep_seconds: float = 0.5,
    ) -> pd.DataFrame:
        """Fetch daily data for multiple symbols sequentially with polite delay."""
        frames = []
        for sym in symbols:
            try:
                df = self.get_daily_data(sym, start_date=start_date, end_date=end_date)
                if not df.empty:
                    frames.append(df)
            except Exception as e:
                print(f"[WARN] AkShare {sym} 获取失败: {e}")
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)
