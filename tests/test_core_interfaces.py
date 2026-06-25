"""Tests for core interface abstractions."""

import inspect

import pytest

from aifa_quant.core.interfaces import BaseBroker, BaseDataSource, BaseModel, BaseStrategy
from aifa_quant.execution.broker.simulated_broker import SimulatedBroker


def test_base_model_is_abstract():
    assert inspect.isabstract(BaseModel)
    with pytest.raises(TypeError):
        BaseModel()  # type: ignore[abstract]


def test_base_strategy_is_abstract():
    assert inspect.isabstract(BaseStrategy)
    with pytest.raises(TypeError):
        BaseStrategy()  # type: ignore[abstract]


def test_base_data_source_is_abstract():
    assert inspect.isabstract(BaseDataSource)
    with pytest.raises(TypeError):
        BaseDataSource()  # type: ignore[abstract]


def test_base_broker_is_abstract():
    assert inspect.isabstract(BaseBroker)
    with pytest.raises(TypeError):
        BaseBroker()  # type: ignore[abstract]


def test_simulated_broker_lifecycle():
    broker = SimulatedBroker(initial_cash=1_000_000.0)
    broker.connect()
    assert broker.query_cash() == 1_000_000.0
    assert broker.query_positions() == {}
    broker.disconnect()


def test_simulated_broker_order():
    broker = SimulatedBroker(initial_cash=1_000_000.0)
    broker.connect()
    order = broker.submit_order("600519.SH", "buy", 100)
    assert order["status"] == "filled"
    assert broker.query_positions()["600519.SH"] == 100
    orders = broker.query_orders()
    assert len(orders) == 1
