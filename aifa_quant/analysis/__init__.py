"""Analysis tools for factors, models, and strategies."""

from .factor_analysis import (
    compute_factor_decay,
    compute_ic_summary,
    compute_quantile_returns,
    plot_ic_distribution,
    plot_quantile_returns,
)
from .shap_explainer import explain_model

__all__ = [
    "compute_ic_summary",
    "compute_quantile_returns",
    "compute_factor_decay",
    "plot_ic_distribution",
    "plot_quantile_returns",
    "explain_model",
]
