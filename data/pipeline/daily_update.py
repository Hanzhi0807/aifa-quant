"""Daily data update pipeline from iFind MCP to DuckDB."""

from datetime import datetime, timedelta

from ...config.settings import Settings
from ..adapters import StockMCPAdapter
from ..storage import DuckDBStore


class DailyUpdatePipeline:
    """Incremental daily quote update pipeline."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.adapter = StockMCPAdapter(self.settings)
        self.store = DuckDBStore(self.settings)

    def fetch_stock_universe(
        self,
        query: str = "上证50成分股",
        sample_size: int | None = None,
    ) -> list[str]:
        """Fetch stock list from MCP. Falls back to a default sample on error."""
        try:
            df = self.adapter.get_stock_list(query)
            symbols = df.iloc[:, 0].astype(str).tolist()
            if sample_size:
                symbols = symbols[:sample_size]
            return symbols
        except Exception as e:
            print(f"[WARN] 获取股票列表失败: {e}，使用默认示例股票")
            return ["000001.SZ", "600000.SH", "000858.SZ", "600519.SH", "000333.SZ"]

    def update_daily_quotes(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        incremental: bool = True,
    ) -> int:
        """Update daily quotes for given symbols.

        Args:
            symbols: List of stock symbols. If None, fetch universe.
            start_date: Start date YYYYMMDD. If None and incremental, use latest stored date.
            end_date: End date YYYYMMDD. If None, use today.
            incremental: Only fetch missing data if True.
        """
        if symbols is None:
            symbols = self.fetch_stock_universe()

        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        total_rows = 0
        for symbol in symbols:
            try:
                sym_start = start_date
                if incremental and sym_start is None:
                    latest = self.store.get_max_trade_date(symbol)
                    if latest:
                        # Start from the day after the latest stored date
                        sym_start = (latest + timedelta(days=1)).strftime("%Y%m%d")
                    else:
                        sym_start = start_date

                # Skip if already up-to-date
                if sym_start and sym_start > end_date:
                    print(f"[SKIP] {symbol}: 已是最新数据")
                    continue

                df = self.adapter.get_daily_data(symbol, start_date=sym_start, end_date=end_date)
                if df.empty:
                    print(f"[WARN] {symbol}: 无数据")
                    continue

                rows = self.store.save_daily_quotes(df)
                total_rows += rows
                print(f"[OK] {symbol}: 新增/更新 {rows} 条")
            except Exception as e:
                print(f"[ERROR] {symbol}: {e}")

        return total_rows
