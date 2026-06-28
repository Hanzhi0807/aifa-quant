"""Import source data from release assets into DuckDB.

Usage:
    python scripts/import_source_data.py data_store/aifa_quant_daily_quotes_2023_2024.csv.gz
    python scripts/import_source_data.py data_store
"""

import gzip
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd  # noqa: E402

from aifa_quant.config.settings import Settings  # noqa: E402
from aifa_quant.data.storage import DuckDBStore  # noqa: E402


def _import_csv_gz(store: DuckDBStore, csv_gz_path: Path, table: str) -> int:
    """Import a gzip CSV into the right DuckDB table."""
    if not csv_gz_path.exists():
        print(f"[skip] {csv_gz_path} not found")
        return 0

    print(f"Importing {csv_gz_path} into {table} ...")
    with gzip.open(csv_gz_path, "rt", encoding="utf-8") as f:
        df = pd.read_csv(f, parse_dates=["trade_date"] if table != "fundamental_data" else ["report_date"])

    if table == "fundamental_data":
        rows = store.save_fundamental_data(df)
    elif table == "macro_data":
        # macro CSV does not include indicator_name? It should. Let's ensure.
        if "indicator_name" not in df.columns and csv_gz_path.stem.endswith("macro_data_2023_2024"):
            # older export may not have indicator_name; skip
            pass
        rows = 0
        for indicator_name, group in df.groupby("indicator_name"):
            group = group.drop(columns=["indicator_name"])
            rows += store.save_macro_data(group, indicator_name)
    else:
        rows = store.save_daily_quotes(df)
    print(f"Imported {rows} rows into {table}")
    return rows


def import_source_data(path: str | Path) -> dict[str, int]:
    """Import source data from a file or directory."""
    path = Path(path).resolve()
    store = DuckDBStore(Settings())
    results: dict[str, int] = {}

    if path.is_dir():
        results["daily_quotes"] = _import_csv_gz(
            store, path / "aifa_quant_daily_quotes_2023_2024.csv.gz", "daily_quotes"
        )
        results["fundamental_data"] = _import_csv_gz(
            store, path / "aifa_quant_fundamental_data_2023_2024.csv.gz", "fundamental_data"
        )
        results["macro_data"] = _import_csv_gz(store, path / "aifa_quant_macro_data_2023_2024.csv.gz", "macro_data")
    else:
        # Single file import: infer table from filename.
        name = path.stem.replace(".csv", "")
        if "fundamental" in name:
            results["fundamental_data"] = _import_csv_gz(store, path, "fundamental_data")
        elif "macro" in name:
            results["macro_data"] = _import_csv_gz(store, path, "macro_data")
        else:
            results["daily_quotes"] = _import_csv_gz(store, path, "daily_quotes")

    return results


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "data_store"
    import_source_data(target)
