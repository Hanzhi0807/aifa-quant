"""Fetch and persist CSI 300 / SSE Composite index quotes to DuckDB."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from aifa_quant.data.adapters.akshare_adapter import AkShareAdapter
from aifa_quant.data.storage.duckdb_store import DuckDBStore

INDEX_SYMBOLS = ["000300.SH", "000001.SH"]


def update_index_data(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    incremental: bool = False,
) -> dict[str, int]:
    """Fetch index OHLCV from AkShare and upsert into daily_quotes."""
    symbols = symbols or INDEX_SYMBOLS
    adapter = AkShareAdapter()
    store = DuckDBStore()

    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    results: dict[str, int] = {}
    for symbol in symbols:
        sym_start = start_date
        if incremental and not sym_start:
            max_date = store.get_max_trade_date(symbol)
            if max_date:
                next_date = max_date + timedelta(days=1)
                sym_start = next_date.strftime("%Y%m%d")
            else:
                sym_start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if not sym_start:
            sym_start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        df = adapter.get_index_data(symbol, start_date=sym_start, end_date=end_date)
        if df.empty:
            results[symbol] = 0
            continue
        rows = store.save_daily_quotes(df)
        results[symbol] = rows
        print(f"Updated {symbol}: {rows} rows ({df['trade_date'].min().date()} ~ {df['trade_date'].max().date()})")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update index benchmark data")
    parser.add_argument("--start", help="Start date YYYYMMDD")
    parser.add_argument("--end", help="End date YYYYMMDD")
    parser.add_argument("--symbols", nargs="+", default=INDEX_SYMBOLS, help="Index symbols")
    args = parser.parse_args()

    update_index_data(symbols=args.symbols, start_date=args.start, end_date=args.end)
