"""Pre-defined strategy profiles for different investor preferences."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class StrategyProfile:
    """Configuration for one strategy variant."""

    id: str
    name: str
    description: str
    top_k: int
    rebalance_freq: int  # trading days between rebalances
    max_industry_pct: float  # max weight in single industry
    # ATR-based risk controls
    atr_stop_loss: float
    atr_take_profit: float
    atr_crash: float
    atr_drawdown: float
    target_risk_pct: float
    # Market regime: skip new entries when index MA ratio < this threshold
    regime_ma_threshold: float = 0.0
    # Factor emphasis: groups of feature column prefixes to up-weight
    factor_weights: dict[str, float] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.name}（{self.description}）"


# ------------------------------------------------------------------
# Strategy Profiles — designed for adequate diversification
# ------------------------------------------------------------------

PROFILES: dict[str, StrategyProfile] = {
    "aggressive": StrategyProfile(
        id="aggressive",
        name="激进型",
        description="高集中度，追求超额收益",
        top_k=15,
        rebalance_freq=5,
        max_industry_pct=0.35,
        atr_stop_loss=1.5,
        atr_take_profit=4.0,
        atr_crash=2.0,
        atr_drawdown=2.0,
        target_risk_pct=0.03,
        regime_ma_threshold=0.0,  # no regime filter
        factor_weights={
            "momentum": 1.5,
            "volatility": 0.5,
            "alpha": 1.3,
            "return": 1.5,
            "volume": 1.2,
        },
    ),
    "balanced": StrategyProfile(
        id="balanced",
        name="均衡型",
        description="攻守兼备，适合大多数人",
        top_k=20,
        rebalance_freq=5,
        max_industry_pct=0.25,
        atr_stop_loss=1.0,
        atr_take_profit=3.0,
        atr_crash=1.5,
        atr_drawdown=1.5,
        target_risk_pct=0.02,
        regime_ma_threshold=0.95,  # reduce exposure if MA20/MA60 < 0.95
        factor_weights={},
    ),
    "conservative": StrategyProfile(
        id="conservative",
        name="稳健型",
        description="充分分散，严控回撤",
        top_k=30,
        rebalance_freq=10,
        max_industry_pct=0.20,
        atr_stop_loss=0.75,
        atr_take_profit=2.0,
        atr_crash=1.0,
        atr_drawdown=1.0,
        target_risk_pct=0.012,
        regime_ma_threshold=0.97,  # conservative: exit earlier
        factor_weights={
            "pe": 1.5,
            "pb": 1.5,
            "roe": 1.5,
            "volatility": -0.5,
            "beta": -0.5,
        },
    ),
    "growth": StrategyProfile(
        id="growth",
        name="成长型",
        description="聚焦高成长潜力股",
        top_k=20,
        rebalance_freq=5,
        max_industry_pct=0.30,
        atr_stop_loss=1.0,
        atr_take_profit=3.0,
        atr_crash=1.5,
        atr_drawdown=1.5,
        target_risk_pct=0.025,
        regime_ma_threshold=0.95,
        factor_weights={
            "roe": 2.0,
            "revenue": 2.0,
            "gross_margin": 1.5,
            "momentum": 1.3,
            "alpha": 1.2,
        },
    ),
    "value": StrategyProfile(
        id="value",
        name="价值型",
        description="低估值选股，安全边际优先",
        top_k=25,
        rebalance_freq=10,
        max_industry_pct=0.25,
        atr_stop_loss=0.75,
        atr_take_profit=2.5,
        atr_crash=1.2,
        atr_drawdown=1.2,
        target_risk_pct=0.015,
        regime_ma_threshold=0.93,  # value: more tolerant of drawdown
        factor_weights={
            "pe": 2.0,
            "pb": 2.0,
            "ps": 1.5,
            "dividend": 2.0,
            "roe": 1.3,
            "momentum": -0.5,
        },
    ),
}


def list_profiles() -> list[StrategyProfile]:
    """Return all strategy profiles."""
    return list(PROFILES.values())


def get_profile(profile_id: str) -> StrategyProfile | None:
    """Get a specific profile by ID."""
    return PROFILES.get(profile_id)


def apply_profile_score(
    df: pd.DataFrame,
    profile: StrategyProfile | str,
    feature_cols: list[str],
    model_weight: float = 0.7,
    factor_weight: float = 0.3,
) -> pd.DataFrame:
    """Blend model prediction score with profile-specific factor emphasis."""
    pf = profile if isinstance(profile, StrategyProfile) else get_profile(profile)
    if pf is None or not pf.factor_weights:
        df = df.copy()
        df["model_score"] = df["pred_score"]
        return df

    df = df.copy()
    df["model_score"] = df["pred_score"]

    factor_score_cols: list[str] = []
    for factor, weight in pf.factor_weights.items():
        matched = [c for c in feature_cols if factor.lower() in c.lower()]
        if not matched:
            continue
        col_name = f"factor_{factor}"
        df[col_name] = df[matched].mean(axis=1) * weight
        factor_score_cols.append(col_name)

    if factor_score_cols:
        df["factor_score"] = df[factor_score_cols].sum(axis=1)
        mean = df["factor_score"].mean()
        std = df["factor_score"].std()
        if std and std > 0:
            df["factor_score"] = (df["factor_score"] - mean) / std
        else:
            df["factor_score"] = 0.0
    else:
        df["factor_score"] = 0.0

    df["pred_score"] = model_weight * df["model_score"] + factor_weight * df["factor_score"]
    return df
