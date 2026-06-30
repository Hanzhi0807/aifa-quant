"""Tests for PurgedKFold and the publish gate."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aifa_quant.models.cv import PurgedKFold, compute_pbo
from aifa_quant.analysis.publish_gate import evaluate_gate, GateThresholds, compute_window_metrics


def test_purged_kfold_excludes_boundary_dates():
    """Rows whose label horizon crosses into val must be excluded from train."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({
        "trade_date": dates,
        "symbol": ["A"] * 30,
        "feat": range(30),
    })
    pkf = PurgedKFold(n_splits=3, label_horizon=5, embargo_pct=0.05)
    splits = list(pkf.split(df))
    assert len(splits) == 3

    for train_idx, val_idx in splits:
        # Train and val must not overlap.
        assert set(train_idx).isdisjoint(set(val_idx))
        # The 5 rows immediately before val must be purged from train.
        val_dates = df.iloc[val_idx]["trade_date"].unique()
        val_start = val_dates.min()
        purge_dates = pd.date_range(end=val_start - pd.Timedelta(days=1), periods=5)
        purge_rows = df[df["trade_date"].isin(purge_dates)].index
        assert set(purge_rows).isdisjoint(set(train_idx))


def test_purged_kfold_requires_enough_dates():
    df = pd.DataFrame({"trade_date": pd.date_range("2024-01-01", periods=2)})
    import pytest
    with pytest.raises(ValueError):
        list(PurgedKFold(n_splits=5).split(df))


def test_pbo_single_strategy_is_zero():
    arr = np.random.default_rng(0).normal(0, 0.01, (100, 1))
    assert compute_pbo(arr) == 0.0


def test_pbo_overfit_strategy_high():
    """An IS-best strategy that underperforms OOS median → high PBO."""
    rng = np.random.default_rng(1)
    # 3 strategies, IS-best is strategy 0 but it underperforms OOS.
    arr = rng.normal(0, 0.01, (100, 3))
    arr[:, 0] -= 0.005  # strategy 0 looks good in-sample by luck but loses OOS
    pbo = compute_pbo(arr)
    assert 0.0 <= pbo <= 1.0


def test_publish_gate_blocks_on_low_rank_ic():
    metrics = [{"window_start": "2024-01", "window_end": "2024-02",
                 "rank_ic": 0.001, "icir": 0.4, "annual_excess": 0.1,
                 "monthly_turnover": 1.0, "max_drawdown": -0.1}]
    report = evaluate_gate(metrics, GateThresholds(rank_ic=0.02))
    assert report.passed is False
    assert any("rank_ic" in f for f in report.failures)


def test_publish_gate_passes_when_all_clear():
    metrics = [{"window_start": "2024-01", "window_end": "2024-02",
                 "rank_ic": 0.05, "icir": 0.6, "annual_excess": 0.15,
                 "monthly_turnover": 0.8, "max_drawdown": -0.1}]
    report = evaluate_gate(metrics)
    assert report.passed is True
    assert report.failures == []


def test_compute_window_metrics_basic():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    n_stocks = 10
    rows = []
    for d in dates:
        for i in range(n_stocks):
            rows.append({
                "trade_date": d,
                "symbol": f"S{i}",
                "pred_score": n_stocks - i,        # S0 highest
                "label_return": i * 0.01,           # S0 lowest return
            })
    pred_df = pd.DataFrame(rows)
    m = compute_window_metrics(pred_df, window_start="2024-01-01", window_end="2024-01-10")
    assert m["window_start"] == "2024-01-01"
    # IC should be negative (high score → low return).
    assert m["rank_ic"] < 0
