"""Fetch all A-share stock names from AkShare and cache them in DuckDB.

This allows the web UI to display Chinese names alongside stock codes.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from aifa_quant.config.settings import Settings
from aifa_quant.data.adapters import AkShareAdapter
from aifa_quant.data.storage import DuckDBStore


def to_standard_symbol(code: str) -> str:
    code = str(code).strip()
    if len(code) == 6 and code.isdigit():
        return f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
    return code


def main():
    settings = Settings()
    store = DuckDBStore(settings)

    print("[INFO] 正在从 AkShare 获取 A股股票名称...")
    adapter = AkShareAdapter(settings)
    ak = adapter._ak

    # AkShare API: all A-share code -> name
    df = ak.stock_info_a_code_name()
    df.columns = [c.strip().lower() for c in df.columns]

    df["symbol"] = df["code"].apply(to_standard_symbol)
    df = df.rename(columns={"name": "name"})[["symbol", "name"]]
    df["name"] = df["name"].astype(str).str.strip()

    # Upsert into stock_universe
    store.conn.register("tmp_names", df)
    store.conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_universe (
            symbol VARCHAR PRIMARY KEY,
            name VARCHAR,
            industry VARCHAR,
            list_date DATE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    store.conn.execute("""
        INSERT OR REPLACE INTO stock_universe (symbol, name, updated_at)
        SELECT symbol, name, CURRENT_TIMESTAMP FROM tmp_names;
    """)
    store.conn.unregister("tmp_names")

    count = store.conn.execute("SELECT COUNT(*) FROM stock_universe").fetchone()[0]
    print(f"[OK] 已缓存 {count} 只股票名称到 stock_universe")


if __name__ == "__main__":
    main()
