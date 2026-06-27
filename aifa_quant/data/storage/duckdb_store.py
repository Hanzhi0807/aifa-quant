"""Local DuckDB storage for raw market data and features."""

import threading
from pathlib import Path
from typing import Any

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
        # Add profile column to existing tables (safe migration)
        for table in ["paper_positions", "paper_orders", "paper_nav"]:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN profile VARCHAR DEFAULT 'balanced'")
            except Exception:
                pass  # column already exists or table doesn't exist yet

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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_positions (
                symbol VARCHAR NOT NULL,
                profile VARCHAR NOT NULL DEFAULT 'balanced',
                shares BIGINT NOT NULL DEFAULT 0,
                cost_basis DOUBLE DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (profile, symbol)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_orders (
                order_id VARCHAR NOT NULL,
                profile VARCHAR NOT NULL DEFAULT 'balanced',
                trade_date DATE NOT NULL,
                symbol VARCHAR NOT NULL,
                side VARCHAR NOT NULL,
                quantity BIGINT NOT NULL,
                order_type VARCHAR NOT NULL,
                price DOUBLE,
                fill_price DOUBLE,
                commission DOUBLE DEFAULT 0.0,
                stamp_duty DOUBLE DEFAULT 0.0,
                status VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (profile, order_id)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_nav (
                trade_date DATE NOT NULL,
                profile VARCHAR NOT NULL DEFAULT 'balanced',
                cash DOUBLE NOT NULL,
                market_value DOUBLE NOT NULL,
                total_value DOUBLE NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (profile, trade_date)
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

    # ------------------------------------------------------------------
    # Paper trading state persistence
    # ------------------------------------------------------------------
    def load_paper_positions(self, profile: str = "balanced") -> pd.DataFrame:
        """Return current paper positions for a profile."""
        return self.conn.execute("""
            SELECT symbol, shares, cost_basis, updated_at
            FROM paper_positions
            WHERE shares != 0 AND profile = ?
            ORDER BY symbol
        """, [profile]).fetchdf()

    def save_paper_positions(self, df: pd.DataFrame, profile: str = "balanced") -> int:
        """Upsert paper positions for a profile."""
        if df.empty:
            return 0
        df = df.copy()
        df["profile"] = profile
        if "updated_at" not in df.columns:
            df["updated_at"] = pd.Timestamp.now()
        self.conn.register("tmp_positions", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO paper_positions (profile, symbol, shares, cost_basis, updated_at)
            SELECT profile, symbol, shares, cost_basis, updated_at
            FROM tmp_positions;
        """)
        self.conn.unregister("tmp_positions")
        return len(df)

    def load_paper_cash(self, profile: str = "balanced") -> float | None:
        result = self.conn.execute("""
            SELECT cash FROM paper_nav WHERE profile = ? ORDER BY updated_at DESC LIMIT 1
        """, [profile]).fetchone()
        return result[0] if result else None

    def save_paper_nav(self, df: pd.DataFrame, profile: str = "balanced") -> int:
        if df.empty:
            return 0
        df = df.copy()
        df["profile"] = profile
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        for col in ["cash", "market_value", "total_value"]:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "updated_at" not in df.columns:
            df["updated_at"] = pd.Timestamp.now()
        self.conn.register("tmp_nav", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO paper_nav (profile, trade_date, cash, market_value, total_value, updated_at)
            SELECT profile, trade_date, cash, market_value, total_value, updated_at
            FROM tmp_nav;
        """)
        self.conn.unregister("tmp_nav")
        return len(df)

    def load_paper_nav(self, profile: str = "balanced", trade_date: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM paper_nav WHERE profile = ?"
        params: list[Any] = [profile]
        if trade_date:
            query += " AND trade_date = ?"
            params.append(pd.to_datetime(trade_date).date())
        query += " ORDER BY trade_date"
        return self.conn.execute(query, params).fetchdf()

    def save_paper_orders(self, df: pd.DataFrame, profile: str = "balanced") -> int:
        if df.empty:
            return 0
        df = df.copy()
        df["profile"] = profile
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        if df["trade_date"].isna().any():
            df["trade_date"] = df["trade_date"].fillna(pd.Timestamp.now().normalize())
        df["trade_date"] = df["trade_date"].dt.date
        numeric_cols = ["price", "fill_price", "commission", "stamp_duty"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "created_at" not in df.columns:
            df["created_at"] = pd.Timestamp.now()
        self.conn.register("tmp_orders", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO paper_orders (profile, order_id, trade_date, symbol, side, quantity, order_type,
                   price, fill_price, commission, stamp_duty, status, created_at)
            SELECT profile, order_id, trade_date, symbol, side, quantity, order_type,
                   price, fill_price, commission, stamp_duty, status, created_at
            FROM tmp_orders;
        """)
        self.conn.unregister("tmp_orders")
        return len(df)

    def load_paper_orders(self, profile: str = "balanced", status: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM paper_orders WHERE profile = ?"
        params: list[Any] = [profile]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at"
        return self.conn.execute(query, params).fetchdf()

    def clear_paper_state(self, profile: str = "balanced") -> None:
        """Truncate all paper trading tables for a profile."""
        self.conn.execute("DELETE FROM paper_positions WHERE profile = ?", [profile])
        self.conn.execute("DELETE FROM paper_orders WHERE profile = ?", [profile])
        self.conn.execute("DELETE FROM paper_nav WHERE profile = ?", [profile])

    def get_latest_trade_date(self) -> pd.Timestamp | None:
        """Return the latest trade_date stored in daily_quotes across all symbols."""
        result = self.conn.execute("SELECT MAX(trade_date) FROM daily_quotes").fetchone()
        if result and result[0]:
            return pd.Timestamp(result[0])
        return None

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
