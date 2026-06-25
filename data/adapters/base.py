"""Base class for iFind MCP adapters."""

from abc import ABC, abstractmethod
from typing import Any

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
