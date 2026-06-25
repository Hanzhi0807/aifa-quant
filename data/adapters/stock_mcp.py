"""iFind stock MCP adapter."""

from typing import Any

import pandas as pd

from ...config.settings import Settings
from .base import BaseMCPAdapter


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

        # iFind get_stock_performance expects a natural-language query.
        # Explicitly request OHLCV fields; otherwise volume/amount may be omitted.
        start_str = start_date or ""
        end_str = end_date or ""
        query = f"{symbol} {start_str} 到 {end_str} 日线行情数据，包含开盘价、收盘价、最高价、最低价、成交量、成交额"
        if kwargs.get("indicators"):
            query += f"，指标：{kwargs['indicators']}"

        content = self.call_tool(tool_name, {"query": query})
        df = self._content_to_dataframe(content)
        return self._clean_daily_data(df)

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
        """Convert MCP tool result content to a pandas DataFrame.

        iFind MCP returns JSON with a markdown table in the `answer` field.
        We handle both markdown tables and plain JSON arrays/objects.
        """
        if not content:
            return pd.DataFrame()

        first = content[0]
        if first.get("type") != "text":
            return pd.DataFrame(first.get("json", {}))

        import json
        from io import StringIO

        text = first.get("text", "")

        # Case 1: iFind wraps the answer in {"code": 1, "data": {"answer": "markdown table"}}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            data_obj = payload.get("data", {})
            # iFind sometimes puts markdown under data.answer, sometimes data.result
            for key in ("answer", "result"):
                answer = data_obj.get(key, "")
                if isinstance(answer, str) and "|" in answer:
                    return StockMCPAdapter._parse_markdown_table(answer)
            # Plain JSON object with data array
            data = data_obj if isinstance(data_obj, list) else None
            if data is None and isinstance(data_obj, dict):
                data = data_obj.get("data")
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict) and "data" in data:
                return pd.DataFrame(data["data"])

        if isinstance(payload, list):
            return pd.DataFrame(payload)

        # Case 2: raw markdown table
        if "|" in text:
            return StockMCPAdapter._parse_markdown_table(text)

        # Fallback: CSV
        return pd.read_csv(StringIO(text))

    @staticmethod
    def _parse_markdown_table(markdown: str) -> pd.DataFrame:
        """Parse a markdown table into a DataFrame."""
        lines = [ln.strip() for ln in markdown.splitlines() if ln.strip()]
        # Only keep lines that look like table rows (contain |)
        lines = [ln for ln in lines if "|" in ln]
        # Filter out separator lines like |---|---|
        rows = [ln for ln in lines if not set(ln.strip("|").replace(" ", "")).issubset({"-", "|", ":"})]
        if len(rows) < 2:
            return pd.DataFrame()

        def split_cells(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip("|").split("|")]

        columns = split_cells(rows[0])
        data = [split_cells(row) for row in rows[1:]]
        df = pd.DataFrame(data, columns=columns)
        # Strip whitespace from cells and column names
        df.columns = [c.strip() for c in df.columns]
        return df.map(lambda x: x.strip() if isinstance(x, str) else x)
