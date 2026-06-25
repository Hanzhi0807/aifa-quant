"""Feature builder: raw quotes -> model features + labels."""

import pandas as pd

from ..config.settings import Settings
from ..data.adapters import EDBMCPAdapter, StockMCPAdapter
from ..data.storage import DuckDBStore
from .fundamental import merge_fundamental_to_daily
from .macro import merge_macro_to_daily
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
        """Load raw daily quotes from DuckDB."""
        return self.store.load_daily_quotes(symbols, start_date, end_date)

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
    ) -> pd.DataFrame:
        """Build full feature matrix and label for modeling.

        Args:
            label_horizon: Number of days ahead for return label.
            nan_threshold: Drop feature columns with NaN ratio above this threshold.
            include_fundamental: Whether to merge PE/PB/ROE ratios from iFind.
            include_macro: Whether to merge macroeconomic indicators.
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
            adapter = StockMCPAdapter(self.settings)
            fin_frames = []
            symbols = raw["symbol"].unique()
            for i, symbol in enumerate(symbols, 1):
                print(f"  [{i}/{len(symbols)}] {symbol}")
                try:
                    fin = adapter.get_financial_data(symbol, start_date, end_date)
                    if not fin.empty:
                        fin_frames.append(fin)
                except Exception as e:
                    print(f"  [WARN] {symbol} 基本面数据获取失败: {e}")
            if fin_frames:
                financial = pd.concat(fin_frames, ignore_index=True)
                raw = merge_fundamental_to_daily(raw, financial)

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
                print(f"  获取 {col_name}: {query}")
                try:
                    macro = edb.get_macro_data(query, start_date, end_date)
                    if not macro.empty:
                        raw = merge_macro_to_daily(raw, macro, col_name)
                except Exception as e:
                    print(f"  [WARN] {col_name} 宏观数据获取失败: {e}")

        print("[yellow]正在构建技术因子...[/yellow]")
        frames = []
        for symbol, group in raw.groupby("symbol"):
            feat = self.build_per_symbol(group)
            feat["symbol"] = symbol
            frames.append(feat)

        df = pd.concat(frames, ignore_index=True)
        print(f"[green]特征矩阵形状: {df.shape}[/green]")

        # Primary label: future N-day return
        df["label_return"] = df.groupby("symbol")["close"].shift(-label_horizon) / df["close"] - 1
        # Binary label: will future return be positive?
        df["label_binary"] = (df["label_return"] > 0).astype(int)

        # Drop feature columns with too many NaNs
        features = self.feature_columns(df)
        for col in features:
            if df[col].isna().mean() > nan_threshold:
                df = df.drop(columns=[col])

        # Fill remaining NaNs with median per symbol, then global median
        features = self.feature_columns(df)
        for col in features:
            df[col] = df.groupby("symbol")[col].transform(lambda x: x.fillna(x.median()))
            df[col] = df[col].fillna(df[col].median())

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
            "label_return",
            "label_binary",
        }
        cols = [c for c in df.columns if c not in exclude]
        # Exclude future returns (data leakage)
        cols = [c for c in cols if not c.startswith("future_return_")]
        return cols
