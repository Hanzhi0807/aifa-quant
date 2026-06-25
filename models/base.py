"""Base model interface."""

from abc import ABC, abstractmethod

import pandas as pd


class BaseModel(ABC):
    """Abstract base class for predictive models."""

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, feature_names: list[str]) -> None:
        """Train the model."""
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Return prediction scores/probabilities."""
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        """Persist model to disk."""
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from disk."""
        ...

    @property
    @abstractmethod
    def feature_importance(self) -> pd.Series:
        """Return feature importance if available."""
        ...
