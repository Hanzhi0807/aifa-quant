"""Meta-labeling second-stage model.

Pipeline:
  1. First-stage model (LambdaRank) scores all candidates; take top_k*2.
  2. Second-stage LightGBM classifier predicts P(profitable | features).
  3. Keep only candidates with P > threshold; take top_k; send to optimizer.

The second-stage label is the realized triple-barrier outcome (+1 = profitable).
Features are the same factor matrix plus the first-stage score as a meta-feature.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd

logger = logging.getLogger(__name__)


class MetaLabeler:
    """Second-stage binary classifier that gates first-stage signals."""

    def __init__(self, params: dict | None = None):
        self.params = params or {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "num_leaves": 15,
            "max_depth": 4,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_child_samples": 30,
            "reg_alpha": 0.1,
            "reg_lambda": 0.5,
            "verbose": -1,
            "n_estimators": 80,
            "random_state": 42,
        }
        self.model: lgb.LGBMClassifier | None = None
        self.feature_names: list[str] = []

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: list[str],
        first_stage_score: pd.Series | None = None,
    ) -> None:
        """Fit the meta-labeler.

        Args:
            X: Factor features for the candidate set.
            y: Realized outcome (1=profitable, 0=not).
            feature_names: Feature columns to use.
            first_stage_score: Optional first-stage prediction to include as a meta-feature.
        """
        self.feature_names = [c for c in feature_names if c in X.columns]
        X_use = X[self.feature_names].copy()
        if first_stage_score is not None:
            X_use["_first_stage_score"] = first_stage_score.reindex(X_use.index).fillna(0.5)
            self.feature_names = self.feature_names + ["_first_stage_score"]

        fit_params = self.params.copy()
        pos = int((y == 1).sum())
        neg = int((y == 0).sum())
        if pos > 0 and neg > 0:
            fit_params["scale_pos_weight"] = float(neg / pos)

        self.model = lgb.LGBMClassifier(**fit_params)
        self.model.fit(X_use, y)

    def predict_proba(self, X: pd.DataFrame, first_stage_score: pd.Series | None = None) -> pd.Series:
        """Return P(profitable) for each row."""
        if self.model is None:
            raise RuntimeError("MetaLabeler not fitted.")
        X_use = X[self.feature_names].copy()
        if "_first_stage_score" in self.feature_names and first_stage_score is not None:
            X_use["_first_stage_score"] = first_stage_score.reindex(X_use.index).fillna(0.5)
        return pd.Series(self.model.predict_proba(X_use)[:, 1], index=X_use.index)

    def gate(
        self,
        candidates: pd.DataFrame,
        score_col: str = "pred_score",
        threshold: float = 0.5,
        top_k: int = 20,
        first_stage_score: pd.Series | None = None,
    ) -> pd.DataFrame:
        """Filter candidates by P(profitable) > threshold, return top_k by score.

        Args:
            candidates: DataFrame with feature columns and a score column.
            score_col: Column to rank by after gating.
            threshold: Minimum P(profitable) to keep.
            top_k: Number of survivors to return.
            first_stage_score: Optional first-stage scores.
        """
        if self.model is None:
            # No meta-model trained → pass through.
            return candidates.nlargest(top_k, score_col)

        proba = self.predict_proba(candidates, first_stage_score)
        candidates = candidates.copy()
        candidates["_meta_proba"] = proba
        survivors = candidates[candidates["_meta_proba"] > threshold]
        if survivors.empty:
            logger.warning("Meta-labeler gated out all candidates; falling back to top_k by score.")
            return candidates.nlargest(top_k, score_col)
        return survivors.nlargest(top_k, score_col)

    def save(self, path: str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "feature_names": self.feature_names, "params": self.params}, path)

    def load(self, path: str) -> None:
        data = joblib.load(path)
        self.model = data["model"]
        self.feature_names = data["feature_names"]
        self.params = data["params"]
