"""Tests for ensemble prediction utilities."""

import numpy as np
import pandas as pd
import pytest

from aifa_quant.models.ensemble import EnsembleModel


class _FakeModel:
    def __init__(self, scores, feature_names=None, importance=None):
        self.scores = pd.Series(scores)
        self.feature_names = feature_names or ["factor"]
        self._importance = importance or pd.Series({"factor": 1.0})

    def predict(self, X):
        return self.scores.loc[X.index]

    @property
    def feature_importance(self):
        return self._importance


def test_rank_mean_ranks_each_model_across_stocks():
    X = pd.DataFrame({"factor": [1.0, 2.0, 3.0]})
    model_a = _FakeModel([0.1, 0.2, 0.3])
    model_b = _FakeModel([0.3, 0.2, 0.1])
    ensemble = EnsembleModel([(model_a, 1.0), (model_b, 1.0)], method="rank_mean")

    scores = ensemble.predict(X)

    assert np.allclose(scores, [2 / 3, 2 / 3, 2 / 3])


def test_weighted_mean_renormalizes_available_model_weights():
    X = pd.DataFrame({"factor": [1.0, None]})
    model_a = _FakeModel([0.2, 0.8])
    model_b = _FakeModel([0.6, 0.4])
    ensemble = EnsembleModel([(model_a, 1.0), (model_b, 3.0)], method="weighted_mean")

    scores = ensemble.predict(X)

    assert scores[0] == pytest.approx(0.5)
    assert scores[1] == 0.0


def test_update_weights_from_ic_uses_softmax_of_mean_over_std():
    X = pd.DataFrame({"factor": [1.0, 2.0, 3.0]})
    model_a = _FakeModel([0.1, 0.2, 0.3])
    model_b = _FakeModel([0.3, 0.2, 0.1])
    ensemble = EnsembleModel(
        [(model_a, 1.0), (model_b, 1.0)],
        method="weighted_mean",
        model_names=["a", "b"],
    )

    ensemble.update_weights_from_ic({"a": 0.1, "b": 0.3})

    assert ensemble.dynamic_weights is not None
    assert ensemble.dynamic_weights["b"] > ensemble.dynamic_weights["a"]

    scores = ensemble.predict(X)
    # With single IC observation std == 0, score = mean; b weight > a weight.
    expected_b_weight = ensemble.dynamic_weights["b"]
    expected_a_weight = ensemble.dynamic_weights["a"]
    expected = (
        expected_a_weight * np.array([0.1, 0.2, 0.3])
        + expected_b_weight * np.array([0.3, 0.2, 0.1])
    )
    assert np.allclose(scores, expected)


def test_dynamic_weights_loaded_from_weights_path(tmp_path):
    weights_path = tmp_path / "ensemble_weights.json"
    ensemble = EnsembleModel(
        [(_FakeModel([0.0]), 1.0)],
        method="weighted_mean",
        model_names=["a"],
        weights_path=weights_path,
    )
    ensemble.update_weights_from_ic({"a": 0.5})

    assert weights_path.exists()

    ensemble2 = EnsembleModel(
        [(_FakeModel([0.0]), 1.0)],
        method="weighted_mean",
        model_names=["a"],
        weights_path=weights_path,
    )
    assert ensemble2.dynamic_weights == {"a": pytest.approx(1.0)}
