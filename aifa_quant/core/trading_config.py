"""Shared trading configuration for backtest and paper trading."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradingConfig:
    """Common trading parameters used by backtest engine, broker and paper trading."""

    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.001
    min_commission: float = 5.0
    slippage: float = 0.0
    rebalance_freq: int = 5
    top_k: int = 5
