"""Import daily quotes from a release asset into DuckDB.

Usage:
    python scripts/import_source_data.py data_store/aifa_quant_daily_quotes_2023_2024.csv.gz
"""

import gzip
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd  # noqa: E402

from aifa_quant.config.settings import Settings  # noqa: E402
from aifa_quant.data.storage import DuckDBStore  # noqa: E402


def import_daily_quotes(csv_gz_path: str | Path) -> int:
    """Import a gzip-compressed CSV of daily quotes into DuckDB."""
    csv_gz_path = Path(csv_gz_path).resolve()
    if not csv_gz_path.exists():
        raise FileNotFoundError(csv_gz_path)

    print(f"Importing {csv_gz_path} ...")
    with gzip.open(csv_gz_path, "rt", encoding="utf-8") as f:
        df = pd.read_csv(f, parse_dates=["trade_date"])

    store = DuckDBStore(Settings())
    rows = store.save_daily_quotes(df)
    print(f"Imported {rows} rows into {store.db_path}")
    return rows


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data_store/aifa_quant_daily_quotes_2023_2024.csv.gz"
    import_daily_quotes(path)
