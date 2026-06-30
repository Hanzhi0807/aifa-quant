"""Pre-defined strategy profiles for different investor preferences."""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# ------------------------------------------------------------------
# Load explicit factor group definitions once at import time.
# ------------------------------------------------------------------
_FACTOR_GROUPS_PATH = Path(__file__).with_name("factor_groups.yml")
with _FACTOR_GROUPS_PATH.open("r", encoding="utf-8") as _fh:
    FACTOR_GROUPS: dict[str, dict] = yaml.safe_load(_fh)


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
    # Factor emphasis: weights per explicit factor group
    factor_group_weights: dict[str, float] = field(default_factory=dict)
    # Kept for backward compatibility; no longer used in scoring logic.
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
        factor_group_weights={
            "momentum": 0.35,
            "alpha": 0.25,
            "volume": 0.20,
            "return": 0.20,
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
        factor_group_weights={
            "momentum": 0.25,
            "value": 0.25,
            "quality": 0.25,
            "low_volatility": 0.25,
        },
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
        factor_group_weights={
            "value": 0.30,
            "quality": 0.30,
            "low_volatility": 0.40,
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
        factor_group_weights={
            "quality": 0.40,
            "momentum": 0.30,
            "alpha": 0.30,
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
        factor_group_weights={
            "value": 0.50,
            "quality": 0.30,
            "low_volatility": 0.20,
        },
    ),
}


def list_profiles() -> list[StrategyProfile]:
    """Return all strategy profiles."""
    return list(PROFILES.values())


def get_profile(profile_id: str) -> StrategyProfile | None:
    """Get a specific profile by ID."""
    return PROFILES.get(profile_id)


def _winsorize_series(series: pd.Series, groups: pd.Series, n_std: float = 3.0) -> pd.Series:
    """Cross-sectional winsorization: clip to median ± n_std * std per group."""

    def _clip(g: pd.Series) -> pd.Series:
        median = g.median()
        std = g.std()
        if pd.isna(std) or std == 0:
            return g
        lower = median - n_std * std
        upper = median + n_std * std
        return g.clip(lower, upper)

    return series.groupby(groups, group_keys=False).apply(_clip)


def _neutralize_series(df: pd.DataFrame, series: pd.Series) -> pd.Series:
    """Return residual of factor ~ industry dummies + log(market_cap) per trade_date.

    If industry or market_cap are missing, return the original series unchanged.
    """
    if "industry" not in df.columns or "market_cap" not in df.columns:
        return series

    tmp = df[["trade_date", "industry", "market_cap"]].copy()
    tmp["factor"] = series.values
    tmp = tmp.dropna(subset=["industry", "market_cap", "factor"])
    if tmp.empty:
        return series

    def _resid(g: pd.DataFrame) -> pd.Series:
        y = g["factor"].values
        dummies = pd.get_dummies(g["industry"], drop_first=True, dtype=float)
        log_mcap = np.log(g["market_cap"].replace(0, np.nan)).fillna(g["market_cap"].median())
        X = pd.concat([dummies, log_mcap.rename("log_mcap")], axis=1).dropna(axis=1)
        if X.empty or X.shape[0] <= X.shape[1]:
            return pd.Series(y, index=g.index)
        design = np.column_stack([np.ones(len(y)), X.values])
        if np.linalg.matrix_rank(design) < design.shape[1]:
            return pd.Series(y, index=g.index)
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        resid = y - design @ beta
        return pd.Series(resid, index=g.index)

    neutralized = tmp.groupby("trade_date", group_keys=False).apply(_resid)
    return neutralized.reindex(series.index).fillna(series)


def _rank_pct(series: pd.Series, groups: pd.Series, direction: int = 1) -> pd.Series:
    """Cross-sectional percentile rank within each group; reverse if direction < 0."""
    ranks = series.groupby(groups, group_keys=False).rank(pct=True, method="average")
    if direction < 0:
        ranks = 1.0 - ranks
    return ranks


def _zscore_within_date(series: pd.Series, dates: pd.Series) -> pd.Series:
    """Cross-sectional z-score within each date; return 0 when std is zero."""

    def _zscore(g: pd.Series) -> pd.Series:
        mean = g.mean()
        std = g.std()
        if pd.isna(std) or std == 0:
            return pd.Series(0.0, index=g.index)
        return (g - mean) / std

    return series.groupby(dates, group_keys=False).apply(_zscore)


def apply_profile_score(
    df: pd.DataFrame,
    profile: StrategyProfile | str,
    feature_cols: list[str],
    model_weight: float = 0.7,
    factor_weight: float = 0.3,
) -> pd.DataFrame:
    """Blend model prediction score with profile-specific factor group emphasis.

    For each active factor group in the profile:
      1. Intersect configured columns with available feature columns.
      2. Winsorize each column cross-sectionally within trade_date.
      3. Optionally neutralize against industry and log(market_cap).
      4. Convert to percentile rank within trade_date (reverse for direction=-1).
      5. Average ranks to obtain the group score.
    The final ``factor_score`` is the weighted sum of group scores, z-scored
    within each trade_date, and blended with the original model score.
    """
    pf = profile if isinstance(profile, StrategyProfile) else get_profile(profile)
    df = df.copy()
    df["model_score"] = df["pred_score"]

    if pf is None or not pf.factor_group_weights:
        return df

    dates = df["trade_date"]
    group_scores: list[pd.Series] = []

    for group_name, group_weight in pf.factor_group_weights.items():
        group_cfg = FACTOR_GROUPS.get(group_name)
        if group_cfg is None:
            continue

        columns = [c for c in group_cfg.get("columns", []) if c in feature_cols]
        if not columns:
            continue

        direction = int(group_cfg.get("direction", 1))
        winsorize = bool(group_cfg.get("winsorize", False))
        neutralize = bool(group_cfg.get("neutralize", False))

        ranked_cols: list[pd.Series] = []
        for col in columns:
            series = df[col].copy()
            if winsorize:
                series = _winsorize_series(series, dates)
            if neutralize:
                series = _neutralize_series(df, series)
            ranked_cols.append(_rank_pct(series, dates, direction=direction))

        group_score = pd.concat(ranked_cols, axis=1).mean(axis=1) * group_weight
        group_scores.append(group_score)

    if group_scores:
        df["factor_score"] = _zscore_within_date(sum(group_scores), dates)
    else:
        df["factor_score"] = 0.0

    df["pred_score"] = model_weight * df["model_score"] + factor_weight * df["factor_score"]
    return df
