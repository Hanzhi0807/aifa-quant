"""Tests for backtest engine."""

import pandas as pd
import pytest

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

class _SinglePickStrategy:
    def generate_signals(self, features, current_date, hold_symbols=None, **kwargs):
        day = features[features["trade_date"] == current_date].copy()
        day["rank"] = 1
        day["selected"] = day["symbol"] == "A"
        return day[["symbol", "pred_score", "rank", "selected"]].rename(columns={"pred_score": "score"})


def test_backtest_executes_signal_next_day_open():
    engine = BacktestEngine(initial_cash=10_000.0, commission_rate=0.0, min_commission=0.0, rebalance_freq=5)
    quotes = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "symbol": ["A", "A"],
            "open": [10.0, 20.0],
            "high": [110.0, 26.0],
            "low": [9.0, 19.0],
            "close": [100.0, 25.0],
            "volume": [1000, 1000],
        }
    )
    features = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-01"]),
            "symbol": ["A"],
            "pred_score": [1.0],
        }
    )

    equity = engine.run(quotes, features, model=None, strategy=_SinglePickStrategy())

    assert len(equity) == 2
    assert len(engine.trades) == 1
    trade = engine.trades[0]
    assert trade.trade_date == pd.Timestamp("2024-01-02")
    assert trade.price == pytest.approx(20.0)


def test_sell_all_forces_exit_even_at_limit_down():
    engine = BacktestEngine(initial_cash=0.0, commission_rate=0.0, stamp_duty_rate=0.0, min_commission=0.0)
    engine.positions["A"] = Position("A", shares=100, cost_basis=10.0)
    engine.prev_day_quotes = pd.DataFrame({"symbol": ["A"], "close": [10.0]})
    day_quotes = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-02"]),
            "symbol": ["A"],
            "open": [9.0],
            "high": [9.2],
            "low": [9.0],
            "close": [9.0],
            "volume": [1000],
        }
    )

    engine._sell_all(pd.Timestamp("2024-01-02"), day_quotes, "A", price_col="open")

    assert "A" not in engine.positions
    assert engine.cash == pytest.approx(900.0)
