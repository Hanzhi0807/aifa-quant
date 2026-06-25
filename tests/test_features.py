"""Basic tests for feature engineering."""

import pandas as pd
import pytest

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
