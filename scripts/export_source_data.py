"""Export raw data tables from DuckDB to compressed CSVs for release assets."""

import gzip
import sys
from pathlib import Path

# Allow running script directly from the repo root or scripts/ dir.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb  # noqa: E402

from aifa_quant.config.settings import Settings  # noqa: E402


def _export_table(con: duckdb.DuckDBPyConnection, table: str, output_path: Path) -> int:
    """Export a single table to a gzip-compressed CSV."""
    df = con.execute(f"SELECT * FROM {table} ORDER BY *").fetchdf()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        df.to_csv(f, index=False)
    print(f"Exported {len(df)} rows from {table} to {output_path}")
    return len(df)


def export_source_data(output_dir: str | Path) -> None:
    """Export daily_quotes, fundamental_data and macro_data to gzip CSVs."""
    settings = Settings()
    db_path = settings.duckdb_path_abs
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        _export_table(con, "daily_quotes", output_dir / "aifa_quant_daily_quotes_2023_2024.csv.gz")
        _export_table(con, "fundamental_data", output_dir / "aifa_quant_fundamental_data_2023_2024.csv.gz")
        _export_table(con, "macro_data", output_dir / "aifa_quant_macro_data_2023_2024.csv.gz")
    finally:
        con.close()


if __name__ == "__main__":
    export_source_data("data_store")
