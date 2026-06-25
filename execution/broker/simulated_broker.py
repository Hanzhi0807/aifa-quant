"""Simulated broker for paper trading and unit tests."""

from typing import Any

from ...core.interfaces import BaseBroker


class SimulatedBroker(BaseBroker):
    """In-memory broker that records orders without sending them to a real exchange.

    Useful for paper trading, integration tests, and strategy debugging.
    """

    def __init__(self, initial_cash: float = 1_000_000.0):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, int] = {}
        self.orders: list[dict[str, Any]] = []
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def query_positions(self) -> dict[str, int]:
        return self.positions.copy()

    def query_cash(self) -> float:
        return self.cash

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict[str, Any]:
        order_id = f"sim_{len(self.orders) + 1:06d}"
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "status": "filled",
        }
        self.orders.append(order)
        # Update internal state naively for simulation
        qty = quantity if side == "buy" else -quantity
        self.positions[symbol] = self.positions.get(symbol, 0) + qty
        return order

    def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order["order_id"] == order_id and order["status"] == "pending":
                order["status"] = "cancelled"
                return True
        return False

    def query_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            return self.orders.copy()
        return [o for o in self.orders if o["status"] == status]
