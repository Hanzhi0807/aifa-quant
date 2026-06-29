"""Tests for strategy selection rules."""

import pandas as pd

from aifa_quant.strategy import TopKDropoutStrategy


def test_topk_dropout_caps_selected_count_after_holding_survival():
    strategy = TopKDropoutStrategy(top_k=2, dropout_threshold=4)
    features = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-02"] * 4),
            "symbol": ["A", "B", "C", "D"],
            "pred_score": [4.0, 3.0, 2.0, 1.0],
        }
    )

    signals = strategy.generate_signals(
        features,
        current_date=pd.Timestamp("2024-01-02"),
        hold_symbols=["C", "D"],
    )

    selected = signals[signals["selected"]]
    assert len(selected) == 2
    assert selected["symbol"].tolist() == ["A", "B"]
