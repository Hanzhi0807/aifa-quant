"""Tests for backtest engine."""

import pandas as pd

from aifa_quant.backtest import BacktestEngine, compute_metrics
from aifa_quant.backtest.engine import Position


def test_position_dataclass():
    pos = Position("000001.SZ", shares=100, cost_basis=10.0)
    assert pos.symbol == "000001.SZ"
    assert pos.shares == 100


def test_backtest_engine_simple_run():
    engine = BacktestEngine(initial_cash=100000)
    engine.positions["A"] = Position("A", shares=100, cost_basis=10.0)
    engine.cash = 90000

    quotes = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "symbol": ["A", "A"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [11.0, 12.0],
            "volume": [1000, 1000],
        }
    )
    engine._record_value(pd.Timestamp("2024-01-01"), quotes[quotes["trade_date"] == "2024-01-01"])
    engine._record_value(pd.Timestamp("2024-01-02"), quotes[quotes["trade_date"] == "2024-01-02"])

    equity = pd.DataFrame(engine.daily_values)
    metrics = compute_metrics(equity)
    assert metrics["total_return"] > 0


def test_compute_metrics_empty():
    metrics = compute_metrics(pd.DataFrame())
    assert metrics == {}
