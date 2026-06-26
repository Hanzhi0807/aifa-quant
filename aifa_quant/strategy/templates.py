"""Strategy templates for quick experimentation.

A template is a pre-defined parameter set that can be applied to train/backtest
commands via `--strategy-template <name>`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyTemplate:
    name: str
    description: str
    top_k: int
    rebalance_freq: int
    dropout_threshold: int | None
    model_type: str
    horizon: int


TEMPLATES: dict[str, StrategyTemplate] = {
    "default": StrategyTemplate(
        name="default",
        description="默认配置：TopK=5，5日调仓，二分类模型",
        top_k=5,
        rebalance_freq=5,
        dropout_threshold=None,
        model_type="binary",
        horizon=5,
    ),
    "aggressive": StrategyTemplate(
        name="aggressive",
        description="激进短线：TopK=3，每日调仓，滚动训练",
        top_k=3,
        rebalance_freq=1,
        dropout_threshold=5,
        model_type="binary",
        horizon=3,
    ),
    "conservative": StrategyTemplate(
        name="conservative",
        description="稳健长线：TopK=10，20日调仓， LambdaRank",
        top_k=10,
        rebalance_freq=20,
        dropout_threshold=15,
        model_type="lambdarank",
        horizon=20,
    ),
    "momentum": StrategyTemplate(
        name="momentum",
        description="动量策略：TopK=5，10日调仓， dropout 阈值 8",
        top_k=5,
        rebalance_freq=10,
        dropout_threshold=8,
        model_type="binary",
        horizon=10,
    ),
}


def get_template(name: str) -> StrategyTemplate:
    if name not in TEMPLATES:
        raise ValueError(
            f"Unknown strategy template: {name}. Available: {', '.join(TEMPLATES.keys())}"
        )
    return TEMPLATES[name]


def list_templates() -> list[StrategyTemplate]:
    return list(TEMPLATES.values())
