"""Tests for AkShare macro fallback normalization."""

import pandas as pd
import pytest

from aifa_quant.data.adapters.akshare_adapter import AkShareAdapter


def test_get_macro_data_normalizes_cpi_frame():
    class FakeAk:
        def macro_china_cpi_yearly(self):
            return pd.DataFrame({"date": ["2024-01-01", "2024-02-01"], "actual": ["2.0%", "2.5%"]})

    adapter = AkShareAdapter.__new__(AkShareAdapter)
    adapter._ak = FakeAk()

    result = adapter.get_macro_data("cpi_yoy", start_date="20240115", end_date="20241231")

    assert list(result.columns) == ["trade_date", "value"]
    assert result["trade_date"].tolist() == [pd.Timestamp("2024-02-01")]
    assert result["value"].iloc[0] == pytest.approx(2.5)


def test_get_macro_data_uses_money_supply_m2_yoy_column_fallback():
    class FakeAk:
        def macro_china_money_supply(self):
            return pd.DataFrame({"month": ["2024-01"], "m2_amount": [1000.0], "m2_yoy": ["8.7"]})

    adapter = AkShareAdapter.__new__(AkShareAdapter)
    adapter._ak = FakeAk()

    result = adapter.get_macro_data("m2_yoy", start_date="20240101", end_date="20241231")

    assert result["trade_date"].iloc[0] == pd.Timestamp("2024-01-01")
    assert result["value"].iloc[0] == pytest.approx(8.7)
