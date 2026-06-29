"""Push daily signals from DuckDB paper_positions to Supabase.

Reads current paper-trading positions from DuckDB and pushes them to Supabase
for the cloud dashboard. No intermediate CSV files needed.

Usage:
    python scripts/push_to_supabase.py [--profile balanced]

Environment variables required:
    SUPABASE_URL: Project URL (https://xxx.supabase.co)
    SUPABASE_SERVICE_ROLE_KEY: Service role key (not anon key)
"""

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from aifa_quant.config.settings import Settings
from aifa_quant.data.storage import DuckDBStore

ALL_PROFILES = ["aggressive", "balanced", "conservative", "value", "growth"]


def get_supabase_client():
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def table_columns(store: DuckDBStore, table: str) -> set[str]:
    """Return DuckDB table columns."""
    return {row[0] for row in store.conn.execute(f"DESCRIBE {table}").fetchall()}


def latest_trade_date(store: DuckDBStore, profile: str) -> str:
    """Use the latest persisted paper-trading date, not the wall-clock date."""
    nav_cols = table_columns(store, "paper_nav")
    if "profile" in nav_cols:
        row = store.conn.execute(
            "SELECT MAX(trade_date) FROM paper_nav WHERE profile = ?",
            [profile],
        ).fetchone()
    else:
        row = store.conn.execute("SELECT MAX(trade_date) FROM paper_nav").fetchone()

    value = row[0] if row else None
    if value is None:
        row = store.conn.execute("SELECT MAX(trade_date) FROM daily_quotes").fetchone()
        value = row[0] if row else None
    if value is None:
        raise RuntimeError("No trade_date found in paper_nav or daily_quotes")
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def load_positions_from_duckdb(store: DuckDBStore, profile: str, trade_date: str) -> pd.DataFrame:
    """Load current paper positions ordered by current market value."""
    cols = table_columns(store, "paper_positions")
    has_profile = "profile" in cols

    if has_profile:
        df = store.conn.execute(
            """
            SELECT p.symbol,
                   p.shares,
                   p.cost_basis,
                   COALESCE(u.name, p.symbol) AS name,
                   COALESCE(q.close, p.cost_basis) AS last_price,
                   p.shares * COALESCE(q.close, p.cost_basis) AS market_value
            FROM paper_positions p
            LEFT JOIN stock_universe u ON p.symbol = u.symbol
            LEFT JOIN daily_quotes q ON p.symbol = q.symbol AND q.trade_date = ?
            WHERE p.profile = ? AND p.shares > 0
            ORDER BY market_value DESC, p.symbol
            """,
            [trade_date, profile],
        ).fetchdf()
    else:
        df = store.conn.execute(
            """
            SELECT p.symbol,
                   p.shares,
                   p.cost_basis,
                   COALESCE(u.name, p.symbol) AS name,
                   COALESCE(q.close, p.cost_basis) AS last_price,
                   p.shares * COALESCE(q.close, p.cost_basis) AS market_value
            FROM paper_positions p
            LEFT JOIN stock_universe u ON p.symbol = u.symbol
            LEFT JOIN daily_quotes q ON p.symbol = q.symbol AND q.trade_date = ?
            WHERE p.shares > 0
            ORDER BY market_value DESC, p.symbol
            """,
            [trade_date],
        ).fetchdf()
    return df


def load_recent_orders(store: DuckDBStore, profile: str, days: int = 5) -> pd.DataFrame:
    """Load recent filled orders."""
    cols = table_columns(store, "paper_orders")
    has_profile = "profile" in cols
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    if has_profile:
        df = store.conn.execute(
            """
            SELECT symbol, side, quantity, fill_price, trade_date
            FROM paper_orders
            WHERE profile = ? AND status = 'filled'
              AND trade_date >= ?
            ORDER BY trade_date DESC, symbol
            """,
            [profile, cutoff],
        ).fetchdf()
    else:
        df = store.conn.execute(
            """
            SELECT symbol, side, quantity, fill_price, trade_date
            FROM paper_orders
            WHERE status = 'filled'
              AND trade_date >= ?
            ORDER BY trade_date DESC, symbol
            """,
            [cutoff],
        ).fetchdf()
    return df


