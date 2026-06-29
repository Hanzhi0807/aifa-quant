"""Tests for rolling trainer leakage boundaries."""

import pandas as pd

from aifa_quant.models.rolling_trainer import RollingTrainer


def test_rolling_trainer_excludes_unavailable_future_labels():
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    features = pd.DataFrame(
        {
            "trade_date": dates,
            "symbol": ["A"] * len(dates),
            "factor": range(len(dates)),
            "label_binary": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )
    sorted_features = features.sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    captured_train_ends = []

    class CapturingModel:
        feature_names = ["factor"]

        def fit(self, X, y, feature_names, **kwargs):
            captured_train_ends.append(sorted_features.loc[y.index, "trade_date"].max())

        def predict(self, X):
            return pd.Series([0.5] * len(X), index=X.index)

        def save(self, path):
            raise NotImplementedError

        def load(self, path):
            raise NotImplementedError

        @property
        def feature_importance(self):
            return pd.Series(dtype=float)

    trainer = RollingTrainer(
        model_factory=CapturingModel,
        train_window_days=10,
        min_train_samples=1,
        label_horizon=2,
        corr_threshold=None,
    )
    pred_date = dates[6]
    preds = trainer.predict_rolling(features, rebalance_dates=[pred_date])

    assert not preds.empty
    assert captured_train_ends == [dates[3]]
