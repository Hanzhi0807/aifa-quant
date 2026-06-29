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
