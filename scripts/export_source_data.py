"""Export daily quotes from DuckDB to a compressed CSV for release assets."""

import gzip
import sys
from pathlib import Path

# Allow running script directly from the repo root or scripts/ dir.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
import pandas as pd

from aifa_quant.config.settings import Settings


def export_daily_quotes(output_path: str | Path) -> None:
    """Export daily_quotes table to a gzip-compressed CSV."""
    settings = Settings()
    db_path = settings.duckdb_path_abs
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path), read_only=True)
    df = con.execute("SELECT * FROM daily_quotes ORDER BY symbol, trade_date").fetchdf()
    con.close()

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        df.to_csv(f, index=False)

    print(f"Exported {len(df)} rows to {output_path}")


if __name__ == "__main__":
    export_daily_quotes("data_store/aifa_quant_daily_quotes_2023_2024.csv.gz")
