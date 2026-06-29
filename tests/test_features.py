"""Basic tests for feature engineering."""

import pandas as pd
import pytest

from aifa_quant.features.alpha_factors import compute_alpha_factors
from aifa_quant.features.fundamental import merge_fundamental_to_daily
from aifa_quant.features.macro import merge_macro_to_daily
from aifa_quant.features.technical import (
    compute_moving_averages,
    compute_returns,
    compute_rsi,
)


def test_compute_returns():
    df = pd.DataFrame(
        {
            "close": [10.0, 11.0, 12.0, 11.0, 13.0],
        }
    )
    result = compute_returns(df)
    assert "return_1d" in result.columns
    assert "future_return_1d" in result.columns
    assert result["return_1d"].iloc[1] == pytest.approx(0.1)


def test_compute_moving_averages():
    df = pd.DataFrame(
        {
            "close": [10.0] * 20,
        }
    )
    result = compute_moving_averages(df)
    assert "ma_5" in result.columns
    assert "close_to_ma_5" in result.columns


def test_compute_rsi():
    df = pd.DataFrame(
        {
            "close": [10.0, 11.0, 12.0, 11.0, 12.0, 13.0, 14.0, 13.0, 14.0, 15.0],
        }
    )
    result = compute_rsi(df)
    assert "rsi_14" in result.columns
    assert result["rsi_14"].iloc[-1] >= 0

def test_compute_rsi_all_gains_returns_100():
    df = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0, 14.0]})
    result = compute_rsi(df, window=3)
    assert result["rsi_3"].iloc[-1] == pytest.approx(100.0)


def test_alpha_rank_is_cross_sectional():
    df = pd.DataFrame(
        {
            "symbol": ["A", "B"],
            "trade_date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
            "open": [10.0, 10.0],
            "high": [12.0, 12.0],
            "low": [9.0, 9.0],
            "close": [11.0, 9.0],
            "volume": [1000, 1000],
            "amount": [11000.0, 9000.0],
        }
    )
    result = compute_alpha_factors(df, selected=["alpha009"])
    scores = result.set_index("symbol")["alpha009"]
    assert scores["A"] == pytest.approx(-1.0)
    assert scores["B"] == pytest.approx(-0.5)


def test_fundamental_merge_uses_delayed_availability_without_ann_date():
    daily = pd.DataFrame(
        {
            "symbol": ["A", "A"],
            "trade_date": pd.to_datetime(["2024-04-15", "2024-07-01"]),
            "close": [10.0, 11.0],
        }
    )
    financial = pd.DataFrame(
        {
            "symbol": ["A"],
            "report_date": pd.to_datetime(["2024-03-31"]),
            "pe_lyr": [12.0],
        }
    )
    result = merge_fundamental_to_daily(daily, financial)
    assert pd.isna(result.loc[result["trade_date"] == pd.Timestamp("2024-04-15"), "pe_lyr"].iloc[0])
    assert result.loc[result["trade_date"] == pd.Timestamp("2024-07-01"), "pe_lyr"].iloc[0] == pytest.approx(12.0)


def test_macro_merge_applies_publication_delay():
    daily = pd.DataFrame(
        {
            "symbol": ["A", "A"],
            "trade_date": pd.to_datetime(["2024-01-15", "2024-02-05"]),
            "close": [10.0, 11.0],
        }
    )
    macro = pd.DataFrame({"trade_date": pd.to_datetime(["2024-01-01"]), "value": [2.0]})
    result = merge_macro_to_daily(daily, macro, "cpi_yoy")
    assert pd.isna(result.loc[result["trade_date"] == pd.Timestamp("2024-01-15"), "cpi_yoy"].iloc[0])
    assert result.loc[result["trade_date"] == pd.Timestamp("2024-02-05"), "cpi_yoy"].iloc[0] == pytest.approx(2.0)
