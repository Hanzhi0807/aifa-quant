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
