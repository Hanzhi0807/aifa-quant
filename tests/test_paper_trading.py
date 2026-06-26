"""Tests for paper trading broker and engine."""

import pandas as pd
import pytest

from aifa_quant.data.storage import DuckDBStore
from aifa_quant.execution.broker import SimulatedBroker
from aifa_quant.paper_trading import PaperTradingEngine


def _make_quotes(symbols, close, prev_close=None):
    df = pd.DataFrame(
        {
            "symbol": symbols,
            "trade_date": pd.Timestamp("2024-12-31"),
            "close": close,
        }
    )
    prev_map = {}
    if prev_close:
        prev_map = dict(zip(symbols, prev_close))
    return df, prev_map


class TestSimulatedBroker:
    def test_buy_and_sell_with_quotes(self):
        broker = SimulatedBroker(initial_cash=1_000_000.0)
        quotes, prev = _make_quotes(["A", "B"], [100.0, 50.0], [99.0, 49.0])
        broker.set_quotes(pd.Timestamp("2024-12-31"), quotes, prev)

        broker.submit_order("A", "buy", 100)
        assert broker.query_positions()["A"] == 100
        # cost = 100*100 + max(100*100*0.0003, 5) = 10000 + 5
        assert broker.query_cash() == pytest.approx(989_995.0)

        broker.submit_order("A", "sell", 100)
        assert "A" not in broker.query_positions()
        # proceeds = 100*100 - 5 - 100*100*0.001 = 10000 - 5 - 10 = 9985
        assert broker.query_cash() == pytest.approx(999_980.0)

    def test_limit_up_buy_rejected(self):
        broker = SimulatedBroker(initial_cash=1_000_000.0)
        # price hits +10% against prev close
        quotes, prev = _make_quotes(["A"], [110.0], [100.0])
        broker.set_quotes(pd.Timestamp("2024-12-31"), quotes, prev)
        order = broker.submit_order("A", "buy", 100)
        assert order["status"] == "rejected-limit-up"

    def test_limit_down_sell_rejected(self):
        broker = SimulatedBroker(initial_cash=1_000_000.0)
        broker._positions["A"] = {"shares": 1000, "cost_basis": 100.0}
        quotes, prev = _make_quotes(["A"], [90.0], [100.0])
        broker.set_quotes(pd.Timestamp("2024-12-31"), quotes, prev)
        order = broker.submit_order("A", "sell", 100)
        assert order["status"] == "rejected-limit-down"

    def test_insufficient_cash_rejected(self):
        broker = SimulatedBroker(initial_cash=1000.0)
        quotes, prev = _make_quotes(["A"], [100.0], [99.0])
        broker.set_quotes(pd.Timestamp("2024-12-31"), quotes, prev)
        order = broker.submit_order("A", "buy", 1000)
        assert order["status"] == "rejected-insufficient-cash"

    def test_lot_size_validation(self):
        broker = SimulatedBroker()
        with pytest.raises(ValueError, match="multiple of 100"):
            broker.submit_order("A", "buy", 50)

    def test_state_persistence(self, tmp_path):
        db_path = tmp_path / "paper.duckdb"
        settings = type("S", (), {"duckdb_path_abs": db_path, "data_dir_path": tmp_path})()
        store = DuckDBStore(settings)
        broker = SimulatedBroker(initial_cash=500_000.0, store=store)
        broker.connect()
        broker.submit_order("A", "buy", 100)
        broker.disconnect()

        # New broker instance reads persisted state
        broker2 = SimulatedBroker(initial_cash=500_000.0, store=store)
        broker2.connect()
        assert broker2.query_positions()["A"] == 100
        assert broker2.query_cash() < 500_000.0


class TestPaperTradingEngine:
    def test_plan_rebalance(self):
        engine = PaperTradingEngine()
        broker = SimulatedBroker(initial_cash=1_000_000.0)
        broker.connect()
        broker._positions["A"] = {"shares": 500, "cost_basis": 90.0}
        broker._positions["B"] = {"shares": 500, "cost_basis": 90.0}
        quotes, _ = _make_quotes(["A", "B", "C"], [100.0, 100.0, 100.0], [99.0, 99.0, 99.0])
        broker.set_quotes(pd.Timestamp("2024-12-31"), quotes)

        orders = engine._plan_rebalance(broker, ["A", "C"], quotes)
        symbols = {o["symbol"] for o in orders}
        sides = {o["symbol"]: o["side"] for o in orders}
        assert symbols == {"A", "B", "C"}
        assert sides["B"] == "sell"
        # A already held, C new; total value ~1,100,000 -> target ~550k -> 5500 shares
        c_order = [o for o in orders if o["symbol"] == "C"][0]
        assert c_order["side"] == "buy"
        assert c_order["quantity"] == 5500

    def test_reset_clears_state(self, tmp_path):
        db_path = tmp_path / "paper.duckdb"
        settings = type("S", (), {"duckdb_path_abs": db_path, "data_dir_path": tmp_path})()
        engine = PaperTradingEngine(settings=settings)
        engine.reset(cash=2_000_000.0)
        store = DuckDBStore(settings)
        assert store.load_paper_cash() == 2_000_000.0
        assert store.load_paper_positions().empty
