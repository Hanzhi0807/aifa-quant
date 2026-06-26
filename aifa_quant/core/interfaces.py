"""Core abstract interfaces for data sources, models, strategies, and brokers.

This module defines the stable contracts that plugins and external integrations
must implement. Concrete implementations live in their respective modules.
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from ..models.base import BaseModel
from ..strategy.base import BaseStrategy


class BaseDataSource(ABC):
    """Abstract data source for market and economic data.

    Implementations may use iFind MCP, AkShare, Tushare, Baostock, or any other
    data provider. The core framework only depends on the returned schema.
    """

    @abstractmethod
    def get_daily_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV quotes for a single symbol.

        Returned DataFrame should contain at least:
        symbol, trade_date, open, high, low, close, volume, amount.
        """
        ...

    @abstractmethod
    def get_index_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch daily index quotes for benchmarking.

        Returned DataFrame should contain at least:
        symbol, trade_date, close.
        """
        ...


class BaseBroker(ABC):
    """Abstract broker interface for simulated or live trading execution."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the broker/trading terminal."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the broker/trading terminal."""
        ...

    @abstractmethod
    def query_positions(self) -> dict[str, int]:
        """Return current holdings as {symbol: quantity}."""
        ...

    @abstractmethod
    def query_cash(self) -> float:
        """Return available cash balance."""
        ...

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict[str, Any]:
        """Submit an order and return order metadata.

        Args:
            symbol: Stock symbol, e.g. "600519.SH".
            side: "buy" or "sell".
            quantity: Number of shares (must be integer multiple of lot size).
            order_type: "market" or "limit".
            price: Limit price, required if order_type is "limit".
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        ...

    @abstractmethod
    def query_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        """Return list of orders, optionally filtered by status."""
        ...


__all__ = [
    "BaseModel",
    "BaseStrategy",
    "BaseDataSource",
    "BaseBroker",
]
