"""Base class for iFind MCP adapters."""

import json
from abc import ABC, abstractmethod
from io import StringIO
from typing import Any

import pandas as pd
import requests

from ...config.settings import Settings


class BaseMCPAdapter(ABC):
    """Generic Streamable HTTP MCP client for iFind data sources."""

    def __init__(self, settings: Settings, url: str, token: str):
        self.settings = settings
        self.url = url
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self._tools: list[dict[str, Any]] | None = None

    def _rpc_request(self, method: str, params: dict[str, Any] | None = None, req_id: int = 1) -> dict[str, Any]:
        """Send a JSON-RPC request to the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": req_id,
        }
        response = self.session.post(self.url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    def list_tools(self) -> list[dict[str, Any]]:
        """Discover available tools from the MCP server."""
        if self._tools is None:
            result = self._rpc_request("tools/list")
            self._tools = result.get("result", {}).get("tools", [])
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a named MCP tool and return its result content."""
        result = self._rpc_request("tools/call", {"name": name, "arguments": arguments or {}})
        return result.get("result", {}).get("content", [])

    @abstractmethod
    def discover_tools(self) -> dict[str, str]:
        """Map human-readable tool names to actual MCP tool names."""
        ...

    @staticmethod
    def _content_to_dataframe(content: list[dict[str, Any]]) -> pd.DataFrame:
        """Convert MCP tool result content to a pandas DataFrame.

        iFind MCP returns JSON with a markdown table in the `answer` field.
        Handles both markdown tables and plain JSON arrays/objects.
        """
        if not content:
            return pd.DataFrame()

        first = content[0]
        if first.get("type") != "text":
            return pd.DataFrame(first.get("json", {}))

        text = first.get("text", "")

        # Case 1: iFind wraps the answer in {"code": 1, "data": {"answer": "markdown table"}}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            data_obj = payload.get("data", {})
            for key in ("answer", "result", "text"):
                answer = data_obj.get(key, "")
                if isinstance(answer, str) and "|" in answer:
                    return BaseMCPAdapter._parse_markdown_table(answer)
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
            return BaseMCPAdapter._parse_markdown_table(text)

        # Fallback: CSV
        return pd.read_csv(StringIO(text))

    @staticmethod
    def _parse_markdown_table(markdown: str) -> pd.DataFrame:
        """Parse a markdown table into a DataFrame."""
        lines = [ln.strip() for ln in markdown.splitlines() if ln.strip()]
        lines = [ln for ln in lines if "|" in ln]
        rows = [ln for ln in lines if not set(ln.strip("|").replace(" ", "")).issubset({"-", "|", ":"})]
        if len(rows) < 2:
            return pd.DataFrame()

        def split_cells(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip("|").split("|")]

        columns = split_cells(rows[0])
        data = [split_cells(row) for row in rows[1:]]
        df = pd.DataFrame(data, columns=columns)
        df.columns = [c.strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == object else x)
        return df
