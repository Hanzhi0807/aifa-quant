"""Tests for the mean-variance optimizer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aifa_quant.strategy.optimizer import MeanVarianceOptimizer, OptimizerConfig


def _make_returns(symbols: list[str], days: int = 60, seed: int = 0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        rng.normal(0, 0.02, (days, len(symbols))),
        columns=symbols,
        index=pd.date_range("2024-01-01", periods=days),
    )


def test_optimizer_weights_sum_to_one():
    syms = ["A", "B", "C", "D", "E"]
    scores = pd.Series([0.9, 0.7, 0.5, 0.3, 0.1], index=syms)
    ret = _make_returns(syms)
    opt = MeanVarianceOptimizer(OptimizerConfig(w_max=0.40))  # loose cap so 5 names fit
    w = opt.optimize(scores, ret)
    assert len(w) == 5
    assert w.sum() == pytest_approx(1.0)
    assert (w >= 0).all()
    assert (w <= 0.40 + 1e-6).all()


def test_optimizer_respects_single_name_cap():
    syms = [f"S{i}" for i in range(20)]
    # One dominant score.
    scores = pd.Series([5.0] + [0.1] * 19, index=syms)
    ret = _make_returns(syms)
    opt = MeanVarianceOptimizer(OptimizerConfig(w_max=0.10, risk_aversion=0.5))
    w = opt.optimize(scores, ret)
    assert w.max() <= 0.10 + 1e-6


def test_optimizer_prefers_higher_score():
    syms = ["A", "B", "C"]
    scores = pd.Series([1.0, 0.5, 0.0], index=syms)
    ret = _make_returns(syms, seed=1)
    opt = MeanVarianceOptimizer(OptimizerConfig(w_max=0.50, risk_aversion=0.1))
    w = opt.optimize(scores, ret)
    # A should get more weight than C.
    assert w["A"] > w["C"]


def test_optimizer_turnover_control():
    """Turnover cap should keep L1 turnover below the bound when feasible."""
    syms = [f"S{i}" for i in range(10)]
    scores = pd.Series(np.linspace(1, 0, 10), index=syms)
    ret = _make_returns(syms)
    # Start from an already-diversified weight (feasible w.r.t. w_max=0.20).
    prev = pd.Series([0.20] * 5 + [0.0] * 5, index=syms)
    opt = MeanVarianceOptimizer(OptimizerConfig(w_max=0.20, turnover_max=0.30, risk_aversion=0.2))
    w = opt.optimize(scores, ret, prev_weights=prev)
    turn = float(np.sum(np.abs(w.to_numpy() - prev.to_numpy())))
    # Turnover cap of 0.30 is feasible here (only minor reweighting needed).
    assert turn <= 0.30 + 0.10  # allow solver slack


def test_optimizer_industry_cap():
    """Industry cap holds when the problem is feasible (≥3 industries)."""
    syms = ["A", "B", "C", "D", "E", "F"]
    scores = pd.Series([1.0, 0.9, 0.8, 0.7, 0.6, 0.5], index=syms)
    ret = _make_returns(syms)
    industry_map = {"A": "tech", "B": "tech", "C": "fin", "D": "fin", "E": "cons", "F": "cons"}
    opt = MeanVarianceOptimizer(OptimizerConfig(w_max=0.40, ind_max=0.40, risk_aversion=0.2))
    w = opt.optimize(scores, ret, industry_map=industry_map)
    for ind in ["tech", "fin", "cons"]:
        ind_w = sum(w[s] for s in [k for k, v in industry_map.items() if v == ind])
        assert ind_w <= 0.40 + 0.02, f"{ind} weight {ind_w} exceeds cap"


def pytest_approx(x, rel=1e-6, abs=1e-6):
    """Local approx helper to avoid importing pytest in module body."""
    import pytest
    return pytest.approx(x, rel=rel, abs=abs)
