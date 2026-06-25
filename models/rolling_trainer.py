"""Rolling window training and prediction to avoid look-ahead bias."""

from collections.abc import Callable

import pandas as pd

from ..config.settings import Settings
from ..features import FeatureBuilder
from .base import BaseModel
from .lgb_ranker import LGBRankerModel


class RollingTrainer:
    """Train models on expanding/rolling windows and predict out-of-sample."""

    def __init__(
        self,
        model_factory: Callable[[], BaseModel] | None = None,
        train_window_days: int = 252 * 2,
        min_train_samples: int = 500,
        settings: Settings | None = None,
    ):
        self.settings = settings or Settings()
        self.model_factory = model_factory or LGBRankerModel
        self.train_window_days = train_window_days
        self.min_train_samples = min_train_samples

    def predict_rolling(
        self,
        features: pd.DataFrame,
        rebalance_dates: list[pd.Timestamp] | None = None,
    ) -> pd.DataFrame:
        """Generate out-of-sample predictions using rolling windows.

        Args:
            features: Full feature DataFrame with trade_date, symbol, label_binary, etc.
            rebalance_dates: Dates on which to retrain and predict. If None, use unique trade_dates.
        """
        features = features.copy()
        features["trade_date"] = pd.to_datetime(features["trade_date"])
        features = features.sort_values(["trade_date", "symbol"]).reset_index(drop=True)

        feature_cols = FeatureBuilder(self.settings).feature_columns(features)
        dates = sorted(features["trade_date"].unique())

        if rebalance_dates is None:
            rebalance_dates = dates
        else:
            rebalance_dates = [pd.to_datetime(d) for d in rebalance_dates]
            rebalance_dates = [d for d in rebalance_dates if d in dates]

        predictions = []
        for pred_date in rebalance_dates:
            # Training window ends the day before prediction date
            cutoff = pred_date - pd.Timedelta(days=1)
            train_end = cutoff
            train_start = train_end - pd.Timedelta(days=self.train_window_days)

            train_mask = (features["trade_date"] >= train_start) & (features["trade_date"] <= train_end)
            train_df = features[train_mask].copy()

            if len(train_df) < self.min_train_samples:
                continue

            # Drop NaNs in features/label
            train_df = train_df.dropna(subset=feature_cols + ["label_binary"])
            if len(train_df) < self.min_train_samples:
                continue

            model = self.model_factory()
            x_train = train_df[feature_cols]
            y_train = train_df["label_binary"]
            model.fit(x_train, y_train, feature_cols)

            # Predict for current date
            pred_mask = features["trade_date"] == pred_date
            pred_df = features[pred_mask].copy()
            pred_df = pred_df.dropna(subset=feature_cols)
            if pred_df.empty:
                continue

            pred_df["pred_score"] = model.predict(pred_df[feature_cols])
            predictions.append(pred_df[["symbol", "trade_date", "pred_score"]])

        if not predictions:
            return pd.DataFrame(columns=["symbol", "trade_date", "pred_score"])
        return pd.concat(predictions, ignore_index=True)
