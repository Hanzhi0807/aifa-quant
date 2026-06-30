"""Feature builder: raw quotes -> model features + labels."""

import logging
import warnings

import pandas as pd

from ..config.settings import Settings
from ..data.adapters import AkShareAdapter, EDBMCPAdapter, StockMCPAdapter, build_free_sentiment_features
from ..data.constants import INDEX_SYMBOLS
from ..data.storage import DuckDBStore
from ..data.validation import DataValidator
from .alpha_factors import compute_alpha_factors, list_alpha_factors
from .fundamental import merge_fundamental_to_daily
from .labels import compute_labels
from .macro import merge_macro_to_daily
from .neutralization import neutralize_cross_section
from .sentiment import build_sentiment_features, merge_sentiment_to_daily
from .technical import (
    compute_atr,
    compute_macd,
    compute_moving_averages,
    compute_returns,
    compute_rsi,
    compute_volatility,
    compute_volume_features,
)

logger = logging.getLogger(__name__)


class FeatureBuilder:
    """Build cross-sectional feature matrix from stored daily quotes."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.store = DuckDBStore(self.settings)

    def load_raw_data(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Load raw daily quotes from DuckDB and validate them."""
        df = self.store.load_daily_quotes(symbols, start_date, end_date)
        # Exclude benchmark indices from the feature matrix so they are never picked as stocks
        if not df.empty and "symbol" in df.columns:
            df = df[~df["symbol"].isin(INDEX_SYMBOLS)].copy()
        return DataValidator.validate_daily_quotes(df)

    @staticmethod
    def build_per_symbol(df: pd.DataFrame) -> pd.DataFrame:
        """Build features for a single symbol's time series."""
        df = df.sort_values("trade_date").copy()
        df = compute_returns(df)
        df = compute_moving_averages(df)
        df = compute_volatility(df)
        df = compute_rsi(df)
        df = compute_macd(df)
        df = compute_volume_features(df)
        df = compute_atr(df)
        return df

    def build_features(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        label_horizon: int = 5,
        label_type: str = "excess_quantile",
        drop_middle: bool = False,
        pt_mult: float = 2.0,
        sl_mult: float = 1.0,
        max_holding: int = 10,
        nan_threshold: float = 0.5,
        include_fundamental: bool = True,
        include_macro: bool = True,
        include_sentiment: bool = True,
        sentiment_source: str = "ifind",
        include_alpha: bool = True,
        alpha_factors: list[str] | None = None,
        neutralize: bool = True,
        corr_threshold: float | None = 0.95,
        cache_only: bool = False,
        prediction_mode: bool = False,
    ) -> pd.DataFrame:
        """Build full feature matrix and label for modeling.

        Args:
            label_horizon: Number of days ahead for return label.
            label_type: Label scheme: 'excess_quantile' (default), 'triple_barrier', 'binary'.
            drop_middle: For excess_quantile; drop middle quantile of each cross-section.
            pt_mult: For triple_barrier; profit-taking ATR multiplier.
            sl_mult: For triple_barrier; stop-loss ATR multiplier.
            max_holding: For triple_barrier; maximum holding period in days.
            nan_threshold: Drop feature columns with NaN ratio above this threshold.
            include_fundamental: Whether to merge PE/PB/ROE ratios from iFind.
            include_macro: Whether to merge macroeconomic indicators.
            include_sentiment: Whether to merge news sentiment factors from iFind.
            cache_only: If True, do not call paid/custom missing-data sources; missing macro cache may use AkShare fallback.
            sentiment_source: "ifind" (default) or "free" (Eastmoney via AkShare).
            include_alpha: Whether to include Alpha101/191 style factors.
            alpha_factors: Optional subset of alpha factor names; None means all registered.
            neutralize: Whether to neutralize alpha factors and momentum/volatility factors
                against industry dummies and log(market_cap).
            corr_threshold: Retained for CLI compatibility; rolling trainers apply feature selection inside each train window.
        """
        print("[yellow]正在从 DuckDB 加载原始日线数据...[/yellow]")
        raw = self.load_raw_data(symbols, start_date, end_date)
        print(f"[green]已加载 {len(raw)} 条日线数据，{raw['symbol'].nunique()} 只股票[/green]")
        if raw.empty:
            return raw

        # Ensure required columns
        for col in ["open", "high", "low", "volume", "amount"]:
            if col not in raw.columns:
                raw[col] = float("nan")

        # Ensure auxiliary columns needed for neutralization are available
        if neutralize:
            # Always try to attach market_cap and industry from stock_universe,
            # because daily_quotes rarely carries outstanding_share.
            try:
                universe = self.store.load_stock_universe()
            except Exception as e:
                warnings.warn(f"Unable to load stock_universe: {e}; neutralization will be limited.")
                universe = pd.DataFrame()

            if "market_cap" not in raw.columns and not universe.empty:
                # Estimate historical market cap = close × circulating_share (snapshot).
                # Share count changes slowly, so this is a reasonable point-in-time proxy.
                if "circulating_share" in universe.columns:
                    mc_map = dict(zip(universe["symbol"], pd.to_numeric(universe["circulating_share"], errors="coerce")))
                    close = pd.to_numeric(raw["close"], errors="coerce")
                    raw["market_cap"] = close * raw["symbol"].map(mc_map)
                    if raw["market_cap"].isna().all():
                        warnings.warn(
                            "circulating_share present in stock_universe but all NaN; "
                            "market_cap unavailable. Run scripts/update_market_caps.py. "
                            "Neutralization will degrade to winsorize+z-score only.",
                        )
                else:
                    warnings.warn(
                        "circulating_share not in stock_universe; run scripts/update_market_caps.py. "
                        "Neutralization will degrade to winsorize+z-score only.",
                    )

            if "industry" not in raw.columns and not universe.empty and "industry" in universe.columns:
                raw = raw.merge(universe[["symbol", "industry"]], on="symbol", how="left")
            elif "industry" not in raw.columns:
                warnings.warn("Industry data not available in stock_universe; skipping industry dummies.")

        # Optionally merge fundamental data
        if include_fundamental:
            print("[yellow]正在获取基本面数据（PE/PB/ROE）...[/yellow]")
            symbols = raw["symbol"].unique().tolist()
            fundamental_start = (
                (pd.to_datetime(start_date) - pd.Timedelta(days=370)).strftime("%Y%m%d")
                if start_date
                else None
            )
            cached_fundamental = self.store.load_fundamental_data(symbols, fundamental_start, end_date)
            cached_symbols = set(cached_fundamental["symbol"].unique()) if not cached_fundamental.empty else set()
            missing_symbols = [s for s in symbols if s not in cached_symbols]

            if missing_symbols and not cache_only:
                adapter = StockMCPAdapter(self.settings)
                fetched_frames = []
                for i, symbol in enumerate(missing_symbols, 1):
                    print(f"  [{i}/{len(missing_symbols)}] {symbol} 从 iFind 拉取")
                    try:
                        fin = adapter.get_financial_data(symbol, start_date, end_date)
                        if not fin.empty:
                            fetched_frames.append(fin)
                    except Exception as e:
                        print(f"  [WARN] {symbol} 基本面数据获取失败: {e}")
                if fetched_frames:
                    fetched = pd.concat(fetched_frames, ignore_index=True)
                    self.store.save_fundamental_data(fetched)
                    cached_fundamental = pd.concat([cached_fundamental, fetched], ignore_index=True)
            elif missing_symbols:
                print(
                    f"[yellow]缓存仅覆盖 {len(cached_symbols)}/{len(symbols)} 只股票，"
                    f"剩余 {len(missing_symbols)} 只因 cache_only 跳过拉取[/yellow]"
                )
            else:
                print(f"[green]已命中缓存：{len(cached_symbols)} 只股票的基本面数据[/green]")

            if not cached_fundamental.empty:
                raw = merge_fundamental_to_daily(raw, cached_fundamental)

            # Also attach the daily valuation snapshot (PE/PB/PS/DV) from
            # stock_universe.  These are current-snapshot values (not point-in-time
            # historical), so they are most appropriate in prediction mode; in
            # backtests they introduce mild look-ahead.  We name them _snap to
            # distinguish from the quarterly pe_lyr/pb above.
            try:
                snap_cols = ["symbol", "pe_ttm", "pb_lyr", "ps_ttm", "dv_ratio"]
                snap = self.store.load_stock_universe()[snap_cols]
                snap = snap.rename(columns={"pe_ttm": "pe_snap", "pb_lyr": "pb_snap",
                                            "ps_ttm": "ps_snap", "dv_ratio": "dv_snap"})
                raw = raw.merge(snap, on="symbol", how="left")
            except Exception as e:
                warnings.warn(f"Unable to merge valuation snapshot: {e}")

        # Optionally merge macro data
        if include_macro:
            print("[yellow]Fetching macro data (CPI/PMI/M2)...[/yellow]")
            free_macro_adapter: AkShareAdapter | None = None
            edb: EDBMCPAdapter | None = None
            macro_indicators = {
                "cpi_yoy": "中国CPI同比",
                "pmi": "中国PMI",
                "m2_yoy": "中国M2同比",
            }
            for col_name, query in macro_indicators.items():
                macro_start = (
                    (pd.to_datetime(start_date) - pd.Timedelta(days=90)).strftime("%Y%m%d")
                    if start_date
                    else None
                )
                cached_macro = self.store.load_macro_data(col_name, macro_start, end_date)
                if not cached_macro.empty:
                    print(f"[green]  {col_name}: cache hit ({len(cached_macro)} rows)[/green]")
                    raw = merge_macro_to_daily(raw, cached_macro, col_name)
                    continue

                macro = pd.DataFrame(columns=["trade_date", "value"])
                if cache_only:
                    print(f"[yellow]  {col_name}: cache empty; trying AkShare macro fallback[/yellow]")
                    try:
                        if free_macro_adapter is None:
                            free_macro_adapter = AkShareAdapter(self.settings)
                        macro = free_macro_adapter.get_macro_data(col_name, macro_start, end_date)
                    except Exception as e:
                        print(f"  [WARN] {col_name} AkShare macro fallback failed: {e}")

                    if macro.empty:
                        print(f"[yellow]  {col_name}: no cached/free macro data; skipping[/yellow]")
                        continue

                    self.store.save_macro_data(macro, col_name)
                    print(f"[green]  {col_name}: fetched {len(macro)} rows from AkShare fallback[/green]")
                    raw = merge_macro_to_daily(raw, macro, col_name)
                    continue

                print(f"  Fetching {col_name} from configured macro data source: {query}")
                try:
                    if edb is None:
                        edb = EDBMCPAdapter(self.settings)
                    macro = edb.get_macro_data(query, macro_start, end_date)
                except Exception as e:
                    print(f"  [WARN] {col_name} configured macro source failed: {e}")

                if macro.empty:
                    print(f"[yellow]  {col_name}: configured source empty; trying AkShare macro fallback[/yellow]")
                    try:
                        if free_macro_adapter is None:
                            free_macro_adapter = AkShareAdapter(self.settings)
                        macro = free_macro_adapter.get_macro_data(col_name, macro_start, end_date)
                    except Exception as e:
                        print(f"  [WARN] {col_name} AkShare macro fallback failed: {e}")

                if not macro.empty:
                    self.store.save_macro_data(macro, col_name)
                    raw = merge_macro_to_daily(raw, macro, col_name)
                else:
                    print(f"[yellow]  {col_name}: no macro data available; skipping[/yellow]")
        # Optionally merge sentiment data
        if include_sentiment:
            print(f"[yellow]正在获取情绪因子（来源：{sentiment_source}）...[/yellow]")
            try:
                symbols = raw["symbol"].unique()
                if sentiment_source == "free":
                    sentiment = build_free_sentiment_features(
                        symbols.tolist(),
                        start_date=start_date,
                        end_date=end_date,
                        settings=self.settings,
                    )
                else:
                    name_map = (
                        raw.drop_duplicates("symbol").set_index("symbol")["name"].to_dict()
                        if "name" in raw.columns
                        else None
                    )
                    sentiment = build_sentiment_features(
                        symbols.tolist(),
                        name_map=name_map,
                        start_date=start_date,
                        end_date=end_date,
                        settings=self.settings,
                        cache_only=cache_only,
                    )
                if not sentiment.empty:
                    raw = merge_sentiment_to_daily(raw, sentiment)
                    print(f"[green]已合并情绪因子，覆盖 {sentiment['symbol'].nunique()} 只股票[/green]")
            except Exception as e:
                print(f"  [WARN] 情绪因子获取失败: {e}")

        print("[yellow]正在构建技术因子...[/yellow]")
        # Use groupby.apply for vectorized per-symbol computation instead of a Python for-loop.
        # pandas 3.x drops the grouping column with group_keys=False; reset_index to recover it.
        df = raw.groupby("symbol").apply(self.build_per_symbol, include_groups=False)
        df = df.reset_index()
        if "level_1" in df.columns:
            df = df.drop(columns=["level_1"])

        if include_alpha:
            print(f"[yellow]正在构建 Alpha101/191 因子（{len(alpha_factors or list_alpha_factors())} 个）...[/yellow]")
            df = compute_alpha_factors(df, selected=alpha_factors)

        if neutralize:
            print("[yellow]正在进行行业与市值中性化...[/yellow]")
            alpha_names = [name for name in (alpha_factors or list_alpha_factors()) if name in df.columns]
            tech_candidates = [c for c in df.columns if "momentum" in c or "volatility" in c]
            neutral_cols = list(dict.fromkeys(alpha_names + tech_candidates))
            if neutral_cols:
                df = neutralize_cross_section(df, neutral_cols)
            # Keep industry / market_cap for downstream profile scoring; they are
            # explicitly excluded from model feature columns below.

        print(f"[green]特征矩阵形状: {df.shape}[/green]")

        if not prediction_mode:
            df = compute_labels(
                df,
                label_type=label_type,
                label_horizon=label_horizon,
                drop_middle=drop_middle,
                pt_mult=pt_mult,
                sl_mult=sl_mult,
                max_holding=max_holding,
            )

        # Drop feature columns with too many NaNs
        features = self.feature_columns(df)
        for col in features:
            if df[col].isna().mean() > nan_threshold:
                df = df.drop(columns=[col])

        # Fill remaining NaNs without looking forward. Order of fallback:
        #   1. each symbol's own expanding median (only past values)
        #   2. the cross-sectional median for the same trade_date (known at T close)
        #   3. 0.0 as a last resort
        # The previous implementation used df[col].median() — the *global* median
        # across all dates — which leaks future information into earlier rows.
        df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
        features = self.feature_columns(df)
        for col in features:
            df[col] = df.groupby("symbol")[col].transform(lambda x: x.fillna(x.expanding(min_periods=1).median()))
            # Cross-sectional median per trade_date is observable at T close.
            cross_sectional = df.groupby("trade_date")[col].transform("median")
            df[col] = df[col].fillna(cross_sectional)
            nan_ratio = df[col].isna().mean()
            if nan_ratio > 0.3:
                logger.warning(f"Feature {col} has {nan_ratio:.0%} NaN after filling — possible data issue")
            df[col] = df[col].fillna(0.0)

        if prediction_mode:
            df = df.dropna(subset=features)
        else:
            # Drop rows with missing label or any remaining NaN in features
            df = df.dropna(subset=["label_rank"] + features)
        return df

    def feature_columns(self, df: pd.DataFrame) -> list[str]:
        """Return list of feature column names (excluding metadata, labels, and leaked future returns)."""
        exclude = {
            "symbol",
            "name",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "adj_factor",
            "created_at",
            "report_date",
            "ann_date",
            "label_return",
            "label_binary",
            "label_rank",
            "label_excess",
            "label_outcome",
            "industry",
            "market_cap",
        }
        cols = [c for c in df.columns if c not in exclude]
        # Exclude future returns (data leakage)
        cols = [c for c in cols if not c.startswith("future_return_")]
        return cols
