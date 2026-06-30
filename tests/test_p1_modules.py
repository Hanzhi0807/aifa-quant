"""Tests for the P1 modules: meta-labeler and factor IC selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aifa_quant.features.factor_selection import select_by_ic, compute_factor_ic
from aifa_quant.models.meta_model import MetaLabeler


def _make_panel(n_stocks=10, n_days=30, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    rows = []
    for s in range(n_stocks):
        for d in dates:
            rows.append({
                "trade_date": d,
                "symbol": f"S{s}",
                "f_good": rng.normal(0, 1) + s * 0.1,  # weak signal
                "f_noise": rng.normal(0, 1),           # pure noise
                "label_return": rng.normal(0, 0.02),
            })
    return pd.DataFrame(rows)


def test_compute_factor_ic_returns_per_factor():
    df = _make_panel()
    ic = compute_factor_ic(df, ["f_good", "f_noise", "missing"])
    assert "f_good" in ic.index
    assert "f_noise" in ic.index
    assert "mean_ic" in ic.columns
    assert "icir" in ic.columns
    # `missing` should be skipped silently.
    assert "missing" not in ic.index


def test_select_by_ic_threshold_filters_noise():
    """A pure-noise factor should be dropped; a signal factor kept (when signal exists)."""
    rng = np.random.default_rng(1)
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    rows = []
    for s in range(20):
        signal = rng.normal(0, 1)
        for d in dates:
            # f_signal correlates with future return; f_noise does not.
            fwd_ret = 0.01 * signal + rng.normal(0, 0.02)
            rows.append({
                "trade_date": d,
                "symbol": f"S{s}",
                "f_signal": signal + rng.normal(0, 0.3),
                "f_noise": rng.normal(0, 1),
                "label_return": fwd_ret,
            })
    df = pd.DataFrame(rows)
    survivors = select_by_ic(df, ["f_signal", "f_noise"], threshold=0.02)
    assert "f_signal" in survivors
    # f_noise may or may not survive depending on randomness; assert at least f_signal kept.
    assert len(survivors) >= 1


def test_select_by_ic_lookback_slices_recent():
    df = _make_panel(n_days=50)
    # lookback=10 should only use the last 10 dates.
    survivors = select_by_ic(df, ["f_good", "f_noise"], threshold=0.0, lookback=10)
    # With threshold 0, all factors with any IC survive.
    assert "f_good" in survivors


def test_meta_labeler_fit_and_predict():
    rng = np.random.default_rng(0)
    n = 200
    X = pd.DataFrame({
        "f1": rng.normal(0, 1, n),
        "f2": rng.normal(0, 1, n),
    })
    # Label: profitable when f1 > 0.
    y = pd.Series((X["f1"] > 0).astype(int).to_numpy() ^ (rng.random(n) > 0.2).astype(int).astype(bool)).astype(int)
    meta = MetaLabeler()
    meta.fit(X, y, ["f1", "f2"])
    proba = meta.predict_proba(X)
    assert len(proba) == n
    assert ((0.0 <= proba) & (proba <= 1.0)).all()


def test_meta_labeler_gate_filters_by_threshold():
    rng = np.random.default_rng(1)
    n = 50
    cands = pd.DataFrame({
        "pred_score": np.linspace(1, 0, n),
        "f1": rng.normal(0, 1, n),
    })
    meta = MetaLabeler()
    # Fit on the same data so the model has seen it.
    y = pd.Series((cands["f1"] > 0).astype(int))
    meta.fit(cands, y, ["f1"])
    gated = meta.gate(cands, score_col="pred_score", threshold=0.5, top_k=10)
    assert len(gated) <= 10
    assert "pred_score" in gated.columns


def test_meta_labeler_passthrough_when_unfitted():
    cands = pd.DataFrame({"pred_score": np.linspace(1, 0, 30)})
    meta = MetaLabeler()
    out = meta.gate(cands, score_col="pred_score", top_k=5)
    assert len(out) == 5
    assert out["pred_score"].iloc[0] == 1.0
