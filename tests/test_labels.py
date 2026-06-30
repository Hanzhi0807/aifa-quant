"""Tests for label construction."""

import pandas as pd
import pytest

from aifa_quant.features.labels import compute_labels


def _make_df() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=10)
    symbols = ["A", "B", "C", "D", "E"]
    rows = []
    for symbol in symbols:
        for i, date in enumerate(dates):
            close = 10.0 + i + (ord(symbol[0]) - ord("A")) * 0.5
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": date,
                    "open": close,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": 1000,
                    "amount": close * 1000,
                }
            )
    return pd.DataFrame(rows)


def test_compute_labels_binary():
    df = _make_df()
    result = compute_labels(df, label_type="binary", label_horizon=2)
    assert "label_return" in result.columns
    assert "label_binary" in result.columns
    assert "label_rank" in result.columns
    assert result["label_binary"].isin([0, 1]).all()
    assert result["label_rank"].equals(result["label_binary"])


def test_compute_labels_excess_quantile():
    df = _make_df()
    result = compute_labels(df, label_type="excess_quantile", label_horizon=2)
    assert "label_return" in result.columns
    assert "label_excess" in result.columns
    assert "label_rank" in result.columns
    assert "label_binary" in result.columns
    ranks = result["label_rank"].dropna()
    assert ranks.isin([0, 1, 2]).all()


def test_compute_labels_excess_quantile_drop_middle():
    df = _make_df()
    result = compute_labels(df, label_type="excess_quantile", label_horizon=2, drop_middle=True)
    ranks = result["label_rank"].dropna()
    assert ranks.isin([0, 2]).all()
    assert not ranks.eq(1).any()


def test_compute_labels_excess_quantile_cost():
    df = _make_df()
    result = compute_labels(df, label_type="excess_quantile", label_horizon=2, cost=0.0008)
    # Cross-sectional median excess should be close to -cost for dates with valid labels.
    for date, group in result.groupby("trade_date"):
        if len(group) >= 5 and not group["label_excess"].isna().all():
            assert group["label_excess"].median() == pytest.approx(-0.0008, abs=1e-6)


def test_compute_labels_triple_barrier():
    df = _make_df()
    df["atr_14"] = 0.5
    result = compute_labels(df, label_type="triple_barrier", label_horizon=2, pt_mult=2.0, sl_mult=1.0, max_holding=3)
    assert "label_return" in result.columns
    assert "label_outcome" in result.columns
    assert "label_rank" in result.columns
    assert "label_binary" in result.columns
    ranks = result["label_rank"].dropna()
    assert ranks.isin([0, 1, 2]).all()
    outcomes = result["label_outcome"].dropna()
    assert outcomes.isin([-1, 0, 1]).all()


def test_compute_labels_triple_barrier_falls_back_without_atr():
    df = _make_df().drop(columns=["high", "low"])
    # compute_atr would not be called, so atr_14 is missing.
    with pytest.warns(UserWarning):
        result = compute_labels(df, label_type="triple_barrier", label_horizon=2)
    assert "label_rank" in result.columns


def test_compute_labels_unknown_type_raises():
    df = _make_df()
    with pytest.raises(ValueError, match="Unknown label_type"):
        compute_labels(df, label_type="unknown")
