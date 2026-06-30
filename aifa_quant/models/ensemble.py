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

    Dynamic ensemble weights can be updated from recent validation RankIC
    values via ``update_weights_from_ic``. When dynamic weights are available
    they override the static config weights for ``weighted_mean``.
    """

    def __init__(
        self,
        models: list[tuple[Any, float]],
        method: str = "weighted_mean",
        rolling_ic_window: int = 6,
        weights_path: str | Path | None = None,
        model_names: list[str] | None = None,
    ):
        self.models = models
        self.method = method
        self.rolling_ic_window = rolling_ic_window
        self.weights_path = Path(weights_path) if weights_path else None
        self.model_names = (
            list(model_names)
            if model_names is not None
            else [f"model_{i}" for i in range(len(models))]
        )
        if len(self.model_names) != len(self.models):
            raise ValueError("model_names length must match models length")

        self._feature_names: list[str] | None = None
        self.ic_history: dict[str, list[float]] = {}
        self.dynamic_weights: dict[str, float] | None = None

        if self.weights_path:
            self._load_weights()

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        registry_dir: Path | None = None,
        weights_path: str | Path | None = None,
    ) -> EnsembleModel:
        config_path = Path(config_path)
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        method = config.get("method", "weighted_mean")
        rolling_ic_window = config.get("rolling_ic_window", 6)
        weights_path = weights_path or config.get("weights_path")

        models: list[tuple[Any, float]] = []
        model_names: list[str] = []
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
            model_names.append(name)
        if not models:
            raise ValueError("Ensemble config must contain at least one model")
        return cls(
            models,
            method=method,
            rolling_ic_window=rolling_ic_window,
            weights_path=weights_path,
            model_names=model_names,
        )

    def _load_weights(self) -> None:
        if not self.weights_path or not self.weights_path.exists():
            return
        try:
            with open(self.weights_path, encoding="utf-8") as f:
                weights = json.load(f)
            if isinstance(weights, dict):
                self.dynamic_weights = {str(k): float(v) for k, v in weights.items()}
        except Exception:
            self.dynamic_weights = None

    def _save_weights(self) -> None:
        if not self.weights_path or self.dynamic_weights is None:
            return
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.weights_path, "w", encoding="utf-8") as f:
            json.dump(self.dynamic_weights, f, ensure_ascii=False, indent=2)

    @property
    def feature_names(self) -> list[str]:
        if self._feature_names is None:
            names: set[str] = set()
            for model, _ in self.models:
                names.update(model.feature_names)
            self._feature_names = sorted(names)
        return self._feature_names

    def update_weights_from_ic(self, ic_map: dict[str, float]) -> None:
        """Update dynamic ensemble weights from a fresh validation RankIC map.

        For each submodel the recent ``rolling_ic_window`` validation IC values
        are used to compute mean / std. Weights are set via softmax(mean/std).
        If std is zero the mean is used directly as the score.
        """
        for name, ic in ic_map.items():
            if name not in self.model_names:
                continue
            self.ic_history.setdefault(name, []).append(float(ic))

        scores: dict[str, float] = {}
        for name in self.model_names:
            values = self.ic_history.get(name, [])
            recent = values[-self.rolling_ic_window :] if values else []
            mean = float(np.mean(recent)) if recent else 0.0
            std = float(np.std(recent, ddof=0)) if recent else 0.0
            scores[name] = mean if std == 0 else mean / std

        score_arr = np.array(list(scores.values()), dtype=float)
        if score_arr.size == 0:
            self.dynamic_weights = None
            return

        # Numerically stable softmax
        shifted = score_arr - np.max(score_arr)
        exp = np.exp(shifted)
        weights = exp / exp.sum()
        self.dynamic_weights = dict(zip(scores.keys(), weights.tolist()))

        if self.weights_path:
            self._save_weights()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.models:
            raise ValueError("No models loaded")
        X = X.copy()
        scores_list: list[np.ndarray] = []
        weights: list[float] = []
        for idx, (model, config_weight) in enumerate(self.models):
            cols = [c for c in model.feature_names if c in X.columns]
            if not cols:
                continue
            sub = X[cols].dropna()
            if sub.empty:
                continue
            pred = pd.Series(index=X.index, dtype=float)
            pred.loc[sub.index] = model.predict(sub)
            scores_list.append(pred.values)

            name = self.model_names[idx]
            if self.dynamic_weights is not None and name in self.dynamic_weights:
                weights.append(self.dynamic_weights[name])
            else:
                weights.append(config_weight)
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
        for idx, (model, config_weight) in enumerate(self.models):
            weight = (
                self.dynamic_weights.get(self.model_names[idx], config_weight)
                if self.dynamic_weights
                else config_weight
            )
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
