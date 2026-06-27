"""每日自动刷新数据并生成最新 AI 选股信号。

设计给非技术用户：
  1. 增量更新沪深 300 日线数据（只补缺失的日期，不重复下载全量）。
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

from aifa_quant.config.settings import Settings
from aifa_quant.data.pipeline.daily_update import DailyUpdatePipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_cli(*args: str) -> None:
    """Run a CLI command in the project virtual environment."""
    python = sys.executable
    cmd = [python, "-m", "aifa_quant.cli.main", *args]
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=project_root, check=True)


def update_daily_data() -> int:
    """Incrementally update CSI300 daily quotes from AkShare."""
    settings = Settings()
    pipeline = DailyUpdatePipeline(settings, max_workers=3, data_source="akshare")
    symbols = pipeline.fetch_stock_universe("沪深300")
    logger.info("沪深300成分股: %d 只", len(symbols))

    now = datetime.now()
    if now.weekday() >= 5:
        logger.info("今日为周末/非交易日，跳过日线增量更新")
        return 0

    today = now.strftime("%Y%m%d")
    rows = pipeline.update_daily_quotes(
        symbols=symbols,
        start_date=None,  # incremental from latest stored date
        end_date=today,
        incremental=True,
    )
    logger.info("日线数据更新完成: %d 条", rows)
    return rows


def main() -> None:
    logger.info("===== AifaQuant 每日刷新开始 =====")
    logger.info("Project root: %s", project_root)

    try:
        update_daily_data()
    except Exception as e:
        logger.error("日线数据更新失败: %s", e)
        raise

    try:
        run_cli("paper-trade", "run", "--all-profiles")
        logger.info("所有策略模拟交易已完成")
    except Exception as e:
        logger.error("模拟交易失败: %s", e)
        raise

    logger.info("===== AifaQuant 每日刷新完成 =====")


if __name__ == "__main__":
    main()
