"""XGBoost binary classifier for stock selection — companion to LGBRankerModel."""

import json
from pathlib import Path

import joblib
import pandas as pd
import xgboost as xgb

from .base import BaseModel


class XGBRankerModel(BaseModel):
    """XGBoost model that predicts probability of positive future return.

    Interface matches LGBRankerModel for drop-in ensemble use.
    """

    def __init__(self, params: dict | None = None):
        self.params = params or {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "reg_alpha": 0.01,
            "reg_lambda": 0.1,
            "n_estimators": 100,
            "random_state": 42,
            "verbosity": 0,
        }
        self.model: xgb.XGBClassifier | None = None
        self.feature_names: list[str] = []

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: list[str],
        eval_X: pd.DataFrame | None = None,
        eval_y: pd.Series | None = None,
        **kwargs,
    ) -> None:
        self.feature_names = [c for c in feature_names if c in X.columns]
        X = X[self.feature_names].copy()

        pos_count = (y == 1).sum()
        neg_count = (y == 0).sum()
        if pos_count > 0 and neg_count > 0:
            self.params["scale_pos_weight"] = float(neg_count / pos_count)

        self.model = xgb.XGBClassifier(**self.params)

        fit_kwargs: dict = {"verbose": False}
        if eval_X is not None and eval_y is not None:
            eval_X = eval_X[self.feature_names].copy()
            fit_kwargs["eval_set"] = [(eval_X, eval_y)]

        self.model.fit(X, y, **fit_kwargs)

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
