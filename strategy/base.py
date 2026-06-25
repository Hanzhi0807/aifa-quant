"""Base strategy interface."""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """Abstract base class for portfolio strategies."""

    @abstractmethod
    def generate_signals(
        self,
        features: pd.DataFrame,
        current_date: pd.Timestamp,
        **kwargs,
    ) -> pd.DataFrame:
        """Return target portfolio for the given date.

        Columns should include at least: symbol, weight/score.
        """
        ...
