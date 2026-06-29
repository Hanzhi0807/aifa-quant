"""Feature builder: raw quotes -> model features + labels."""

import pandas as pd

from ..config.settings import Settings
from ..data.adapters import EDBMCPAdapter, StockMCPAdapter, build_free_sentiment_features
from ..data.constants import INDEX_SYMBOLS
from ..data.storage import DuckDBStore
from ..data.validation import DataValidator
from .alpha_factors import compute_alpha_factors, list_alpha_factors
from .fundamental import merge_fundamental_to_daily
from .macro import merge_macro_to_daily
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
        nan_threshold: float = 0.5,
        include_fundamental: bool = True,
        include_macro: bool = True,
        include_sentiment: bool = True,
        sentiment_source: str = "ifind",
        include_alpha: bool = True,
        alpha_factors: list[str] | None = None,
        corr_threshold: float | None = 0.95,
        cache_only: bool = False,
        prediction_mode: bool = False,
    ) -> pd.DataFrame:
        """Build full feature matrix and label for modeling.

        Args:
            label_horizon: Number of days ahead for return label.
            nan_threshold: Drop feature columns with NaN ratio above this threshold.
            include_fundamental: Whether to merge PE/PB/ROE ratios from iFind.
            include_macro: Whether to merge macroeconomic indicators.
            include_sentiment: Whether to merge news sentiment factors from iFind.
            cache_only: If True, only use cached fundamental/macro data; do not call iFind for missing data.
            sentiment_source: "ifind" (default) or "free" (Eastmoney via AkShare).
            include_alpha: Whether to include Alpha101/191 style factors.
            alpha_factors: Optional subset of alpha factor names; None means all registered.
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

        # Optionally merge macro data
        if include_macro:
            print("[yellow]正在获取宏观数据（CPI/PMI/M2）...[/yellow]")
            edb = EDBMCPAdapter(self.settings)
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
                    print(f"[green]  {col_name}: 已命中缓存 ({len(cached_macro)} 条)[/green]")
                    raw = merge_macro_to_daily(raw, cached_macro, col_name)
                    continue

                if cache_only:
                    print(f"[yellow]  {col_name}: 缓存为空且 cache_only=True，跳过[/yellow]")
                    continue

                print(f"  从 iFind 拉取 {col_name}: {query}")
                try:
                    macro = edb.get_macro_data(query, start_date, end_date)
                    if not macro.empty:
                        self.store.save_macro_data(macro, col_name)
                        raw = merge_macro_to_daily(raw, macro, col_name)
                except Exception as e:
                    print(f"  [WARN] {col_name} 宏观数据获取失败: {e}")

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

        print(f"[green]特征矩阵形状: {df.shape}[/green]")

        if not prediction_mode:
            # Primary label: future N-day return
            df["label_return"] = df.groupby("symbol")["close"].shift(-label_horizon) / df["close"] - 1
            # Binary label: will future return be positive?
            df["label_binary"] = (df["label_return"] > 0).astype(int)

        # Drop feature columns with too many NaNs
        features = self.feature_columns(df)
        for col in features:
            if df[col].isna().mean() > nan_threshold:
                df = df.drop(columns=[col])

        # Fill remaining NaNs without looking forward. First use each symbol's
        # expanding median, then a date-level expanding median, then zero for
        # columns that have no historical observations yet.
        df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
        features = self.feature_columns(df)
        for col in features:
            df[col] = df.groupby("symbol")[col].transform(lambda x: x.fillna(x.expanding(min_periods=1).median()))
            date_median = df.groupby("trade_date")[col].median().sort_index().expanding(min_periods=1).median()
            df[col] = df[col].fillna(df["trade_date"].map(date_median))
            df[col] = df[col].fillna(0.0)

        if prediction_mode:
            df = df.dropna(subset=features)
        else:
            # Drop rows with missing label or any remaining NaN in features
            df = df.dropna(subset=["label_return"] + features)
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
        }
        cols = [c for c in df.columns if c not in exclude]
        # Exclude future returns (data leakage)
        cols = [c for c in cols if not c.startswith("future_return_")]
        return cols
