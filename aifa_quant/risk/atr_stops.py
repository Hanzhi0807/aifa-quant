"""Three-layer ATR stop-loss / take-profit system inspired by abu.

Layer 1 — Basic stop: stop-loss at N×ATR loss, take-profit at M×ATR gain.
Layer 2 — Crash stop: single-day drop exceeding X×ATR triggers immediate stop.
Layer 3 — Drawdown stop: profit drawdown from peak exceeding Y×ATR locks profit.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StopSignal:
    symbol: str
    type: str  # "stop_loss" | "take_profit" | "crash_stop" | "drawdown_stop"
    reason: str
    current_price: float
    trigger_price: float


class ATRStopManager:
    """Manage stop-loss / take-profit signals for current positions."""

    def __init__(
        self,
        stop_loss_atr: float = 1.0,
        stop_win_atr: float = 3.0,
        crash_atr: float = 1.5,
        drawdown_atr: float = 1.5,
        atr_window: int = 14,
    ):
        self.stop_loss_atr = stop_loss_atr
        self.stop_win_atr = stop_win_atr
        self.crash_atr = crash_atr
        self.drawdown_atr = drawdown_atr
        self.atr_window = atr_window

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check_all(
        self,
        symbol: str,
        position_shares: int,
        cost_basis: float,
        daily_quotes: pd.DataFrame,
        prev_close: float | None = None,
    ) -> list[StopSignal]:
        """Run all three layers and return any triggered stop signals."""
        if position_shares <= 0:
            return []

        atr = self._compute_atr(daily_quotes, self.atr_window)
        if atr is None or atr <= 0:
            return []

        current_price = float(daily_quotes.iloc[-1]["close"])

        signals: list[StopSignal] = []

        s = self._check_basic_stop(symbol, cost_basis, current_price, atr)
        if s:
            signals.append(s)

        s = self._check_crash_stop(symbol, current_price, atr, prev_close)
        if s:
            signals.append(s)

        s = self._check_drawdown_stop(symbol, cost_basis, daily_quotes, atr)
        if s:
            signals.append(s)

        return signals

    # ------------------------------------------------------------------
    # Layer 1 — Basic stop-loss / take-profit
    # ------------------------------------------------------------------
    def _check_basic_stop(self, symbol: str, cost_basis: float, current_price: float, atr: float) -> StopSignal | None:
        pnl_ratio = (current_price - cost_basis) / cost_basis
        atr_ratio = atr / cost_basis

        if pnl_ratio <= -self.stop_loss_atr * atr_ratio:
            return StopSignal(
                symbol=symbol,
                type="stop_loss",
                reason=f"亏损 {-pnl_ratio * 100:.1f}% 超 {self.stop_loss_atr}×ATR",
                current_price=current_price,
                trigger_price=cost_basis * (1 - self.stop_loss_atr * atr_ratio),
            )

        if pnl_ratio >= self.stop_win_atr * atr_ratio:
            return StopSignal(
                symbol=symbol,
                type="take_profit",
                reason=f"盈利 {pnl_ratio * 100:.1f}% 达 {self.stop_win_atr}×ATR",
                current_price=current_price,
                trigger_price=cost_basis * (1 + self.stop_win_atr * atr_ratio),
            )

        return None

    # ------------------------------------------------------------------
    # Layer 2 — Single-day crash protection
    # ------------------------------------------------------------------
    def _check_crash_stop(
        self, symbol: str, current_price: float, atr: float, prev_close: float | None
    ) -> StopSignal | None:
        if prev_close is None or prev_close <= 0:
            return None

        daily_drop = current_price - prev_close
        if daily_drop < 0 and abs(daily_drop) > self.crash_atr * atr:
            return StopSignal(
                symbol=symbol,
                type="crash_stop",
                reason=f"单日跌幅 {daily_drop / prev_close * 100:.1f}% 超 {self.crash_atr}×ATR({atr:.2f})",
                current_price=current_price,
                trigger_price=prev_close - self.crash_atr * atr,
            )

        return None

    # ------------------------------------------------------------------
    # Layer 3 — Profit drawdown protection
    # ------------------------------------------------------------------
    def _check_drawdown_stop(
        self, symbol: str, cost_basis: float, quotes: pd.DataFrame, atr: float
    ) -> StopSignal | None:
        closes = quotes["close"].values
        if len(closes) < 5:
            return None

        peak_price = float(np.max(closes))
        current_price = float(closes[-1])

        # Only trigger drawdown stop if we're in profit territory
        if current_price <= cost_basis:
            return None

        drawdown = peak_price - current_price
        if drawdown > self.drawdown_atr * atr:
            return StopSignal(
                symbol=symbol,
                type="drawdown_stop",
                reason=f"从高点 {peak_price:.2f} 回撤 {drawdown:.2f} 超 {self.drawdown_atr}×ATR",
                current_price=current_price,
                trigger_price=peak_price - self.drawdown_atr * atr,
            )

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_atr(quotes: pd.DataFrame, window: int = 14) -> float | None:
        """Compute ATR(14) from daily quotes."""
        df = quotes.copy()
        if df.empty or "close" not in df.columns:
            return None
        if len(df) < window + 1:
            return None

        if "high" in df.columns and "low" in df.columns:
            df["prev_close"] = df["close"].shift(1)
            df["tr1"] = df["high"] - df["low"]
            df["tr2"] = abs(df["high"] - df["prev_close"])
            df["tr3"] = abs(df["low"] - df["prev_close"])
            df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
        else:
            # Fallback: use absolute daily change as pseudo-ATR
            df["tr"] = abs(df["close"].diff())

        atr_series = df["tr"].rolling(window=window, min_periods=window).mean()
        last_atr = atr_series.iloc[-1]
        return float(last_atr) if not pd.isna(last_atr) else None
