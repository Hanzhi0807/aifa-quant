"""TopK-Dropout strategy: pick top K stocks by model score, rebalance periodically."""

import pandas as pd

from .base import BaseStrategy


class TopKDropoutStrategy(BaseStrategy):
    """Select top K stocks by score; drop stocks that fall out of top K."""

    def __init__(
        self,
        top_k: int = 5,
        rebalance_freq: int = 5,
        dropout_threshold: int | None = None,
    ):
        self.top_k = top_k
        self.rebalance_freq = rebalance_freq
        # Drop a held stock if it falls below this rank; default = top_k * 2
        self.dropout_threshold = dropout_threshold or top_k * 2

    def generate_signals(
        self,
        features: pd.DataFrame,
        current_date: pd.Timestamp,
        hold_symbols: list | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Generate selection for current_date.

        Args:
            features: DataFrame with model score column `pred_score`.
            current_date: Trade date to select for.
            hold_symbols: Currently held symbols (for dropout logic).
        """
        day_df = features[features["trade_date"] == current_date].copy()
        if day_df.empty:
            return pd.DataFrame(columns=["symbol", "score", "rank", "selected"])

        day_df = day_df.sort_values("pred_score", ascending=False).reset_index(drop=True)
        day_df["rank"] = day_df.index + 1

        hold_symbols = set(hold_symbols or [])
        selected = []
        for _, row in day_df.iterrows():
            sym = row["symbol"]
            rank = row["rank"]
            if sym in hold_symbols and rank <= self.dropout_threshold:
                selected.append(True)
            elif rank <= self.top_k:
                selected.append(True)
            else:
                selected.append(False)
        day_df["selected"] = selected
        return day_df[["symbol", "pred_score", "rank", "selected"]].rename(columns={"pred_score": "score"})
