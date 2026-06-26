"""Local DuckDB storage for raw market data and features."""

import threading
from pathlib import Path

import duckdb
import pandas as pd

from ...config.settings import Settings


class DuckDBStore:
    """Simple DuckDB wrapper for quant data persistence."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.db_path = Path(self.settings.duckdb_path_abs)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # One connection per thread to avoid DuckDB concurrency errors.
        self._local = threading.local()

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = duckdb.connect(str(self.db_path))
            self._local.conn = conn
            self._init_tables(conn)
        return conn

    def _init_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create core tables if they do not exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_quotes (
                symbol VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                adj_factor DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, trade_date)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_universe (
                symbol VARCHAR PRIMARY KEY,
                name VARCHAR,
                industry VARCHAR,
                list_date DATE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fundamental_data (
                symbol VARCHAR NOT NULL,
                report_date DATE NOT NULL,
                name VARCHAR,
                pe_lyr DOUBLE,
                pb DOUBLE,
                pb_mrq DOUBLE,
                roe_deducted DOUBLE,
                roe_ttm DOUBLE,
                roe_weighted DOUBLE,
                roe_diluted DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, report_date)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS macro_data (
                indicator_name VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                value DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (indicator_name, trade_date)
            );
        """)

    def save_daily_quotes(self, df: pd.DataFrame) -> int:
        """Upsert daily quote data. Returns number of rows written."""
        if df.empty:
            return 0
        required = {"symbol", "trade_date", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns for daily_quotes: {missing}")

        # Ensure optional columns exist
        for col in ["open", "high", "low", "volume", "amount"]:
            if col not in df.columns:
                df[col] = float("nan")

        # Normalize column types
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        if "adj_factor" not in df.columns:
            df["adj_factor"] = float("nan")
        for col in ["open", "high", "low", "close", "volume", "amount", "adj_factor"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Register temp table and upsert
        self.conn.register("tmp_daily", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO daily_quotes
            SELECT symbol, trade_date, open, high, low, close, volume, amount, adj_factor, CURRENT_TIMESTAMP
            FROM tmp_daily;
        """)
        self.conn.unregister("tmp_daily")
        return len(df)

    def load_daily_quotes(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Load daily quotes from local storage."""
        query = "SELECT * FROM daily_quotes WHERE 1=1"
        params = []
        if symbols:
            placeholders = ", ".join(["?"] * len(symbols))
            query += f" AND symbol IN ({placeholders})"
            params.extend(symbols)
        if start_date:
            query += " AND trade_date >= ?"
            params.append(pd.to_datetime(start_date).date())
        if end_date:
            query += " AND trade_date <= ?"
            params.append(pd.to_datetime(end_date).date())
        query += " ORDER BY symbol, trade_date"
        return self.conn.execute(query, params).fetchdf()

    def get_max_trade_date(self, symbol: str) -> pd.Timestamp | None:
        """Return the latest stored trade date for a symbol."""
        result = self.conn.execute(
            "SELECT MAX(trade_date) FROM daily_quotes WHERE symbol = ?",
            [symbol],
        ).fetchone()
        if result and result[0]:
            return pd.Timestamp(result[0])
        return None

    def save_fundamental_data(self, df: pd.DataFrame) -> int:
        """Upsert quarterly fundamental/valuation data. Returns rows written."""
        if df.empty:
            return 0
        df = df.copy()
        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
        if "name" not in df.columns:
            df["name"] = None
        numeric_cols = ["pe_lyr", "pb", "pb_mrq", "roe_deducted", "roe_ttm", "roe_weighted", "roe_diluted"]
        for col in numeric_cols:
            if col not in df.columns:
                df[col] = float("nan")
            df[col] = pd.to_numeric(df[col], errors="coerce")
        self.conn.register("tmp_fundamental", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO fundamental_data
            SELECT symbol, report_date, name, pe_lyr, pb, pb_mrq,
                   roe_deducted, roe_ttm, roe_weighted, roe_diluted, CURRENT_TIMESTAMP
            FROM tmp_fundamental;
        """)
        self.conn.unregister("tmp_fundamental")
        return len(df)

    def load_fundamental_data(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Load cached fundamental data for given symbols and report date range."""
        query = "SELECT * FROM fundamental_data WHERE 1=1"
        params = []
        if symbols:
            placeholders = ", ".join(["?"] * len(symbols))
            query += f" AND symbol IN ({placeholders})"
            params.extend(symbols)
        if start_date:
            query += " AND report_date >= ?"
            params.append(pd.to_datetime(start_date).date())
        if end_date:
            query += " AND report_date <= ?"
            params.append(pd.to_datetime(end_date).date())
        query += " ORDER BY symbol, report_date"
        return self.conn.execute(query, params).fetchdf()

    def save_macro_data(self, df: pd.DataFrame, indicator_name: str) -> int:
        """Upsert macro indicator time series. Returns rows written."""
        if df.empty:
            return 0
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        if "value" in df.columns:
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["indicator_name"] = indicator_name
        self.conn.register("tmp_macro", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO macro_data
            SELECT indicator_name, trade_date, value, CURRENT_TIMESTAMP
            FROM tmp_macro;
        """)
        self.conn.unregister("tmp_macro")
        return len(df)

    def load_macro_data(
        self,
        indicator_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Load cached macro indicator data for a date range."""
        query = "SELECT * FROM macro_data WHERE indicator_name = ?"
        params = [indicator_name]
        if start_date:
            query += " AND trade_date >= ?"
            params.append(pd.to_datetime(start_date).date())
        if end_date:
            query += " AND trade_date <= ?"
            params.append(pd.to_datetime(end_date).date())
        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
