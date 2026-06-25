"""iFind index MCP adapter."""

import pandas as pd

from ...config.settings import Settings
from .base import BaseMCPAdapter


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
            if "performance" in name.lower() or "kline" in name.lower() or "行情" in name.lower():
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

        start_str = start_date or ""
        end_str = end_date or ""
        query = f"{symbol} {start_str} 到 {end_str} 日线行情数据"
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
