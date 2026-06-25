"""iFind index MCP adapter."""

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

    def discover_tools(self):
        # Placeholder: implement after inspecting available tools.
        return {}
