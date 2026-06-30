"""Constrained mean-variance portfolio optimizer.

Replaces the equal-weight / vol-target rebalancer with a QP-style optimizer
that respects single-name caps, industry caps, turnover limits and a target
volatility.  Solves via scipy.optimize.minimize (SLSQP) so we avoid the cvxpy
dependency.

Objective (L2 turnover penalty — smooth, solvable by SLSQP):

    max  μᵀw − λ·wᵀΣw − c·‖w − w_prev‖₂²
    s.t.  Σw = 1
          0 ≤ w_i ≤ w_max              (single-name cap, default 5%)
          Σ_{i∈ind} w_i ≤ ind_max      (per-industry cap, default 25%)
          ‖w − w_prev‖₁ ≤ τ_max        (turnover cap, default 40%)
          sqrt(wᵀΣw · 252) ≤ σ_target  (annualized vol cap, default 20%)

``μ`` is the model score (cross-sectionally ranked then normalized).
``Σ`` is a Ledoit-Wolf shrunk covariance of recent daily returns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class OptimizerConfig:
    risk_aversion: float = 1.0          # λ
    turnover_cost: float = 0.005        # c (per unit of L2 turnover)
    w_max: float = 0.05                 # single-name cap
    ind_max: float = 0.25               # per-industry cap
    turnover_max: float = 0.40          # τ_max (L1 turnover cap)
    target_vol: float = 0.20            # annualized
    lookback: int = 60                  # days for covariance estimation


class MeanVarianceOptimizer:
    """Constrained mean-variance optimizer using scipy SLSQP."""

    def __init__(self, config: OptimizerConfig | None = None):
        self.config = config or OptimizerConfig()

    def optimize(
        self,
        scores: pd.Series,          # symbol -> model score
        returns_df: pd.DataFrame,   # wide form: index=date, columns=symbol, values=daily return
        prev_weights: pd.Series | None = None,
        industry_map: dict[str, str] | None = None,
    ) -> pd.Series:
        """Return target weights (symbol -> weight) summing to 1.

        Args:
            scores: Cross-sectional model scores for candidate symbols.
            returns_df: Recent daily returns wide-format for covariance estimation.
            prev_weights: Current portfolio weights (for turnover control). None → equal.
            industry_map: symbol -> industry, for industry caps.
        """
        symbols = list(scores.index)
        n = len(symbols)
        if n == 0:
            return pd.Series(dtype=float)

        mu = self._normalize_scores(scores.reindex(symbols).fillna(0.0))
        Sigma = self._estimate_covariance(returns_df, symbols)
        w0 = np.full(n, 1.0 / n)
        if prev_weights is not None:
            w_prev = prev_weights.reindex(symbols).fillna(0.0).to_numpy()
        else:
            w_prev = np.zeros(n)

        cfg = self.config

        def neg_utility(w: np.ndarray) -> float:
            ret = float(mu @ w)
            risk = float(w @ Sigma @ w)
            turn = float(np.sum((w - w_prev) ** 2))
            return -(ret - cfg.risk_aversion * risk - cfg.turnover_cost * turn)

        def grad(w: np.ndarray) -> np.ndarray:
            ret_g = mu.to_numpy()
            risk_g = 2.0 * (Sigma @ w)
            turn_g = 2.0 * cfg.turnover_cost * (w - w_prev)
            return -(ret_g - cfg.risk_aversion * risk_g - turn_g)

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)},
        ]
        # Target vol cap (annualized): sqrt(wᵀΣw * 252) ≤ target_vol
        if cfg.target_vol > 0:
            constraints.append({
                "type": "ineq",
                "fun": lambda w: cfg.target_vol ** 2 - float(w @ Sigma @ w) * 252,
                "jac": lambda w: -2.0 * 252 * (Sigma @ w),
            })
        # Turnover cap (L1): ||w - w_prev||_1 ≤ turnover_max
        if cfg.turnover_max > 0 and w_prev.any():
            constraints.append({
                "type": "ineq",
                "fun": lambda w: cfg.turnover_max - np.sum(np.abs(w - w_prev)),
            })

        bounds = [(0.0, cfg.w_max)] * n

        # Industry caps: for each industry, Σ_{i∈ind} w_i ≤ ind_max
        if industry_map and cfg.ind_max > 0:
            ind_of = [industry_map.get(s, "unknown") for s in symbols]
            for ind in set(ind_of):
                mask = np.array([i == ind for i in ind_of], dtype=float)
                constraints.append({
                    "type": "ineq",
                    "fun": (lambda w, m=mask: cfg.ind_max - float(m @ w)),
                })

        result = minimize(
            neg_utility, w0, jac=grad, method="SLSQP",
            bounds=bounds, constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-9},
        )
        if not result.success:
            # Retry from equal-weight without the jac (sometimes more robust).
            result = minimize(
                neg_utility, w0, method="SLSQP",
                bounds=bounds, constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-9},
            )
        if not result.success:
            logger.warning("Optimizer did not fully converge: %s", result.message)

        w = result.x
        # Clean tiny negatives from numerical error.
        w = np.clip(w, 0.0, None)

        # Post-hoc projection for constraints SLSQP may not have satisfied.
        # Single-name cap.
        w = np.minimum(w, cfg.w_max)
        # Industry cap: scale down any over-budget industry, redistribute freed
        # weight to symbols in non-over-budget industries (proportionally).
        if industry_map and cfg.ind_max > 0:
            ind_of = np.array([industry_map.get(s, "unknown") for s in symbols])
            for _ in range(5):  # iterate; redistributing may push others over
                over = False
                for ind in set(ind_of):
                    mask = ind_of == ind
                    total_ind = float(w[mask].sum())
                    if total_ind > cfg.ind_max + 1e-9:
                        freed = total_ind - cfg.ind_max
                        w[mask] *= cfg.ind_max / total_ind
                        # Distribute freed weight to non-this-industry symbols under their cap.
                        others = ~mask
                        room = np.maximum(cfg.w_max - w, 0.0) * others
                        room_sum = float(room.sum())
                        if room_sum > 0:
                            w += room * (freed / room_sum)
                        over = True
                if not over:
                    break
        total = w.sum()
        if total > 0:
            w = w / total
        return pd.Series(w, index=symbols)

    @staticmethod
    def _normalize_scores(scores: pd.Series) -> pd.Series:
        """Rank-normalize scores to [0, 1] so μ has a comparable scale to risk."""
        if scores.empty:
            return scores
        ranked = scores.rank(method="average", pct=True)
        return ranked - 0.5  # center around 0, range ≈ [-0.5, 0.5]

    def _estimate_covariance(self, returns_df: pd.DataFrame, symbols: list[str]) -> np.ndarray:
        """Ledoit-Wolf shrunk covariance of recent daily returns.

        Falls back to diagonal (variance-only) if too few observations.
        """
        n = len(symbols)
        if returns_df is None or returns_df.empty:
            return np.eye(n) * 0.04 / 252  # 20% annual vol placeholder

        avail = [s for s in symbols if s in returns_df.columns]
        if len(avail) < 2:
            return np.eye(n) * 0.04 / 252

        sub = returns_df[avail].tail(self.config.lookback).dropna(axis=1, how="all")
        if sub.shape[1] < 2 or sub.shape[0] < 5:
            return np.eye(n) * 0.04 / 252

        ret = sub.fillna(0.0).to_numpy()
        sample = np.cov(ret, rowvar=False)
        # Ledoit-Wolf-style shrinkage toward diagonal average variance.
        avg_var = np.mean(np.diag(sample))
        target = np.eye(sample.shape[0]) * avg_var
        # Shrinkage intensity — heuristic 0.1 (light). Real LW would estimate it.
        shrink = 0.1
        cov_shrunk = shrink * target + (1 - shrink) * sample

        # Map back to full symbol set (fill missing with avg_var).
        full = np.eye(n) * (avg_var if avg_var > 0 else 0.04 / 252)
        avail_idx = [symbols.index(s) for s in sub.columns]
        for ii, i in enumerate(avail_idx):
            for jj, j in enumerate(avail_idx):
                full[i, j] = cov_shrunk[ii, jj]
        return full