def clear_cloud_snapshot(client, trade_date: str, profile: str) -> None:
    """Remove stale rows for a profile/date before writing a fresh snapshot."""
    for table in ("daily_signals", "portfolio"):
        client.table(table).delete().eq("trade_date", trade_date).eq("profile", profile).execute()


def push_signals(client, positions: pd.DataFrame, trade_date: str, profile: str) -> None:
    """Push current positions as daily signals."""
    if positions.empty:
        print(f"[{profile}] No positions to push as signals")
        return

    max_market_value = float(positions["market_value"].max()) if "market_value" in positions else 0.0
    records = []
    for i, (_, row) in enumerate(positions.iterrows(), 1):
        market_value = float(row.get("market_value") or 0.0)
        records.append(
            {
                "trade_date": trade_date,
                "symbol": row["symbol"],
                "name": row["name"] if pd.notna(row.get("name")) else "",
                "score": round(market_value / max_market_value, 4) if max_market_value > 0 else 0.0,
                "rank": i,
                "profile": profile,
            }
        )

    client.table("daily_signals").upsert(records, on_conflict="trade_date,symbol,profile").execute()
    print(f"[{profile}] Pushed {len(records)} signals for {trade_date}")


def push_portfolio(client, positions: pd.DataFrame, trade_date: str, profile: str) -> None:
    """Push current positions as portfolio holdings."""
    if positions.empty:
        print(f"[{profile}] No positions to push as portfolio")
        return

    total_market_value = float(positions["market_value"].sum()) if "market_value" in positions else 0.0
    records = []
    for _, row in positions.iterrows():
        market_value = float(row.get("market_value") or 0.0)
        last_price = float(row.get("last_price") or row["cost_basis"])
        records.append(
            {
                "trade_date": trade_date,
                "symbol": row["symbol"],
                "name": row["name"] if pd.notna(row.get("name")) else "",
                "action": "hold",
                "weight": round(market_value / total_market_value, 4) if total_market_value > 0 else 0.0,
                "reason": f"持仓 {int(row['shares'])} 股 | 最新价 {last_price:.2f} | 市值 {market_value:.2f}",
                "profile": profile,
            }
        )

    client.table("portfolio").upsert(records, on_conflict="trade_date,symbol,profile").execute()
    print(f"[{profile}] Pushed {len(records)} portfolio positions for {trade_date}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Push signals to Supabase from DuckDB")
    parser.add_argument("--profile", default=None, help="Strategy profile name (default: all)")
    args = parser.parse_args(argv)

    if args.profile and args.profile not in ALL_PROFILES:
        parser.error(f"--profile must be one of: {', '.join(ALL_PROFILES)}")

    profiles = [args.profile] if args.profile else ALL_PROFILES

    settings = Settings()
    store = DuckDBStore(settings)
    client = get_supabase_client()

    pushed = 0
    for profile in profiles:
        trade_date = latest_trade_date(store, profile)
        positions = load_positions_from_duckdb(store, profile, trade_date)
        clear_cloud_snapshot(client, trade_date, profile)
        if positions.empty:
            print(f"[{profile}] No positions found; cleared cloud snapshot for {trade_date}.")
            continue
        print(f"[{profile}] Found {len(positions)} positions for {trade_date}")
        push_signals(client, positions, trade_date, profile)
        push_portfolio(client, positions, trade_date, profile)
        pushed += 1

    if pushed == 0:
        print("No positions found for any profile, nothing pushed.")
    else:
        print(f"Done. Pushed {pushed} profile(s) to Supabase.")


if __name__ == "__main__":
    main()
