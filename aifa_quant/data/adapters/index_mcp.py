"""iFind index MCP adapter."""

import pandas as pd

from ...config.settings import Settings
from .base import BaseMCPAdapter
from .stock_mcp import _split_date_range


class IndexMCPAdapter(BaseMCPAdapter):
    """Adapter for iFind index MCP server."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        super().__init__(
            settings=s,
            url=s.ifind_index_mcp_url,
            token=s.ifind_index_mcp_token,
        )
        self._tool_map: dict[str, str] | None = None

    def discover_tools(self) -> dict[str, str]:
        """Discover actual tool names provided by the index MCP server."""
        if self._tool_map is not None:
            return self._tool_map

        tools = self.list_tools()
        mapping = {}
        for tool in tools:
            name = tool.get("name", "")
            lower = name.lower()
            if "index_data" in lower or "performance" in lower or "kline" in lower or "行情" in lower:
                mapping["daily"] = name
            else:
                mapping[name] = name
        self._tool_map = mapping
        return mapping

    def get_daily_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        """Fetch daily index data."""
        tools = self.discover_tools()
        tool_name = tools.get("daily")
        if not tool_name:
            raise RuntimeError("No daily tool found on index MCP server")

        if start_date is None or end_date is None:
            return self._fetch_index_chunk(tool_name, symbol, start_date, end_date)

        chunks = _split_date_range(start_date, end_date, months=4)
        frames = []
        for s, e in chunks:
            df = self._fetch_index_chunk(tool_name, symbol, s, e)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.drop_duplicates(subset=["symbol", "trade_date"], keep="first")
        return combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    def _fetch_index_chunk(
        self,
        tool_name: str,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
    ) -> pd.DataFrame:
        """Fetch one chunk of index close data."""
        start_str = start_date or ""
        end_str = end_date or ""
        query = f"{symbol} {start_str} 到 {end_str} 收盘价"
        content = self.call_tool(tool_name, {"query": query})
        df = self._content_to_dataframe(content)
        # Normalize column names similar to stock adapter
        column_map = {
            "证券代码": "symbol",
            "指数代码": "symbol",
            "指数名称": "name",
            "日期": "trade_date",
            "开盘价（单位：元）": "open",
            "收盘价（单位：元）": "close",
            "最高价（单位：元）": "high",
            "最低价（单位：元）": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
