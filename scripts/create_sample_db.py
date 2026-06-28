"""Create a temporary DuckDB containing a subset of symbols for quick experiments."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import duckdb  # noqa: E402

from aifa_quant.config.settings import Settings  # noqa: E402


def create_sample_db(sample_symbols: list[str], dst_path: str | Path) -> None:
    """Clone daily_quotes for sample_symbols + benchmark from main DB to dst_path."""
    settings = Settings()
    src = settings.duckdb_path_abs
    dst = Path(dst_path).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()

    src_con = duckdb.connect(str(src), read_only=True)
    schema = src_con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='daily_quotes'").fetchone()
    if schema is None:
        raise RuntimeError("daily_quotes table not found in source DB")

    dst_con = duckdb.connect(str(dst))
    dst_con.execute(schema[0])

    symbols = list(set(sample_symbols) | {"000300.SH"})
    placeholder = ",".join(["?"] * len(symbols))
    rows = src_con.execute(
        f"SELECT * FROM daily_quotes WHERE symbol IN ({placeholder})",
        symbols,
    ).fetchall()
    columns = [desc[0] for desc in src_con.description]

    import pandas as pd

    df = pd.DataFrame(rows, columns=columns)
    dst_con.register("tmp_df", df)
    dst_con.execute("INSERT INTO daily_quotes SELECT * FROM tmp_df")
    dst_con.close()
    src_con.close()
    print(f"Created {dst} with {len(df)} rows across {df['symbol'].nunique()} symbols")


if __name__ == "__main__":
    sample = Path("data_store/csi300_symbols.txt").read_text(encoding="utf-8").splitlines()[:30]
    create_sample_db(sample, "data_store/aifa_quant_sample.duckdb")
