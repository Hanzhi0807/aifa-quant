"""iFind EDB (economic database) MCP adapter."""

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

    def discover_tools(self):
        # Placeholder: implement after inspecting available tools.
        return {}
