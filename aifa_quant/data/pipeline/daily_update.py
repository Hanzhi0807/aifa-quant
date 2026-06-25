"""Daily data update pipeline from iFind MCP to DuckDB."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd

from ...config.settings import Settings
from ..adapters import StockMCPAdapter
from ..storage import DuckDBStore


class RateLimiter:
    """Simple sliding-window rate limiter (requests per second)."""

    def __init__(self, max_requests: int = 5, window_seconds: float = 1.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._timestamps: list[float] = []

    def acquire(self) -> None:
        """Block until a request slot is available."""
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.pop(0)

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(time.monotonic())
                    return

                sleep_time = self._timestamps[0] + self.window_seconds - now
            if sleep_time > 0:
                time.sleep(sleep_time)


class DailyUpdatePipeline:
    """Incremental daily quote update pipeline."""

    def __init__(self, settings: Settings | None = None, max_workers: int = 3):
        self.settings = settings or Settings()
        self.adapter = StockMCPAdapter(self.settings)
        self.store = DuckDBStore(self.settings)
        self.max_workers = max_workers
        self._rate_limiter = RateLimiter(max_requests=5, window_seconds=1.0)

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

    def _resolve_symbol_window(
        self,
        symbol: str,
        start_date: str | None,
        end_date: str,
        incremental: bool,
    ) -> tuple[str, str | None]:
        """Return (symbol, effective_start_date) for the symbol."""
        sym_start = start_date
        if incremental and sym_start is None:
            latest = self.store.get_max_trade_date(symbol)
            if latest:
                sym_start = (latest + timedelta(days=1)).strftime("%Y%m%d")

        if sym_start and sym_start > end_date:
            return symbol, None
        return symbol, sym_start

    def update_daily_quotes(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        incremental: bool = True,
    ) -> int:
        """Update daily quotes for given symbols concurrently.

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

        # Resolve per-symbol date windows in single-threaded DB reads
        tasks = []
        for symbol in symbols:
            sym, sym_start = self._resolve_symbol_window(symbol, start_date, end_date, incremental)
            if sym_start is None:
                print(f"[SKIP] {sym}: 已是最新数据")
                continue
            tasks.append((sym, sym_start))

        total_rows = 0

        def fetch_one(symbol: str, sym_start: str) -> tuple[str, pd.DataFrame | None, Exception | None]:
            # Respect iFind MCP rate limit: 5 requests / second
            self._rate_limiter.acquire()
            try:
                df = self.adapter.get_daily_data(symbol, start_date=sym_start, end_date=end_date)
                return symbol, df, None
            except Exception as e:
                return symbol, None, e

        print(f"[INFO] 开始并发下载 {len(tasks)} 只股票，最大并发数 {self.max_workers}，限速 5 req/s", flush=True)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(fetch_one, sym, s): sym for sym, s in tasks}
            for future in as_completed(futures):
                symbol, df, error = future.result()
                if error is not None:
                    print(f"[ERROR] {symbol}: {error}", flush=True)
                    continue
                if df is None or df.empty:
                    print(f"[WARN] {symbol}: 无数据", flush=True)
                    continue
                try:
                    rows = self.store.save_daily_quotes(df)
                    total_rows += rows
                    print(f"[OK] {symbol}: 新增/更新 {rows} 条", flush=True)
                except Exception as e:
                    print(f"[ERROR] {symbol} 保存失败: {e}", flush=True)

        return total_rows
