"""iFind stock MCP adapter."""

from typing import Any

import pandas as pd

from ...config.settings import Settings
from .base import BaseMCPAdapter


def _split_date_range(start_date: str, end_date: str, months: int = 4) -> list[tuple[str, str]]:
    """Split a date range into chunks of approximately N calendar months."""
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    chunks = []
    current = start
    while current <= end:
        chunk_end = (current + pd.DateOffset(months=months)) - pd.Timedelta(days=1)
        chunk_end = min(chunk_end, end)
        chunks.append((current.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        current = chunk_end + pd.Timedelta(days=1)
    return chunks


class StockMCPAdapter(BaseMCPAdapter):
    """Adapter for iFind stock data MCP server."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        super().__init__(
            settings=s,
            url=s.ifind_stock_mcp_url,
            token=s.ifind_stock_mcp_token,
        )
        self._tool_map: dict[str, str] | None = None

    def discover_tools(self) -> dict[str, str]:
        """Discover actual tool names provided by the stock MCP server."""
        if self._tool_map is not None:
            return self._tool_map

        tools = self.list_tools()
        mapping = {}
        for tool in tools:
            name = tool.get("name", "")
            # Heuristic mapping based on iFind tool names.
            if "performance" in name.lower():
                mapping["daily"] = name
            elif "search" in name.lower():
                mapping["stock_list"] = name
            elif "financial" in name.lower():
                mapping["finance"] = name
            elif "summary" in name.lower():
                mapping["summary"] = name
            elif "highfreq" in name.lower():
                mapping["highfreq"] = name
            else:
                mapping[name] = name
        self._tool_map = mapping
        return mapping

    def get_stock_universe(self, query: str = "A股上市股票列表") -> pd.DataFrame:
        """Fetch the list of A-share stocks (alias for get_stock_list)."""
        return self.get_stock_list(query)

    def get_stock_list(self, query: str = "A股上市股票列表") -> pd.DataFrame:
        """Fetch the list of A-share stocks."""
        tools = self.discover_tools()
        tool_name = tools.get("stock_list")
        if not tool_name:
            raise RuntimeError("No stock_list tool found on stock MCP server")
        content = self.call_tool(tool_name, {"query": query})
        return self._content_to_dataframe(content)

    def get_daily_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV data for a single symbol.

        Args:
            symbol: Stock symbol, e.g. "000001.SZ" or "600000.SH".
            start_date: Start date in YYYYMMDD format.
            end_date: End date in YYYYMMDD format.
        """
        tools = self.discover_tools()
        tool_name = tools.get("daily")
        if not tool_name:
            raise RuntimeError("No daily/kline tool found on stock MCP server")

        if start_date is None or end_date is None:
            # Single query when no date range specified
            return self._fetch_daily_chunk(tool_name, symbol, start_date, end_date, **kwargs)

        chunks = _split_date_range(start_date, end_date, months=4)
        frames = []
        for s, e in chunks:
            df = self._fetch_daily_chunk(tool_name, symbol, s, e, **kwargs)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.drop_duplicates(subset=["symbol", "trade_date"], keep="first")
        return combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    def _fetch_daily_chunk(
        self,
        tool_name: str,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch one chunk of daily data."""
        start_str = start_date or ""
        end_str = end_date or ""
        query = f"{symbol} {start_str} 到 {end_str} 日线行情数据，包含开盘价、收盘价、最高价、最低价、成交量、成交额"
        if kwargs.get("indicators"):
            query += f"，指标：{kwargs['indicators']}"

        content = self.call_tool(tool_name, {"query": query})
        df = self._content_to_dataframe(content)
        return self._clean_daily_data(df)

    def get_financial_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Fetch quarterly financial/valuation ratios for a single symbol."""
        tools = self.discover_tools()
        tool_name = tools.get("finance")
        if not tool_name:
            raise RuntimeError("No financial tool found on stock MCP server")

        start_str = start_date or ""
        end_str = end_date or ""
        query = f"{symbol} {start_str} 到 {end_str} 财务数据，包含市盈率、市净率、净资产收益率ROE"
        content = self.call_tool(tool_name, {"query": query})
        df = self._content_to_dataframe(content)
        return self._clean_financial_data(df)

    @staticmethod
    def _clean_financial_data(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize iFind financial DataFrame to standard schema."""
        if df.empty:
            return df

        column_map = {
            "证券代码": "symbol",
            "证券简称": "name",
            "日期": "report_date",
            "公告日期": "ann_date",
            "披露日期": "ann_date",
            "发布日期": "ann_date",
            "市盈率（PE，LYR）": "pe_lyr",
            "市净率(PB,最新)": "pb",
            "市净率（PB，MRQ）": "pb_mrq",
            "净资产收益率ROE(扣除／加权)（单位：%）": "roe_deducted",
            "净资产收益率ROE(TTM)（单位：%）": "roe_ttm",
            "净资产收益率ROE(加权,公布值)（单位：%）": "roe_weighted",
            "净资产收益率ROE(摊薄,公布值)（单位：%）": "roe_diluted",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        if df.columns.duplicated().any():
            for col in df.columns[df.columns.duplicated()].unique():
                duplicate_values = df.loc[:, df.columns == col]
                df[col] = duplicate_values.bfill(axis=1).iloc[:, 0]
            df = df.loc[:, ~df.columns.duplicated()].copy()
        keep = [
            "symbol",
            "name",
            "report_date",
            "ann_date",
            "pe_lyr",
            "pb",
            "pb_mrq",
            "roe_deducted",
            "roe_ttm",
            "roe_weighted",
            "roe_diluted",
        ]
        df = df[[c for c in keep if c in df.columns]].copy()

        df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
        if "ann_date" in df.columns:
            df["ann_date"] = pd.to_datetime(df["ann_date"], errors="coerce")
        for col in ["pe_lyr", "pb", "pb_mrq", "roe_deducted", "roe_ttm", "roe_weighted", "roe_diluted"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna(subset=["symbol", "report_date"])

    def get_daily_data_many(
        self,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Fetch daily data for multiple symbols and concatenate."""
        frames = []
        for sym in symbols:
            df = self.get_daily_data(sym, start_date, end_date)
            if not df.empty:
                df["symbol"] = sym
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _clean_daily_data(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize iFind daily quote DataFrame to standard schema."""
        if df.empty:
            return df

        # Source -> target mapping. Order matters: earlier sources are preferred.
        column_groups = {
            "symbol": ["证券代码"],
            "name": ["证券简称"],
            "trade_date": ["日期"],
            "open": ["开盘价（单位：元）"],
            "high": ["最高价（单位：元）"],
            "low": ["最低价（单位：元）"],
            "close": ["收盘价（单位：元）"],
            "volume": ["成交量(含大宗交易)（单位：股）", "成交量"],
            "amount": ["成交额(含大宗交易)（单位：元）", "成交额（单位：元）"],
        }
        renamed = {}
        for target, sources in column_groups.items():
            available = [s for s in sources if s in df.columns]
            if not available:
                continue
            # Coalesce multiple source columns (prefer first non-null)
            series = df[available[0]].copy()
            for src in available[1:]:
                series = series.fillna(df[src])
            renamed[target] = series
        df = pd.DataFrame(renamed)

        # Ensure standardized columns exist
        keep = ["symbol", "name", "trade_date", "open", "high", "low", "close", "volume", "amount"]
        for col in keep:
            if col not in df.columns:
                df[col] = float("nan")
        df = df[keep].copy()

        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ["volume", "amount"]:
            if col in df.columns:
                df[col] = df[col].apply(StockMCPAdapter._parse_chinese_number)

        # Infer missing volume/amount from each other
        if "volume" in df.columns and "amount" in df.columns and "close" in df.columns:
            missing_volume = df["volume"].isna() & df["amount"].notna() & df["close"].notna()
            df.loc[missing_volume, "volume"] = df.loc[missing_volume, "amount"] / df.loc[missing_volume, "close"]
            missing_amount = df["amount"].isna() & df["volume"].notna() & df["close"].notna()
            df.loc[missing_amount, "amount"] = df.loc[missing_amount, "volume"] * df.loc[missing_amount, "close"]

        return df.dropna(subset=["symbol", "trade_date", "close"])

    @staticmethod
    def _parse_chinese_number(value) -> float:
        """Parse numbers with Chinese units like 1.2万 or 3.5亿."""
        if pd.isna(value):
            return float("nan")
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        multiplier = 1.0
        if text.endswith("万"):
            multiplier = 10_000
            text = text[:-1]
        elif text.endswith("亿"):
            multiplier = 100_000_000
            text = text[:-1]
        try:
            return float(text) * multiplier
        except ValueError:
            return float("nan")

    @staticmethod
    def _content_to_dataframe(content: list[dict[str, Any]]) -> pd.DataFrame:
        """Convert MCP tool result content to a pandas DataFrame."""
        return BaseMCPAdapter._content_to_dataframe(content)

    @staticmethod
    def _parse_markdown_table(markdown: str) -> pd.DataFrame:
        """Parse a markdown table into a DataFrame."""
        return BaseMCPAdapter._parse_markdown_table(markdown)
