"""Resume AkShare daily quote download for missing CSI300 symbols."""

import time
import duckdb
from aifa_quant.config.settings import Settings
from aifa_quant.data.adapters import AkShareAdapter
from aifa_quant.data.storage import DuckDBStore


def main():
    settings = Settings()
    store = DuckDBStore(settings)
    adapter = AkShareAdapter(settings)

    conn = duckdb.connect(str(store.db_path))
    try:
        existing = set(
            conn.execute("SELECT DISTINCT symbol FROM daily_quotes").fetchdf()["symbol"].tolist()
        )
    except Exception:
        existing = set()
    conn.close()

    universe = adapter.get_stock_universe("沪深300")
    missing = [s for s in universe if s not in existing]
    print(f"已有 {len(existing)} 只，目标 {len(universe)} 只，待下载 {len(missing)} 只")

    total_rows = 0
    for i, symbol in enumerate(missing, 1):
        try:
            df = adapter.get_daily_data(symbol, start_date="20230101", end_date="20241231")
            if df.empty:
                print(f"[{i}/{len(missing)}] {symbol}: 无数据")
                continue
            rows = store.save_daily_quotes(df)
            total_rows += rows
            print(f"[{i}/{len(missing)}] {symbol}: 写入 {rows} 条")
        except Exception as e:
            print(f"[{i}/{len(missing)}] {symbol}: 失败 {e}")
        time.sleep(0.5)

    # Final summary
    conn = duckdb.connect(str(store.db_path))
    cnt = conn.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM daily_quotes").fetchone()
    conn.close()
    print(f"完成：新增 {total_rows} 条；日线表共 {cnt[0]} 条，{cnt[1]} 只股票")


if __name__ == "__main__":
    main()
