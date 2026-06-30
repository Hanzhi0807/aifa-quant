"""Rolling window training and prediction to avoid look-ahead bias."""

from collections.abc import Callable

import pandas as pd

from ..config.settings import Settings
from ..features import FeatureBuilder
from ..features.selection import drop_highly_correlated
from .base import BaseModel
from .lgb_lambdarank import LGBLambdaRankModel


class RollingTrainer:
    """Train models on rolling trading-day windows and predict out-of-sample."""

    def __init__(
        self,
        model_factory: Callable[[], BaseModel] | None = None,
        train_window_days: int = 252 * 2,
        min_train_samples: int = 500,
        settings: Settings | None = None,
        label_horizon: int = 5,
        label_type: str = "excess_quantile",
        corr_threshold: float | None = 0.95,
    ):
        self.settings = settings or Settings()
        self.model_factory = model_factory or LGBLambdaRankModel
        # train_window_days is measured in trading days, not calendar days.
        self.train_window_days = train_window_days
        self.min_train_samples = min_train_samples
        self.label_horizon = label_horizon
        self.label_type = label_type
        self.corr_threshold = corr_threshold

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
        dates = sorted(pd.to_datetime(features["trade_date"].unique()))
        date_to_idx = {date: idx for idx, date in enumerate(dates)}

        if rebalance_dates is None:
            rebalance_dates = dates
        else:
            rebalance_dates = [pd.to_datetime(d) for d in rebalance_dates]
            rebalance_dates = [d for d in rebalance_dates if d in date_to_idx]

        predictions = []
        for pred_date in rebalance_dates:
            pred_idx = date_to_idx[pred_date]
            # A row dated t has a label that uses t + label_horizon. To predict
            # pred_date without leakage, the latest training row must have its
            # future label fully observed before pred_date.
            train_end_idx = pred_idx - self.label_horizon - 1
            if train_end_idx < 0:
                continue
            train_start_idx = max(0, train_end_idx - self.train_window_days + 1)
            train_start = dates[train_start_idx]
            train_end = dates[train_end_idx]

            train_mask = (features["trade_date"] >= train_start) & (features["trade_date"] <= train_end)
            train_df = features[train_mask].copy()

            if len(train_df) < self.min_train_samples:
                continue

            active_features = feature_cols
            if self.corr_threshold is not None and self.corr_threshold < 1.0:
                active_features = drop_highly_correlated(train_df, active_features, threshold=self.corr_threshold)
            if not active_features:
                continue

            model = self.model_factory()
            is_ranker = getattr(model, "is_ranker", False)
            label_col = "label_rank" if is_ranker else "label_binary"

            # Drop NaNs in features/label
            train_df = train_df.dropna(subset=active_features + [label_col])
            if len(train_df) < self.min_train_samples:
                continue

            x_train = train_df[active_features]
            y_train = train_df[label_col]
            fit_kwargs: dict = {}
            if is_ranker:
                fit_kwargs["groups"] = train_df["trade_date"]
            model.fit(x_train, y_train, active_features, **fit_kwargs)

            # Predict for current date using the same train-window-selected features.
            pred_mask = features["trade_date"] == pred_date
            pred_df = features[pred_mask].copy()
            pred_df = pred_df.dropna(subset=active_features)
            if pred_df.empty:
                continue

            pred_df["pred_score"] = model.predict(pred_df[active_features])
            predictions.append(pred_df[["symbol", "trade_date", "pred_score"]])

        if not predictions:
            return pd.DataFrame(columns=["symbol", "trade_date", "pred_score"])
        return pd.concat(predictions, ignore_index=True)
