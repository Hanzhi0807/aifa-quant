"""Simple model registry for saving/loading artifacts."""

from pathlib import Path

from ..config.settings import Settings


class ModelRegistry:
    """Manage model artifact paths."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.root = Path(self.settings.data_dir_path) / "models"
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, model_name: str, version: str = "latest") -> Path:
        return self.root / f"{model_name}_{version}.pkl"
