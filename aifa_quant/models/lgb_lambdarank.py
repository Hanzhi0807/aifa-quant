"""LightGBM LambdaRank model for learning-to-rank stock selection.

Treats each trade_date as a query group and ranks stocks by their future return.
"""

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from .base import BaseModel


class LGBLambdaRankModel(BaseModel):
    """LightGBM LambdaRank model that learns to rank stocks within each date."""

    def __init__(self, params: dict | None = None):
        self.params = params or {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [5, 10, 20],
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "max_depth": 8,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_child_samples": 20,
            "reg_alpha": 0.01,
            "reg_lambda": 0.1,
            "verbose": -1,
            "n_estimators": 100,
            "random_state": 42,
            "label_gain": [i for i in range(10)],  # default gain for 0..9 labels
        }
        self.model: lgb.LGBMRanker | None = None
        self.feature_names: list[str] = []

    def _build_groups(self, y: pd.Series) -> np.ndarray:
        """Build query group sizes assuming y is sorted by trade_date."""
        return y.groupby(y.index).size().values

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: list[str],
        groups: pd.Series | None = None,
        **kwargs,
    ) -> None:
        """Train LambdaRank model.

        Args:
            X: Feature matrix.
            y: Target label. For ranking we recommend a binned future return label (0..N).
            feature_names: List of feature column names.
            groups: Series mapping each row to a query group (e.g. trade_date).
        """
        self.feature_names = [c for c in feature_names if c in X.columns]
        X = X[self.feature_names].copy()

        if groups is None:
            raise ValueError("LambdaRank requires groups (e.g. trade_date)")

        # Sort by group to satisfy LightGBM's requirement
        df = pd.DataFrame({"y": y, "group": groups}).join(X)
        df = df.sort_values("group").reset_index(drop=True)
        y_sorted = df["y"].astype(int)
        group_sizes = df.groupby("group").size().values
        x_sorted = df[self.feature_names]

        self.model = lgb.LGBMRanker(**self.params)
        self.model.fit(x_sorted, y_sorted, group=group_sizes)

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if self.model is None:
            raise RuntimeError("Model has not been fitted or loaded.")
        X = X[self.feature_names].copy()
        return pd.Series(self.model.predict(X), index=X.index)

    def save(self, path: str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)
        meta_path = path.with_suffix(".json")
        meta = {
            "feature_names": self.feature_names,
            "params": self.params,
            "feature_importance": self.feature_importance.to_dict(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        path = Path(path)
        self.model = joblib.load(path)
        meta_path = path.with_suffix(".json")
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
                self.feature_names = meta.get("feature_names", [])
                self.params = meta.get("params", self.params)

    @property
    def feature_importance(self) -> pd.Series:
        if self.model is None:
            raise RuntimeError("Model has not been fitted or loaded.")
        importance = self.model.feature_importances_
        return pd.Series(importance, index=self.feature_names).sort_values(ascending=False)
