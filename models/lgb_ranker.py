"""LightGBM binary classifier for stock selection."""

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd

from .base import BaseModel


class LGBRankerModel(BaseModel):
    """LightGBM model that predicts probability of positive future return."""

    def __init__(self, params: dict | None = None):
        self.params = params or {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "n_estimators": 100,
            "random_state": 42,
        }
        self.model: lgb.LGBMClassifier | None = None
        self.feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series, feature_names: list[str]) -> None:
        self.feature_names = [c for c in feature_names if c in X.columns]
        X = X[self.feature_names].copy()
        self.model = lgb.LGBMClassifier(**self.params)
        self.model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if self.model is None:
            raise RuntimeError("Model has not been fitted or loaded.")
        X = X[self.feature_names].copy()
        return pd.Series(self.model.predict_proba(X)[:, 1], index=X.index)

    def save(self, path: str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)
        meta_path = path.with_suffix(".json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"feature_names": self.feature_names, "params": self.params}, f)

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
