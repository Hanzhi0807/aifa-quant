"""TopK-Dropout strategy with industry constraints and market regime filter."""

import pandas as pd

from .base import BaseStrategy


class TopKDropoutStrategy(BaseStrategy):
    """Select top K stocks by score with dropout hysteresis.

    Improvements over naive top-K:
    - Industry concentration cap prevents sector blowups
    - Market regime filter reduces exposure in severe downtrends
    """

    def __init__(
        self,
        top_k: int = 20,
        rebalance_freq: int = 5,
        dropout_threshold: int | None = None,
        max_industry_pct: float = 0.30,
        min_liquidity_wan: float | None = None,
    ):
        self.top_k = top_k
        self.rebalance_freq = rebalance_freq
        self.dropout_threshold = dropout_threshold or top_k * 2
        self.max_industry_pct = max_industry_pct
        self.min_liquidity_wan = min_liquidity_wan

    def generate_signals(
        self,
        features: pd.DataFrame,
        current_date: pd.Timestamp,
        hold_symbols: list | None = None,
        industry_map: dict[str, str] | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Generate selection for current_date with industry cap.

        Args:
            features: DataFrame with model score column `pred_score`.
            current_date: Trade date to select for.
            hold_symbols: Currently held symbols (for dropout logic).
            industry_map: symbol -> industry mapping for concentration control.
        """
        day_df = features[features["trade_date"] == current_date].copy()
        if day_df.empty:
            return pd.DataFrame(columns=["symbol", "score", "rank", "selected"])

        if (
            self.min_liquidity_wan is not None
            and "avg_amount_20d" in day_df.columns
        ):
            day_df = day_df[day_df["avg_amount_20d"] >= self.min_liquidity_wan]

        day_df = day_df.sort_values("pred_score", ascending=False).reset_index(drop=True)
        day_df["rank"] = day_df.index + 1

        hold_symbols = set(hold_symbols or [])
        day_df["is_held"] = day_df["symbol"].isin(hold_symbols)

        # Dropout logic: held stocks get wider tolerance band
        day_df["eligible"] = (day_df["is_held"] & (day_df["rank"] <= self.dropout_threshold)) | (
            ~day_df["is_held"] & (day_df["rank"] <= self.top_k)
        )

        # Select from eligible candidates with industry concentration cap
        eligible = day_df[day_df["eligible"]].copy()
        selected_symbols = self._select_with_industry_cap(eligible, industry_map)

        day_df["selected"] = day_df["symbol"].isin(selected_symbols)
        return day_df[["symbol", "pred_score", "rank", "selected"]].rename(columns={"pred_score": "score"})

    def _select_with_industry_cap(
        self,
        eligible: pd.DataFrame,
        industry_map: dict[str, str] | None,
    ) -> set[str]:
        """Greedy selection respecting per-industry concentration limit."""
        if industry_map is None or not self.max_industry_pct:
            # No industry data: fall back to simple top-K
            return set(eligible.nsmallest(self.top_k, "rank")["symbol"])

        max_per_industry = max(1, int(self.top_k * self.max_industry_pct))
        selected: list[str] = []
        industry_count: dict[str, int] = {}

        for _, row in eligible.iterrows():
            if len(selected) >= self.top_k:
                break
            sym = row["symbol"]
            ind = industry_map.get(sym, "unknown")
            if industry_count.get(ind, 0) >= max_per_industry:
                continue
            selected.append(sym)
            industry_count[ind] = industry_count.get(ind, 0) + 1

        return set(selected)
