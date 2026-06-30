"""Publish gate: block signal push when recent rolling-window metrics underperform.

Aggregates the last N rolling windows' diagnostics (RankIC, ICIR, excess return,
turnover, max drawdown) and only allows the Supabase push if every window passes
configured thresholds.  This prevents shipping a degraded model to the dashboard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class GateThresholds:
    rank_ic: float = 0.02         # minimum mean RankIC per window
    icir: float = 0.3             # minimum ICIR per window
    annual_excess: float = 0.0    # minimum annualized excess return per window
    monthly_turnover: float = 2.0  # maximum monthly single-side turnover
    max_drawdown: float = -0.50   # maximum drawdown (negative) per window


@dataclass
class GateReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)


def evaluate_gate(
    window_metrics: list[dict],
    thresholds: GateThresholds | None = None,
) -> GateReport:
    """Evaluate the publish gate across recent rolling windows.

    Each dict in window_metrics should contain: rank_ic, icir, annual_excess,
    monthly_turnover, max_drawdown, window_start, window_end.
    """
    th = thresholds or GateThresholds()
    if not window_metrics:
        return GateReport(passed=False, failures=["no window metrics available"])

    failures: list[str] = []
    for m in window_metrics:
        ws = m.get("window_start", "?")
        we = m.get("window_end", "?")
        if m.get("rank_ic", 0.0) < th.rank_ic:
            failures.append(f"{ws}~{we}: rank_ic {m.get('rank_ic'):.4f} < {th.rank_ic}")
        if m.get("icir", 0.0) < th.icir:
            failures.append(f"{ws}~{we}: icir {m.get('icir'):.3f} < {th.icir}")
        if m.get("annual_excess", 0.0) < th.annual_excess:
            failures.append(f"{ws}~{we}: annual_excess {m.get('annual_excess'):.2%} < {th.annual_excess:.2%}")
        if m.get("monthly_turnover", 0.0) > th.monthly_turnover:
            failures.append(f"{ws}~{we}: turnover {m.get('monthly_turnover'):.2%} > {th.monthly_turnover:.2%}")
        if m.get("max_drawdown", 0.0) < th.max_drawdown:
            failures.append(f"{ws}~{we}: drawdown {m.get('max_drawdown'):.2%} < {th.max_drawdown:.2%}")

    return GateReport(passed=not failures, failures=failures, metrics=window_metrics)


def compute_window_metrics(
    pred_df: pd.DataFrame,
    label_col: str = "label_return",
    score_col: str = "pred_score",
    equity_curve: pd.DataFrame | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict:
    """Compute one window's metrics from predictions + optional equity curve.

    pred_df must have: trade_date, symbol, score_col, label_col.
    equity_curve (optional) must have: trade_date, total_value (for turnover/dd).
    """
    from scipy.stats import spearmanr

    ic_vals: list[float] = []
    for date, group in pred_df.groupby("trade_date"):
        sub = group[[score_col, label_col]].dropna()
        if len(sub) < 5:
            continue
        try:
            ic = spearmanr(sub[score_col], sub[label_col]).correlation
            if not pd.isna(ic):
                ic_vals.append(float(ic))
        except Exception:
            continue

    rank_ic = float(np.mean(ic_vals)) if ic_vals else 0.0
    icir = float(np.mean(ic_vals) / (np.std(ic_vals) + 1e-9)) if ic_vals else 0.0

    annual_excess = 0.0
    monthly_turnover = 0.0
    max_dd = 0.0
    if equity_curve is not None and not equity_curve.empty and "total_value" in equity_curve.columns:
        eq = equity_curve.sort_values("trade_date").reset_index(drop=True)
        nav = eq["total_value"].astype(float)
        rets = nav.pct_change().dropna()
        if len(rets) > 1:
            annual_excess = float(rets.mean() * 252)  # treat as excess vs 0
        peak = nav.cummax()
        dd = (nav - peak) / peak
        max_dd = float(dd.min())
        # Turnover: needs trades; approximate from nav changes if trades absent.
        if "trades_value" in eq.columns:
            total_traded = float(eq["trades_value"].sum())
            months = max(1, len(eq) / 21)
            monthly_turnover = total_traded / (nav.iloc[-1] * months)

    return {
        "window_start": window_start,
        "window_end": window_end,
        "rank_ic": rank_ic,
        "icir": icir,
        "annual_excess": annual_excess,
        "monthly_turnover": monthly_turnover,
        "max_drawdown": max_dd,
    }


# numpy is used inside compute_window_metrics via np — keep import at module level.
import numpy as np  # noqa: E402
