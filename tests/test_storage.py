"""Tests for DuckDB storage."""

import tempfile

import pandas as pd
import pytest

from aifa_quant.config.settings import Settings
from aifa_quant.data.storage import DuckDBStore


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings(data_dir=tmpdir, duckdb_path=f"{tmpdir}/test.duckdb")
        store = DuckDBStore(settings)
        yield store
        store.close()


def test_save_and_load_daily_quotes(temp_store):
    df = pd.DataFrame(
        {
            "symbol": ["000001.SZ", "000001.SZ"],
            "trade_date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [10.0, 10.5],
            "high": [10.2, 10.6],
            "low": [9.9, 10.4],
            "close": [10.1, 10.55],
            "volume": [100000, 150000],
            "amount": [1000000, 1500000],
        }
    )
    rows = temp_store.save_daily_quotes(df)
    assert rows == 2

    loaded = temp_store.load_daily_quotes()
    assert len(loaded) == 2
    assert set(loaded["symbol"].unique()) == {"000001.SZ"}


def test_save_and_load_fundamental_data(temp_store):
    df = pd.DataFrame(
        {
            "symbol": ["000001.SZ", "000001.SZ", "600519.SH"],
            "report_date": pd.to_datetime(["2024-03-31", "2024-06-30", "2024-03-31"]),
            "pe_lyr": [5.0, 5.5, 25.0],
            "pb": [1.0, 1.1, 8.0],
            "roe_ttm": [10.0, 11.0, 20.0],
        }
    )
    rows = temp_store.save_fundamental_data(df)
    assert rows == 3

    loaded = temp_store.load_fundamental_data(symbols=["000001.SZ"], start_date="20240101", end_date="20241231")
    assert len(loaded) == 2
    assert set(loaded["symbol"].unique()) == {"000001.SZ"}


def test_save_and_load_macro_data(temp_store):
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"]),
            "value": [2.1, 2.2, 2.3],
        }
    )
    rows = temp_store.save_macro_data(df, "cpi_yoy")
    assert rows == 3

    loaded = temp_store.load_macro_data("cpi_yoy", start_date="20240101", end_date="20241231")
    assert len(loaded) == 3
    assert loaded["indicator_name"].unique()[0] == "cpi_yoy"


def test_fundamental_data_upsert(temp_store):
    df1 = pd.DataFrame(
        {
            "symbol": ["000001.SZ"],
            "report_date": pd.to_datetime(["2024-03-31"]),
            "pe_lyr": [5.0],
        }
    )
    df2 = pd.DataFrame(
        {
            "symbol": ["000001.SZ"],
            "report_date": pd.to_datetime(["2024-03-31"]),
            "pe_lyr": [6.0],
        }
    )
    temp_store.save_fundamental_data(df1)
    temp_store.save_fundamental_data(df2)
    loaded = temp_store.load_fundamental_data(symbols=["000001.SZ"])
    assert len(loaded) == 1
    assert loaded["pe_lyr"].iloc[0] == pytest.approx(6.0)
