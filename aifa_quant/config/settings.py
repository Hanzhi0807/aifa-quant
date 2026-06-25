"""Project-wide configuration using Pydantic Settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Locate .env relative to this file (aifa_quant/config/settings.py -> aifa_quant/.env)
    _project_root = Path(__file__).parent.parent

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
