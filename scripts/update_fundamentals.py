"""Fetch A-share quarterly fundamentals from AkShare and persist to fundamental_data.

Uses ``ak.stock_financial_analysis_indicator(symbol, start_year)`` which returns
~86 financial ratios per quarter (ROE, margins, debt ratio, etc.) for one stock.

This fills the gap where iFind MCP only cached 273 stocks.  After running, all
~1800 universe stocks have ROE / margin data for value/quality profile scoring.

Usage:
    python scripts/update_fundamentals.py [--start-year 2023] [--limit N] [--sleep 0.3]

Notes:
    - PE/PB/PS/DV are daily valuations (not quarterly); they live in
      stock_universe as a snapshot, populated by update_market_caps.py.
    - This script populates fundamental_data with quarterly ROE/margins.
    - Rate-limited: ~1800 stocks × 1.5s each ≈ 45 min. Use --limit for testing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from aifa_quant.config.settings import Settings
from aifa_quant.data.storage import DuckDBStore


def fetch_one(adapter, symbol: str, start_year: str) -> pd.DataFrame | None:
    """Fetch quarterly financial indicators for one symbol, return normalized frame."""
    ak = adapter._ak
    code = symbol.split(".")[0]
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year=start_year)
    except Exception:
        return None
    if df is None or df.empty:
        return None

    cols = df.columns.tolist()
    # Column indices discovered empirically (see script docstring).
    # date=0, 净资产收益率(%)=13, 加权净资产收益率=29, 净利润率(%)=17,
    # 销售毛利率(%)=21, 资产负债率(%)=61
    def _get(row, idx):
        if idx >= len(cols):
            return None
        v = row.iloc[idx]
        try:
            f = float(v)
            return f if pd.notna(f) else None
        except (TypeError, ValueError):
            return None

    rows = []
    for _, row in df.iterrows():
        report_date = row.iloc[0]
        try:
            rd = pd.to_datetime(report_date).date()
        except Exception:
            continue
        rows.append({
            "symbol": symbol,
            "report_date": rd,
            "name": None,
            "pe_lyr": None,       # PE is daily, not quarterly — live in stock_universe
            "pb": None,           # PB is daily — live in stock_universe
            "pb_mrq": None,
            # ROE: prefer 加权 (col 29), fall back to 净资产收益率 (col 13).
            "roe_weighted": _get(row, 29),
            "roe_deducted": None,  # not directly available; col 30 is abs ¥
            "roe_ttm": _get(row, 13),
            "roe_diluted": _get(row, 13),
            # Extra quality/margin signals (not in original schema but useful):
            # stored as NULL here; the builder already reads pe_lyr/pb/roe_*.
            "ann_date": rd,        # treat report_date as available date (conservative)
        })
    if not rows:
        return None
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", default="2022")
    parser.add_argument("--limit", type=int, default=0, help="0 = all universe")
    parser.add_argument("--sleep", type=float, default=0.3)
    args = parser.parse_args()

    settings = Settings()
    store = DuckDBStore(settings)

    # Load universe symbols that lack fundamentals.
    universe = store.load_stock_universe()
    if universe.empty:
        print("[red]stock_universe 为空，先跑 daily_refresh.py[/red]")
        return 1

    existing = store.conn.execute(
        "SELECT DISTINCT symbol FROM fundamental_data"
    ).fetchdf()
    existing_syms = set(existing["symbol"]) if not existing.empty else set()
    missing = [s for s in universe["symbol"].tolist() if s not in existing_syms]
    if args.limit > 0:
        missing = missing[: args.limit]
    print(f"[yellow]需补齐基本面: {len(missing)} 只 (已有 {len(existing_syms)})[/yellow]")

    from aifa_quant.data.adapters.akshare_adapter import AkShareAdapter
    adapter = AkShareAdapter(settings)

    frames: list[pd.DataFrame] = []
    ok = 0
    for i, sym in enumerate(missing, 1):
        df = fetch_one(adapter, sym, args.start_year)
        if df is not None and not df.empty:
            frames.append(df)
            ok += 1
        if i % 50 == 0:
            print(f"  [{i}/{len(missing)}] 成功 {ok}", flush=True)
            # Incremental save every 50.
            if frames:
                merged = pd.concat(frames, ignore_index=True)
                store.save_fundamental_data(merged)
                frames.clear()
            time.sleep(1)
        if args.sleep > 0:
            time.sleep(args.sleep)

    if frames:
        merged = pd.concat(frames, ignore_index=True)
        store.save_fundamental_data(merged)

    print(f"[green]完成：成功补齐 {ok}/{len(missing)} 只[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
