"""每日自动刷新数据并生成最新 AI 选股信号。

设计给非技术用户：
  1. 增量更新沪深300/中证500/中证1000日线数据（2025年起）。
  2. 运行模拟交易，生成今日日度持仓。
  3. 生成每周选股报告，作为周度策略信号。

用法（需先激活 .venv）：
    python scripts/daily_refresh.py

Windows 任务计划程序：
    参考 scripts/daily_refresh.bat
"""

import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from aifa_quant.config.settings import Settings
from aifa_quant.data.pipeline.daily_update import DailyUpdatePipeline
from aifa_quant.data.storage import DuckDBStore
from scripts.update_index_data import update_index_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

INDEX_QUERIES = ["沪深300", "中证500", "中证1000"]
SUPABASE_PROFILE = "balanced"
# 策略计算需要年初以来的历史，2024 年及以前的数据不再需要
HISTORY_START = "20250101"


def push_to_supabase() -> None:
    """Push latest positions to Supabase for the web dashboard."""
    import os

    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        logger.info("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set, skipping push")
        return

    from scripts.push_to_supabase import main as push_main

    push_main()


def run_cli(*args: str) -> None:
    """Run a CLI command in the project virtual environment."""
    python = sys.executable
    cmd = [python, "-m", "aifa_quant.cli.main", *args]
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=project_root, check=True)


def fetch_combined_universe(pipeline: DailyUpdatePipeline) -> list[str]:
    """Fetch CSI300/500/1000 constituents and merge into a unique list."""
    symbols: set[str] = set()
    for query in INDEX_QUERIES:
        try:
            batch = pipeline.fetch_stock_universe(query)
            logger.info("%s 成分股: %d 只", query, len(batch))
            symbols.update(batch)
        except Exception as e:
            logger.error("获取 %s 成分股失败: %s", query, e)
    return sorted(symbols)


def update_stock_names(symbols: list[str]) -> int:
    """Make sure stock_universe has names for the given symbols."""
    try:
        import akshare as ak

        store = DuckDBStore()
        all_names = ak.stock_info_a_code_name()
        all_names.columns = [c.strip().lower() for c in all_names.columns]

        def to_standard(code: str) -> str:
            code = str(code).strip()
            if len(code) == 6 and code.isdigit():
                return f"{code}.{'SH' if code.startswith(('6', '5', '9')) else 'SZ'}"
            return code

        all_names["symbol"] = all_names["code"].apply(to_standard)
        name_map = dict(zip(all_names["symbol"], all_names["name"].astype(str)))

        rows = [(sym, name_map.get(sym, sym)) for sym in symbols]
        df = pd.DataFrame(rows, columns=["symbol", "name"])
        store.conn.register("tmp_names", df)
        store.conn.execute("""
            INSERT OR REPLACE INTO stock_universe (symbol, name, updated_at)
            SELECT symbol, name, CURRENT_TIMESTAMP FROM tmp_names;
        """)
        store.conn.unregister("tmp_names")
        logger.info("股票名称表更新完成: %d 只", len(rows))
        return len(rows)
    except Exception as e:
        logger.error("更新股票名称失败: %s", e)
        return 0


def update_daily_data(force: bool = False) -> int:
    """Incrementally update CSI300/500/1000 daily quotes from AkShare."""
    settings = Settings()
    pipeline = DailyUpdatePipeline(settings, max_workers=3, data_source="akshare")
    symbols = fetch_combined_universe(pipeline)
    logger.info("合并后选股池: %d 只", len(symbols))

    # Keep names in sync even on weekends
    update_stock_names(symbols)

    now = datetime.now()
    if not force and now.weekday() >= 5:
        logger.info("今日为周末/非交易日，跳过日线增量更新")
        return 0

    today = now.strftime("%Y%m%d")
    rows = pipeline.update_daily_quotes(
        symbols=symbols,
        start_date=HISTORY_START,
        end_date=today,
        incremental=True,
    )
    logger.info("日线数据更新完成: %d 条", rows)

    # Best-effort fundamental cache for new symbols
    try:
        pipeline.update_fundamental_data(symbols=symbols)
    except Exception as e:
        logger.warning("基本面数据更新失败（将继续）: %s", e)

    return rows


def main(force: bool = False, skip_paper_trade: bool = False) -> None:
    logger.info("===== AifaQuant 每日刷新开始 =====")
    logger.info("Project root: %s", project_root)

    try:
        update_daily_data(force=force)
    except Exception as e:
        logger.error("日线数据更新失败: %s", e)
        raise

    try:
        update_index_data(incremental=True)
        logger.info("指数基准数据更新已完成")
    except Exception as e:
        logger.error("指数基准数据更新失败: %s", e)
        raise

    if not skip_paper_trade:
        try:
            run_cli("paper-trade", "run", "--all-profiles")
            logger.info("所有策略模拟交易已完成")
        except Exception as e:
            logger.error("模拟交易失败: %s", e)
            raise

    # Push results to Supabase for web dashboard
    try:
        push_to_supabase()
        logger.info("Supabase 推送完成")
    except Exception as e:
        logger.warning("Supabase 推送失败（不影响本地数据）: %s", e)

    logger.info("===== AifaQuant 每日刷新完成 =====")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AifaQuant 每日数据刷新")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制刷新（忽略周末跳过逻辑）",
    )
    parser.add_argument(
        "--skip-paper-trade",
        action="store_true",
        help="只更新数据，不运行模拟交易",
    )
    args = parser.parse_args()

    main(force=args.force, skip_paper_trade=args.skip_paper_trade)
