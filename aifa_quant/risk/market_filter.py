"""Market oscillation detector — skip rebalancing in choppy markets.

Uses polynomial fit residuals: larger residuals → more oscillation.
Based on abu's AbuSDBreak / AbuLeastPolyWrap pattern.
"""

import numpy as np
import pandas as pd


def detect_oscillation(
    benchmark_close: pd.Series,
    window: int = 20,
    poly_degree: int = 2,
    poly_threshold: float = 0.02,
    verbose: bool = False,
) -> tuple[bool, float]:
    """Detect whether the benchmark is oscillating (choppy / sideways).

    Args:
        benchmark_close: Close prices of the benchmark (e.g., CSI 300).
        window: Lookback window in trading days.
        poly_degree: Degree of polynomial fit.
        poly_threshold: If the normalized residual exceeds this, consider oscillating.

    Returns:
        (is_oscillating, confidence) — True if the market looks choppy.
    """
    if len(benchmark_close) < window:
        return False, 0.0

    recent = benchmark_close.iloc[-window:].values.astype(float)
    if recent[0] == 0:
        return False, 0.0

    # Normalize to start at 1.0
    normalized = recent / recent[0]
    x = np.arange(len(normalized))

    # Polynomial fit
    coeffs = np.polyfit(x, normalized, min(poly_degree, len(normalized) - 1))
    poly = np.poly1d(coeffs)
    fitted = poly(x)

    # Residual = how much the real price deviates from the smooth fit
    residuals = np.abs(normalized - fitted)
    mean_residual = float(np.mean(residuals))

    is_oscillating = mean_residual > poly_threshold

    if verbose:
        print(
            f"[market_filter] {window}d oscillation check: "
            f"residual={mean_residual:.4f} threshold={poly_threshold} → "
            f"{'CHOPPY' if is_oscillating else 'trending'}"
        )

    return is_oscillating, mean_residual
