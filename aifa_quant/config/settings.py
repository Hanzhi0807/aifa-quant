"""Project-wide configuration using Pydantic Settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Locate the project root by walking up until a .env file is found."""
    path = Path(__file__).resolve().parent.parent
    while path.parent != path:
        if (path / ".env").exists():
            return path
        path = path.parent
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Locate .env by walking up from this file until a project root .env is found.
    _project_root = _find_project_root()

    model_config = SettingsConfigDict(
        env_file=str(_project_root / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # iFind MCP endpoints
    ifind_stock_mcp_url: str = ""
    ifind_stock_mcp_token: str = ""
    ifind_edb_mcp_url: str = ""
    ifind_edb_mcp_token: str = ""
    ifind_news_mcp_url: str = ""
    ifind_news_mcp_token: str = ""
    ifind_index_mcp_url: str = ""
    ifind_index_mcp_token: str = ""

    # Third-party data source tokens
    tushare_token: str = ""

    # Project paths
    data_dir: str = "./data_store"
    duckdb_path: str = "./data_store/aifa_quant.duckdb"

    @property
    def data_dir_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def duckdb_path_abs(self) -> Path:
        return Path(self.duckdb_path).resolve()


settings = Settings()
