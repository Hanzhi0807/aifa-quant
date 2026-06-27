"""Volatility-based position sizing — risk budget per trade.

Formula (from abu):
    shares = target_risk / (N × ATR)
where:
    target_risk = total_value × target_risk_pct   (dollar risk per trade)
    N           = atr_multiplier                    (stop width in ATR units)
    ATR         = Average True Range over atr_window

The result is rounded down to the nearest 100-share lot.  If the resulting
notional exposure exceeds available cash, all positions are scaled back
proportionally so orders can actually be filled.
"""

import pandas as pd


class VolatilityPositionSizer:
    """Size positions using a fixed risk-budget per trade."""

    def __init__(self, target_risk_pct: float = 0.02, atr_multiplier: int = 2, atr_window: int = 14):
        self.target_risk_pct = target_risk_pct
        self.atr_multiplier = atr_multiplier
        self.atr_window = atr_window

    def size_positions(
        self,
        total_value: float,
        selected_symbols: list[str],
        quotes: pd.DataFrame,
        cost_basis_map: dict[str, float] | None = None,
        cash: float | None = None,
    ) -> dict[str, int]:
        """Return target share counts for each symbol.

        Args:
            total_value: Total portfolio value (cash + market value).
            selected_symbols: Symbols to size.
            quotes: OHLCV quote history (multiple days) for the selected universe.
            cost_basis_map: Ignored; kept for interface compatibility.
            cash: Available cash for new positions.  If provided, the computed
                positions are scaled back when their total cost exceeds cash.
        """
        if not selected_symbols or total_value <= 0:
            return {}

        risk_budget = total_value * self.target_risk_pct

        atrs: dict[str, float] = {}
        prices: dict[str, float] = {}
        for sym in selected_symbols:
            sym_quotes = quotes[quotes["symbol"] == sym].sort_values("trade_date")
            atr = self._compute_atr(sym_quotes, self.atr_window)
            last_price = (
                float(sym_quotes.iloc[-1]["close"]) if not sym_quotes.empty else 10.0
            )
            prices[sym] = last_price
            if atr and atr > 0:
                atrs[sym] = atr
            else:
                # Fallback: use 2% of price as ATR proxy
                atrs[sym] = last_price * 0.02

        # shares = risk_budget / (N * ATR), rounded to 100-share lot
        target_shares: dict[str, int] = {}
        for sym in selected_symbols:
            raw_shares = risk_budget / (self.atr_multiplier * atrs[sym])
            rounded = int(raw_shares / 100) * 100
            target_shares[sym] = max(rounded, 0)

        # Cash cap: if we don't have enough cash, scale down proportionally.
        if cash is not None and cash > 0:
            total_cost = sum(target_shares[sym] * prices[sym] for sym in selected_symbols)
            if total_cost > cash:
                scale = cash / total_cost
                for sym in selected_symbols:
                    target_shares[sym] = int(target_shares[sym] * scale / 100) * 100

        return target_shares

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_atr(sym_quotes: pd.DataFrame, window: int = 14) -> float | None:
        if sym_quotes.empty or len(sym_quotes) < window + 1:
            return None
        df = sym_quotes.copy().sort_values("trade_date")
        if "high" in df.columns and "low" in df.columns:
            df["prev_close"] = df["close"].shift(1)
            df["tr1"] = df["high"] - df["low"]
            df["tr2"] = abs(df["high"] - df["prev_close"])
            df["tr3"] = abs(df["low"] - df["prev_close"])
            df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
        else:
            df["tr"] = abs(df["close"].diff())
        atr = df["tr"].rolling(window=window, min_periods=window).mean().iloc[-1]
        return float(atr) if not pd.isna(atr) else None
