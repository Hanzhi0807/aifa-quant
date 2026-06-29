"""Ensemble wrapper for multiple trained models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .lgb_lambdarank import LGBLambdaRankModel
from .lgb_ranker import LGBRankerModel

MODEL_CLASS_MAP = {
    "lgb_classifier": LGBRankerModel,
    "binary": LGBRankerModel,
    "lgb_lambdarank": LGBLambdaRankModel,
    "lambdarank": LGBLambdaRankModel,
}


class EnsembleModel:
    """Combine predictions from multiple trained models.

    Supported methods:
        - weighted_mean: weighted average of model scores
        - mean: equal-weight average
        - median: median score per stock
        - rank_mean: average of normalized ranks
    """

    def __init__(self, models: list[tuple[Any, float]], method: str = "weighted_mean"):
        self.models = models
        self.method = method
        self._feature_names: list[str] | None = None

    @classmethod
    def from_config(cls, config_path: str | Path, registry_dir: Path | None = None) -> EnsembleModel:
        config_path = Path(config_path)
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        method = config.get("method", "weighted_mean")
        models: list[tuple[Any, float]] = []
        for item in config.get("models", []):
            name = item.get("name", item.get("path", ""))
            weight = float(item.get("weight", 1.0))
            model_path = Path(item["path"]) if "path" in item else None
            if model_path is None and registry_dir is not None:
                model_path = registry_dir / name
            if model_path is None or not model_path.exists():
                raise FileNotFoundError(f"Ensemble model not found: {name} ({model_path})")
            allowed_base = (registry_dir if registry_dir else config_path.parent).resolve()
            if not str(model_path.resolve()).startswith(str(allowed_base)):
                raise ValueError(f"Model path escapes allowed directory: {model_path}")

            model_type = item.get("type", "lgb_classifier")
            model_cls = MODEL_CLASS_MAP.get(model_type)
            if model_cls is None:
                raise ValueError(f"Unsupported ensemble model type: {model_type}")
            model = model_cls()
            model.load(str(model_path))
            models.append((model, weight))
        if not models:
            raise ValueError("Ensemble config must contain at least one model")
        return cls(models, method=method)

    @property
    def feature_names(self) -> list[str]:
        if self._feature_names is None:
            names: set[str] = set()
            for model, _ in self.models:
                names.update(model.feature_names)
            self._feature_names = sorted(names)
        return self._feature_names

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.models:
            raise ValueError("No models loaded")
        X = X.copy()
        scores_list: list[np.ndarray] = []
        weights: list[float] = []
        for model, weight in self.models:
            cols = [c for c in model.feature_names if c in X.columns]
            if not cols:
                continue
            sub = X[cols].dropna()
            if sub.empty:
                continue
            pred = pd.Series(index=X.index, dtype=float)
            pred.loc[sub.index] = model.predict(sub)
            scores_list.append(pred.values)
            weights.append(weight)
        if not scores_list:
            return np.zeros(len(X))
        scores = np.vstack(scores_list)
        if self.method == "mean":
            return np.nanmean(scores, axis=0)
        if self.method == "median":
            return np.nanmedian(scores, axis=0)
        if self.method == "rank_mean":
            ranks = np.apply_along_axis(lambda s: pd.Series(s).rank(pct=True).values, 1, scores)
            return np.nanmean(ranks, axis=0)

        weights_arr = np.array(weights, dtype=float)
        if weights_arr.sum() == 0:
            weights_arr = np.ones_like(weights_arr)
        weights_arr = weights_arr / weights_arr.sum()
        mask = ~np.isnan(scores)
        effective_weights = np.where(mask, weights_arr[:, np.newaxis], 0.0)
        weight_sums = effective_weights.sum(axis=0)
        result = np.zeros(scores.shape[1], dtype=float)
        valid = weight_sums > 0
        result[valid] = np.nansum(scores[:, valid] * effective_weights[:, valid], axis=0) / weight_sums[valid]
        return result

    def save(self, path: str | Path) -> None:
        raise NotImplementedError("Use the underlying sub-models; ensemble config is separate")

    @property
    def feature_importance(self) -> dict[str, float] | None:
        agg: dict[str, float] = {}
        total_weight = 0.0
        for model, weight in self.models:
            fi = model.feature_importance
            if fi is None:
                continue
            for name, value in fi.items():
                agg[name] = agg.get(name, 0.0) + value * weight
            total_weight += weight
        if not agg:
            return None
        if total_weight:
            agg = {k: v / total_weight for k, v in agg.items()}
        return agg
