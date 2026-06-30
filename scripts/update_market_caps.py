"""Fetch A-share market-cap snapshot from AkShare and persist to stock_universe.

Usage:
    python scripts/update_market_caps.py

This populates circulating_share / total_share / circulating_mv / total_mv /
is_st / mc_snapshot_date on stock_universe rows.  Builder then estimates
historical market_cap as ``close × circulating_share`` for neutralization.

Notes:
    - Share counts change slowly (only on placement/buyback), so a periodic
      snapshot is a reasonable point-in-time proxy for historical estimation.
    - ``is_st`` is derived from the name containing 'ST' at snapshot time; a
      stock that was ST historically but has since been un-ST'd will be missed.
      For rigorous ST history, a dedicated ST-status history table is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script from anywhere.
_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from aifa_quant.config.settings import Settings
from aifa_quant.data.adapters.akshare_adapter import AkShareAdapter
from aifa_quant.data.storage import DuckDBStore


def main() -> int:
    settings = Settings()
    adapter = AkShareAdapter(settings)
    store = DuckDBStore(settings)

    print("[yellow]从 AkShare 拉取全市场市值+估值快照...[/yellow]", flush=True)
    try:
        df = adapter.get_market_cap_snapshot()
    except Exception as e:
        print(f"[red]拉取失败(重试已耗尽): {e}[/red]", flush=True)
        print("[yellow]东财服务器偶尔不可用,稍后重试即可。已有市值数据不会丢失。[/yellow]", flush=True)
        return 1
    if df.empty:
        print("[red]拉取返回空[/red]", flush=True)
        return 1
    print(f"[green]获取到 {len(df)} 只股票的快照[/green]", flush=True)

    n = store.update_market_caps(df)
    print(f"[green]已更新 {n} 条记录到 stock_universe (含市值+PE/PB/PS/DV)[/green]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
