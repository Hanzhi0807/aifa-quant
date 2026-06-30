"""Local DuckDB storage for raw market data and features."""

import logging
import threading
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ...config.settings import Settings

logger = logging.getLogger(__name__)

# Module-level write lock. DuckDB allows concurrent readers but serializes writes;
# we guard all write paths through this lock to prevent "database is locked" errors
# when daily_refresh and the web server run simultaneously.
_WRITE_LOCK = threading.Lock()


class DuckDBStore:
    """Simple DuckDB wrapper for quant data persistence."""

    def __init__(self, settings: Settings | None = None, read_only: bool = False):
        self.settings = settings or Settings()
        self.db_path = Path(self.settings.duckdb_path_abs)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.read_only = read_only
        # One connection per thread to avoid DuckDB concurrency errors.
        self._local = threading.local()

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if self.read_only:
                conn = duckdb.connect(str(self.db_path), read_only=True)
            else:
                conn = duckdb.connect(str(self.db_path))
                self._init_tables(conn)
            self._local.conn = conn
        return conn

    def execute_write(self, sql: str, params: list[Any] | None = None) -> Any:
        """Execute a write statement under the global write lock."""
        with _WRITE_LOCK:
            if params is not None:
                return self.conn.execute(sql, params)
            return self.conn.execute(sql)

    def _init_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create core tables if they do not exist."""
        # Add columns to existing tables (safe migrations)
        for table in ["paper_positions", "paper_orders", "paper_nav"]:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN profile VARCHAR DEFAULT 'balanced'")
            except Exception:
                pass  # column already exists or table doesn't exist yet

        try:
            conn.execute("ALTER TABLE paper_pending_orders ADD COLUMN profile VARCHAR DEFAULT 'balanced'")
        except Exception:
            pass

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

        # Safe migrations: add market-cap columns to stock_universe if missing.
        for col, ddl in [
            ("circulating_share", "DOUBLE"),
            ("total_share", "DOUBLE"),
            ("circulating_mv", "DOUBLE"),
            ("total_mv", "DOUBLE"),
            ("is_st", "BOOLEAN"),
            ("mc_snapshot_date", "DATE"),
            ("pe_ttm", "DOUBLE"),
            ("pb_lyr", "DOUBLE"),
            ("ps_ttm", "DOUBLE"),
            ("dv_ratio", "DOUBLE"),
        ]:
            try:
                conn.execute(f"ALTER TABLE stock_universe ADD COLUMN {col} {ddl}")
            except Exception:
                pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fundamental_data (
                symbol VARCHAR NOT NULL,
                report_date DATE NOT NULL,
                ann_date DATE,
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

        try:
            conn.execute("ALTER TABLE fundamental_data ADD COLUMN ann_date DATE")
        except Exception:
            pass  # column already exists or table does not exist yet

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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_pending_orders (
                pending_id VARCHAR NOT NULL,
                profile VARCHAR NOT NULL DEFAULT 'balanced',
                signal_date DATE NOT NULL,
                symbol VARCHAR NOT NULL,
                side VARCHAR NOT NULL,
                quantity BIGINT NOT NULL,
                order_type VARCHAR NOT NULL,
                reason VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (profile, pending_id)
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

    def load_stock_universe(self, symbols: list[str] | None = None) -> pd.DataFrame:
        """Load stock universe metadata (name, industry, market cap, etc.)."""
        query = "SELECT * FROM stock_universe WHERE 1=1"
        params: list[Any] = []
        if symbols:
            placeholders = ", ".join(["?"] * len(symbols))
            query += f" AND symbol IN ({placeholders})"
            params.extend(symbols)
        query += " ORDER BY symbol"
        return self.conn.execute(query, params).fetchdf()

    def update_market_caps(self, df: pd.DataFrame) -> int:
        """Upsert circulating/total share, market cap, and valuation snapshot into stock_universe.

        Expects columns: symbol, circulating_share, total_share, circulating_mv,
        total_mv, is_st (optional), mc_snapshot_date (optional),
        pe_ttm / pb_lyr / ps_ttm / dv_ratio (optional valuations).
        Missing optional columns are filled with NULL.
        """
        if df.empty:
            return 0
        df = df.copy()
        for col in ["circulating_share", "total_share", "circulating_mv", "total_mv",
                    "pe_ttm", "pb_lyr", "ps_ttm", "dv_ratio"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = pd.NA
        if "is_st" not in df.columns:
            df["is_st"] = df.get("name", "").apply(lambda x: "ST" in str(x).upper() if x else False)
        if "mc_snapshot_date" not in df.columns:
            df["mc_snapshot_date"] = pd.Timestamp.now().normalize().date()
        df["mc_snapshot_date"] = pd.to_datetime(df["mc_snapshot_date"], errors="coerce").dt.date
        df["updated_at"] = pd.Timestamp.now()

        # Only keep columns we need for the UPDATE.
        update_cols = ["symbol", "circulating_share", "total_share", "circulating_mv",
                       "total_mv", "is_st", "mc_snapshot_date", "updated_at",
                       "pe_ttm", "pb_lyr", "ps_ttm", "dv_ratio"]
        update_df = df[[c for c in update_cols if c in df.columns]].copy()
        self.conn.register("tmp_mc", update_df)
        try:
            self.conn.execute("""
                UPDATE stock_universe AS t
                SET circulating_share = s.circulating_share,
                    total_share = s.total_share,
                    circulating_mv = s.circulating_mv,
                    total_mv = s.total_mv,
                    is_st = s.is_st,
                    mc_snapshot_date = s.mc_snapshot_date,
                    pe_ttm = s.pe_ttm,
                    pb_lyr = s.pb_lyr,
                    ps_ttm = s.ps_ttm,
                    dv_ratio = s.dv_ratio,
                    updated_at = s.updated_at
                FROM tmp_mc AS s
                WHERE t.symbol = s.symbol;
            """)
        finally:
            self.conn.unregister("tmp_mc")
        return len(df)

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
        if "ann_date" in df.columns:
            df["ann_date"] = pd.to_datetime(df["ann_date"], errors="coerce").dt.date
        else:
            df["ann_date"] = None
        if "name" not in df.columns:
            df["name"] = None
        numeric_cols = ["pe_lyr", "pb", "pb_mrq", "roe_deducted", "roe_ttm", "roe_weighted", "roe_diluted"]
        for col in numeric_cols:
            if col not in df.columns:
                df[col] = float("nan")
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # Keep only the columns the table expects, in the right order.
        ordered = df[["symbol", "report_date", "name", "pe_lyr", "pb", "pb_mrq",
                      "roe_deducted", "roe_ttm", "roe_weighted", "roe_diluted", "ann_date"]].copy()
        self.conn.register("tmp_fundamental", ordered)
        self.conn.execute("""
            INSERT OR REPLACE INTO fundamental_data
                (symbol, report_date, name, pe_lyr, pb, pb_mrq,
                 roe_deducted, roe_ttm, roe_weighted, roe_diluted, ann_date)
            SELECT symbol, report_date, name, pe_lyr, pb, pb_mrq,
                   roe_deducted, roe_ttm, roe_weighted, roe_diluted, ann_date
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
        return self.conn.execute(
            """
            SELECT symbol, shares, cost_basis, updated_at
            FROM paper_positions
            WHERE shares != 0 AND profile = ?
            ORDER BY symbol
        """,
            [profile],
        ).fetchdf()

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
        result = self.conn.execute(
            """
            SELECT cash FROM paper_nav WHERE profile = ? ORDER BY updated_at DESC LIMIT 1
        """,
            [profile],
        ).fetchone()
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
        with _WRITE_LOCK:
            self.conn.execute("DELETE FROM paper_positions WHERE profile = ?", [profile])
            self.conn.execute("DELETE FROM paper_orders WHERE profile = ?", [profile])
            self.conn.execute("DELETE FROM paper_nav WHERE profile = ?", [profile])
            self.conn.execute("DELETE FROM paper_pending_orders WHERE profile = ?", [profile])

    def save_paper_pending_orders(self, df: pd.DataFrame, profile: str = "balanced") -> int:
        if df.empty:
            return 0
        df = df.copy()
        df["profile"] = profile
        df["signal_date"] = pd.to_datetime(df["signal_date"], errors="coerce").dt.date
        if "created_at" not in df.columns:
            df["created_at"] = pd.Timestamp.now()
        self.conn.register("tmp_pending", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO paper_pending_orders
                (profile, pending_id, signal_date, symbol, side, quantity, order_type, reason, created_at)
            SELECT profile, pending_id, signal_date, symbol, side, quantity, order_type, reason, created_at
            FROM tmp_pending;
        """)
        self.conn.unregister("tmp_pending")
        return len(df)

    def load_paper_pending_orders(self, profile: str = "balanced") -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM paper_pending_orders WHERE profile = ? ORDER BY signal_date",
            [profile],
        ).fetchdf()

    def delete_paper_pending_order(self, pending_id: str, profile: str = "balanced") -> None:
        self.conn.execute(
            "DELETE FROM paper_pending_orders WHERE profile = ? AND pending_id = ?",
            [profile, pending_id],
        )

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
