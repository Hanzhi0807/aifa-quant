"""Local DuckDB storage for raw market data and features."""

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
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._closed = True

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None or self._closed:
            self._conn = duckdb.connect(str(self.db_path))
            self._closed = False
            self._init_tables()
        return self._conn

    def _init_tables(self) -> None:
        """Create core tables if they do not exist."""
        self._conn.execute("""
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

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_universe (
                symbol VARCHAR PRIMARY KEY,
                name VARCHAR,
                industry VARCHAR,
                list_date DATE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def close(self) -> None:
        if self._conn and not self._closed:
            self._conn.close()
            self._closed = True
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
