"""Simulated broker for paper trading and unit tests."""

from typing import Any

import pandas as pd

from ...core.interfaces import BaseBroker
from ...data.storage import DuckDBStore


class SimulatedBroker(BaseBroker):
    """In-memory broker that records orders without sending them to a real exchange.

    Supports A-share trading rules (100-share lots, stamp duty on sell,
    min commission, limit-up/down skip) when daily quote data is provided.
    If no quote data is set, it falls back to a simplified test mode.

    Optionally backed by ``DuckDBStore`` so that cash, positions and orders
    survive across process restarts.
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000.0,
        store: DuckDBStore | None = None,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        stamp_duty_rate: float = 0.001,
        slippage: float = 0.0,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self._positions: dict[str, dict[str, Any]] = {}  # symbol -> {shares, cost_basis}
        self.orders: list[dict[str, Any]] = []
        self.store = store
        self._connected = False

        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_duty_rate = stamp_duty_rate
        self.slippage = slippage

        self._trade_date: pd.Timestamp | None = None
        self._day_quotes: pd.DataFrame | None = None
        self._prev_close_map: dict[str, float] | None = None

    # ------------------------------------------------------------------
    # Connection & state management
    # ------------------------------------------------------------------
    def connect(self) -> None:
        self._connected = True
        if self.store is not None:
            self._load_state()

    def disconnect(self) -> None:
        if self.store is not None:
            self._save_state()
        self._connected = False

    def reset_state(self) -> None:
        """Clear all positions/orders and reset cash to initial capital."""
        self.cash = self.initial_cash
        self._positions = {}
        self.orders = []
        if self.store is not None:
            self.store.clear_paper_state()
            self._save_state()

    def _load_state(self) -> None:
        """Load cash, positions and orders from the configured store."""
        if self.store is None:
            return

        stored_cash = self.store.load_paper_cash()
        if stored_cash is not None:
            self.cash = float(stored_cash)

        pos_df = self.store.load_paper_positions()
        self._positions = {}
        for _, row in pos_df.iterrows():
            sym = str(row["symbol"])
            self._positions[sym] = {
                "shares": int(row["shares"]),
                "cost_basis": float(row["cost_basis"]),
            }

        self.orders = self.store.load_paper_orders().to_dict("records")

    def _save_state(self) -> None:
        """Persist cash, positions and orders to the configured store."""
        if self.store is None:
            return

        if self._positions:
            pos_df = pd.DataFrame(
                [
                    {
                        "symbol": sym,
                        "shares": data["shares"],
                        "cost_basis": data["cost_basis"],
                    }
                    for sym, data in self._positions.items()
                    if data["shares"] != 0
                ]
            )
        else:
            pos_df = pd.DataFrame(columns=["symbol", "shares", "cost_basis"])
        self.store.save_paper_positions(pos_df)

        nav_df = pd.DataFrame(
            [
                {
                    "trade_date": self._trade_date or pd.Timestamp.now().normalize(),
                    "cash": self.cash,
                    "market_value": self._market_value(),
                    "total_value": self.cash + self._market_value(),
                }
            ]
        )
        self.store.save_paper_nav(nav_df)

        if self.orders:
            self.store.save_paper_orders(pd.DataFrame(self.orders))

    # ------------------------------------------------------------------
    # Daily market data
    # ------------------------------------------------------------------
    def set_quotes(
        self,
        trade_date: pd.Timestamp,
        day_quotes: pd.DataFrame,
        prev_close_map: dict[str, float] | None = None,
    ) -> None:
        """Set the current day's market data used for fills and limit checks."""
        self._trade_date = pd.to_datetime(trade_date)
        self._day_quotes = day_quotes.copy() if day_quotes is not None else None
        self._prev_close_map = prev_close_map.copy() if prev_close_map else None

    # ------------------------------------------------------------------
    # Order interface
    # ------------------------------------------------------------------
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict[str, Any]:
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError(f"Unsupported side: {side}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if quantity % 100 != 0:
            raise ValueError("A-shares require quantity to be a multiple of 100")

        order_id = f"sim_{len(self.orders) + 1:06d}"
        base_order = {
            "order_id": order_id,
            "trade_date": self._trade_date,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "fill_price": None,
            "commission": 0.0,
            "stamp_duty": 0.0,
            "status": "pending",
        }

        quote_price = self._quote_price(symbol)
        exec_price = price if price is not None else quote_price
        if exec_price is None:
            # Test mode fallback
            exec_price = 100.0

        # Limit-up / limit-down checks only when we have a reference close
        prev_close = self._prev_close(symbol)
        if prev_close:
            if side == "buy" and exec_price >= prev_close * 1.095:
                base_order["status"] = "rejected-limit-up"
                self.orders.append(base_order)
                return base_order
            if side == "sell" and exec_price <= prev_close * 0.905:
                base_order["status"] = "rejected-limit-down"
                self.orders.append(base_order)
                return base_order

        # Apply slippage
        if side == "buy":
            fill_price = exec_price * (1 + self.slippage)
            amount = fill_price * quantity
            commission = max(amount * self.commission_rate, self.min_commission)
            total_cost = amount + commission
            if total_cost > self.cash:
                base_order["status"] = "rejected-insufficient-cash"
                self.orders.append(base_order)
                return base_order

            self.cash -= total_cost
            pos = self._positions.setdefault(symbol, {"shares": 0, "cost_basis": 0.0})
            new_shares = pos["shares"] + quantity
            new_cost = (pos["shares"] * pos["cost_basis"] + quantity * fill_price) / new_shares
            pos["shares"] = new_shares
            pos["cost_basis"] = new_cost
            base_order.update(
                {
                    "fill_price": fill_price,
                    "commission": commission,
                    "status": "filled",
                }
            )
        else:  # sell
            pos = self._positions.get(symbol)
            if pos is None or pos["shares"] == 0:
                base_order["status"] = "rejected-no-position"
                self.orders.append(base_order)
                return base_order

            quantity = min(quantity, pos["shares"])
            fill_price = exec_price * (1 - self.slippage)
            amount = fill_price * quantity
            commission = max(amount * self.commission_rate, self.min_commission)
            stamp_duty = amount * self.stamp_duty_rate
            self.cash += amount - commission - stamp_duty
            pos["shares"] -= quantity
            if pos["shares"] == 0:
                del self._positions[symbol]
            base_order.update(
                {
                    "fill_price": fill_price,
                    "commission": commission,
                    "stamp_duty": stamp_duty,
                    "status": "filled",
                }
            )

        self.orders.append(base_order)
        return base_order

    def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order["order_id"] == order_id and order["status"] == "pending":
                order["status"] = "cancelled"
                return True
        return False

    def query_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        orders = [o.copy() for o in self.orders]
        if status is None:
            return orders
        return [o for o in orders if o.get("status") == status]

    def query_positions(self) -> dict[str, int]:
        return {sym: data["shares"] for sym, data in self._positions.items()}

    def query_cost_basis(self) -> dict[str, float]:
        return {sym: data["cost_basis"] for sym, data in self._positions.items()}

    def query_cash(self) -> float:
        return self.cash

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _quote_price(self, symbol: str) -> float | None:
        if self._day_quotes is None or self._day_quotes.empty:
            return None
        row = self._day_quotes[self._day_quotes["symbol"] == symbol]
        if row.empty or "close" not in row.columns:
            return None
        return float(row.iloc[0]["close"])

    def _prev_close(self, symbol: str) -> float | None:
        if self._prev_close_map and symbol in self._prev_close_map:
            return float(self._prev_close_map[symbol])
        pos = self._positions.get(symbol)
        if pos:
            return float(pos["cost_basis"])
        return None

    def _market_value(self, day_quotes: pd.DataFrame | None = None) -> float:
        quotes = day_quotes if day_quotes is not None else self._day_quotes
        if quotes is None or quotes.empty:
            return 0.0
        value = 0.0
        for sym, data in self._positions.items():
            row = quotes[quotes["symbol"] == sym]
            if not row.empty and "close" in row.columns:
                value += data["shares"] * float(row.iloc[0]["close"])
        return value
