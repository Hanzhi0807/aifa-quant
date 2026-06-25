"""iFind EDB (economic database) MCP adapter."""

import pandas as pd

from ...config.settings import Settings
from .base import BaseMCPAdapter


class EDBMCPAdapter(BaseMCPAdapter):
    """Adapter for iFind macro/economic data MCP server."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        super().__init__(
            settings=s,
            url=s.ifind_edb_mcp_url,
            token=s.ifind_edb_mcp_token,
        )

    def discover_tools(self) -> dict[str, str]:
        """Discover tools provided by the EDB MCP server."""
        tools = self.list_tools()
        mapping = {}
        for tool in tools:
            name = tool.get("name", "")
            if "edb" in name.lower():
                mapping["edb"] = name
            else:
                mapping[name] = name
        return mapping

    def get_macro_data(
        self,
        indicator_query: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Fetch macro indicator time series.

        Args:
            indicator_query: Natural language query, e.g. "中国CPI同比".
            start_date: Start date YYYYMMDD.
            end_date: End date YYYYMMDD.
        """
        tools = self.discover_tools()
        tool_name = tools.get("edb")
        if not tool_name:
            raise RuntimeError("No EDB tool found")

        query = indicator_query
        if start_date:
            query += f" {start_date}"
        if end_date:
            query += f" 到 {end_date}"
        content = self.call_tool(tool_name, {"query": query})
        df = self._content_to_dataframe(content)
        return self._clean_macro_data(df)

    @staticmethod
    def _clean_macro_data(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize macro DataFrame: first column is date, second is value."""
        if df.empty or len(df.columns) < 2:
            return df

        cols = df.columns.tolist()
        df = df.rename(columns={cols[0]: "trade_date", cols[1]: "value"})
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df["value"] = pd.to_numeric(
            df["value"].astype(str).str.replace("万亿", "").str.replace("万", ""), errors="coerce"
        )
        return df.dropna(subset=["trade_date", "value"])
