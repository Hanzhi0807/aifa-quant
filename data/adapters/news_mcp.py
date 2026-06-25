"""iFind news MCP adapter."""

from ...config.settings import Settings
from .base import BaseMCPAdapter


class NewsMCPAdapter(BaseMCPAdapter):
    """Adapter for iFind news/sentiment MCP server."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        super().__init__(
            settings=s,
            url=s.ifind_news_mcp_url,
            token=s.ifind_news_mcp_token,
        )

    def discover_tools(self):
        # Placeholder: implement after inspecting available tools.
        return {}
