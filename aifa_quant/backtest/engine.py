"""Lightweight event-driven backtest engine for A-shares."""

from dataclasses import dataclass

import pandas as pd

from ..core.trading_config import TradingConfig
from ..models.base import BaseModel
from ..strategy.base import BaseStrategy

# Model may be omitted when pred_score is already provided by rolling trainer.
ModelType = BaseModel | None


@dataclass
class Position:
    symbol: str
    shares: int = 0
    cost_basis: float = 0.0


@dataclass
class Trade:
    trade_date: pd.Timestamp
    symbol: str
    action: str  # BUY or SELL
    shares: int
    price: float
    amount: float


class BacktestEngine:
    """Simple backtest engine supporting A-share rules."""

    def __init__(
        self,
        config: TradingConfig | None = None,
        initial_cash: float = 1_000_000.0,
        commission_rate: float = 0.0003,
        stamp_duty_rate: float = 0.001,  # A-share sell-side stamp duty
        min_commission: float = 5.0,
        slippage: float = 0.0,
        rebalance_freq: int = 5,
        regime_ma_threshold: float = 0.0,
        industry_map: dict[str, str] | None = None,
        st_symbols: set[str] | None = None,
        weighting: str = "equal",  # "equal" | "qp"
        optimizer: "MeanVarianceOptimizer | None" = None,
    ):
        if config is None:
            config = TradingConfig(
                initial_cash=initial_cash,
                commission_rate=commission_rate,
                stamp_duty_rate=stamp_duty_rate,
                min_commission=min_commission,
                slippage=slippage,
                rebalance_freq=rebalance_freq,
            )
        self.config = config
        self.initial_cash = config.initial_cash
        self.commission_rate = config.commission_rate
        self.stamp_duty_rate = config.stamp_duty_rate
        self.min_commission = config.min_commission
        self.slippage = config.slippage
        self.rebalance_freq = config.rebalance_freq
        self.regime_ma_threshold = regime_ma_threshold
        self.industry_map = industry_map
        # Symbols flagged ST (e.g. from stock_universe.name containing 'ST').
        # Used to apply the 5% limit instead of 10%/20%.
        self.st_symbols: set[str] = set(st_symbols) if st_symbols else set()
        # Portfolio weighting mode: "equal" (default) or "qp" (mean-variance).
        self.weighting = weighting
        self.optimizer = optimizer
        # Cached daily returns for covariance estimation (qp mode).
        self._returns_cache: pd.DataFrame | None = None

        self.cash: float = self.initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.daily_values: list[dict] = []

        self.quotes_by_date: dict[pd.Timestamp, pd.DataFrame] = {}
        self.prev_day_quotes: pd.DataFrame | None = None
        self._last_known_price: dict[str, float] = {}
        self._index_closes: list[float] = []  # for regime detection

    def reset(self) -> None:
        self.cash = self.initial_cash
        self.positions = {}
        self.trades = []
        self.daily_values = []
        self.quotes_by_date = {}
        self.prev_day_quotes = None
        self._last_known_price = {}
        self._index_closes = []

    def run(
        self,
        quotes: pd.DataFrame,
        features: pd.DataFrame,
        model: ModelType,
        strategy: BaseStrategy,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Run backtest and return daily equity curve."""
        self.reset()

        quotes = quotes.copy()
        quotes["trade_date"] = pd.to_datetime(quotes["trade_date"])
        features = features.copy()
        features["trade_date"] = pd.to_datetime(features["trade_date"])

        if start_date:
            quotes = quotes[quotes["trade_date"] >= pd.to_datetime(start_date)]
            features = features[features["trade_date"] >= pd.to_datetime(start_date)]
        if end_date:
            quotes = quotes[quotes["trade_date"] <= pd.to_datetime(end_date)]
            features = features[features["trade_date"] <= pd.to_datetime(end_date)]

        dates = sorted(quotes["trade_date"].unique())
        if len(dates) == 0:
            return pd.DataFrame()

        # Pre-build date index for O(1) lookup instead of filtering the full frame each day.
        self.quotes_by_date = {d: g for d, g in quotes.groupby("trade_date")}

        # Build index close series for regime detection (CSI300)
        index_quotes = quotes[quotes["symbol"] == "000300.SH"].sort_values("trade_date")
        index_close_map: dict[pd.Timestamp, float] = {}
        if not index_quotes.empty:
            index_close_map = dict(zip(index_quotes["trade_date"], index_quotes["close"]))

        # Add prediction scores if not already present (e.g. from rolling trainer)
        if "pred_score" not in features.columns:
            if model is None:
                raise ValueError("pred_score column is missing and no model was provided")
            feat_cols = [c for c in features.columns if c in model.feature_names]
            features["pred_score"] = model.predict(features[feat_cols])

        last_rebalance_idx: int | None = None
        pending_targets: set[str] | None = None
        pending_scores: dict[str, float] = {}

        # Pre-compute daily returns (wide form) for QP covariance estimation.
        if self.weighting == "qp" and self.optimizer is not None:
            px = quotes.pivot(index="trade_date", columns="symbol", values="close").sort_index()
            self._returns_cache = px.pct_change()

        for i, date in enumerate(dates):
            day_quotes = self.quotes_by_date[date]
            day_features = features[features["trade_date"] == date]

            # Track index close for regime filter
            if date in index_close_map:
                self._index_closes.append(index_close_map[date])

            # Execute the prior trading day's close signal at today's open.
            if pending_targets is not None:
                self._rebalance(
                    date, day_quotes, pending_targets, price_col="open",
                    scores=pending_scores,
                )
                pending_targets = None
                pending_scores = {}

            # Generate today's signal after today's data is known.
            if last_rebalance_idx is None or (i - last_rebalance_idx) >= self.rebalance_freq:
                if not day_features.empty:
                    # Market regime check: skip new entries in severe downtrend
                    if self._is_bear_regime():
                        last_rebalance_idx = i
                        self._record_value(date, day_quotes)
                        self.prev_day_quotes = day_quotes
                        continue

                    hold_symbols = set(self.positions.keys())
                    signals = strategy.generate_signals(
                        day_features,
                        current_date=date,
                        hold_symbols=list(hold_symbols),
                        industry_map=self.industry_map,
                    )
                    selected = signals[signals["selected"]]["symbol"].tolist()
                    pending_targets = set(selected)
                    # Capture scores for QP weighting.
                    score_col = "pred_score" if "pred_score" in signals.columns else "score"
                    pending_scores = dict(zip(signals["symbol"], signals[score_col]))
                    last_rebalance_idx = i

            # Mark to market at the close.
            self._record_value(date, day_quotes)
            self.prev_day_quotes = day_quotes

        return pd.DataFrame(self.daily_values)

    def _is_bear_regime(self) -> bool:
        """Check if market is in severe downtrend using MA20/MA60 of index."""
        if self.regime_ma_threshold <= 0 or len(self._index_closes) < 60:
            return False
        ma20 = sum(self._index_closes[-20:]) / 20
        ma60 = sum(self._index_closes[-60:]) / 60
        return (ma20 / ma60) < self.regime_ma_threshold

    def _rebalance(
        self,
        date: pd.Timestamp,
        day_quotes: pd.DataFrame,
        target_symbols: set,
        price_col: str = "close",
        scores: dict[str, float] | None = None,
    ) -> None:
        """Rebalance portfolio to target_symbols with equal or QP weights."""
        # First, sell positions not in target.
        for sym in list(self.positions.keys()):
            if sym not in target_symbols:
                self._sell_all(date, day_quotes, sym, price_col=price_col)

        # Determine targets that have execution price data today. New positions
        # that are already limit-up or suspended are excluded before cash is allocated.
        available_targets = []
        for sym in target_symbols:
            row = day_quotes[day_quotes["symbol"] == sym]
            if row.empty or price_col not in row.columns:
                continue
            price = float(row.iloc[0][price_col])
            if pd.isna(price) or price <= 0:
                continue
            # Suspension: volume==0 → cannot trade.
            if self._is_suspended(row):
                continue
            prev_close = self._prev_close(sym)
            current_pos = self.positions.get(sym)
            if (current_pos is None or current_pos.shares == 0) and prev_close and price >= prev_close * self._limit_up_ratio(sym, row):
                continue
            available_targets.append(sym)
        if not available_targets:
            return

        total_portfolio_value = self.cash + self._market_value(day_quotes)

        # Compute target weights.
        if self.weighting == "qp" and self.optimizer is not None and scores:
            weights = self._qp_weights(available_targets, scores, date)
        else:
            weights = {sym: 1.0 / len(available_targets) for sym in available_targets}

        for sym in available_targets:
            row = day_quotes[day_quotes["symbol"] == sym]
            price = float(row.iloc[0][price_col])
            target_value = total_portfolio_value * weights.get(sym, 0.0)
            # A-shares: lot size 100 shares
            target_shares = int(target_value / price / 100) * 100
            current_pos = self.positions.get(sym)
            current_shares = current_pos.shares if current_pos else 0

            if target_shares > current_shares:
                prev_close = self._prev_close(sym)
                if prev_close and price >= prev_close * self._limit_up_ratio(sym, row):
                    continue
                shares_to_buy = target_shares - current_shares
                self._buy(date, sym, shares_to_buy, price)
            elif target_shares < current_shares:
                shares_to_sell = current_shares - target_shares
                self._sell(date, sym, shares_to_sell, price, quote_row=row)

    def _qp_weights(
        self,
        symbols: list[str],
        scores: dict[str, float],
        date: pd.Timestamp,
    ) -> dict[str, float]:
        """Compute QP weights for the given symbols at the given date."""
        import pandas as pd
        score_series = pd.Series({s: scores.get(s, 0.0) for s in symbols})
        # Use returns up to `date` for covariance (no look-ahead).
        if self._returns_cache is not None:
            returns_df = self._returns_cache.loc[:date]
        else:
            returns_df = pd.DataFrame()
        # Previous weights from current positions.
        prev_w: dict[str, float] = {}
        total_mv = self._market_value(self.quotes_by_date.get(date, pd.DataFrame())) or 1.0
        for sym, pos in self.positions.items():
            price = self._last_known_price.get(sym, pos.cost_basis)
            prev_w[sym] = (pos.shares * price) / total_mv
        prev_series = pd.Series(prev_w)
        try:
            w = self.optimizer.optimize(
                score_series, returns_df,
                prev_weights=prev_series,
                industry_map=self.industry_map,
            )
            return {s: float(w.get(s, 0.0)) for s in symbols}
        except Exception as e:  # pragma: no cover - defensive
            # Fall back to equal weight if optimizer fails.
            return {s: 1.0 / len(symbols) for s in symbols}

    def _buy(self, date: pd.Timestamp, symbol: str, shares: int, price: float) -> None:
        if shares <= 0:
            return
        exec_price = price * (1 + self.slippage)
        amount = exec_price * shares
        commission = max(amount * self.commission_rate, self.min_commission)
        total_cost = amount + commission
        if total_cost > self.cash:
            return
        self.cash -= total_cost
        pos = self.positions.get(symbol)
        if pos is None:
            self.positions[symbol] = Position(symbol, shares, exec_price)
        else:
            new_shares = pos.shares + shares
            new_cost = (pos.shares * pos.cost_basis + shares * exec_price) / new_shares
            pos.shares = new_shares
            pos.cost_basis = new_cost
        self.trades.append(Trade(date, symbol, "BUY", shares, exec_price, amount))

    def _sell(
        self,
        date: pd.Timestamp,
        symbol: str,
        shares: int,
        price: float,
        force: bool = False,
        quote_row: pd.DataFrame | None = None,
    ) -> None:
        if shares <= 0:
            return
        pos = self.positions.get(symbol)
        if pos is None or pos.shares == 0:
            return
        shares = min(shares, pos.shares)

        # Skip sell if hits lower limit (cannot sell). ``force`` is kept for
        # explicit administrative exits, not regular strategy exits.
        if not force:
            prev_close = self._prev_close(symbol)
            if prev_close and price <= prev_close * self._limit_down_ratio(symbol, quote_row):
                return

        exec_price = price * (1 - self.slippage)
        amount = exec_price * shares
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_duty = amount * self.stamp_duty_rate
        self.cash += amount - commission - stamp_duty
        pos.shares -= shares
        if pos.shares == 0:
            del self.positions[symbol]
        self.trades.append(Trade(date, symbol, "SELL", shares, exec_price, amount))

    def _sell_all(
        self,
        date: pd.Timestamp,
        day_quotes: pd.DataFrame,
        symbol: str,
        price_col: str = "close",
    ) -> None:
        pos = self.positions.get(symbol)
        if pos is None or pos.shares == 0:
            return
        row = day_quotes[day_quotes["symbol"] == symbol]
        if row.empty or price_col not in row.columns:
            return
        price = float(row.iloc[0][price_col])
        if pd.isna(price) or price <= 0:
            return
        self._sell(date, symbol, pos.shares, price, force=True, quote_row=row)

    def _record_value(self, date: pd.Timestamp, day_quotes: pd.DataFrame) -> None:
        market_value = self._market_value(day_quotes)
        total_value = self.cash + market_value
        self.daily_values.append(
            {
                "trade_date": date,
                "cash": self.cash,
                "market_value": market_value,
                "total_value": total_value,
            }
        )

    def _market_value(self, day_quotes: pd.DataFrame) -> float:
        market_value = 0.0
        for sym, pos in self.positions.items():
            row = day_quotes[day_quotes["symbol"] == sym]
            if not row.empty:
                price = float(row.iloc[0]["close"])
                self._last_known_price[sym] = price
            else:
                price = self._last_known_price.get(sym, pos.cost_basis)
            market_value += pos.shares * price
        return market_value

    def _prev_close(self, symbol: str) -> float | None:
        """Return the previous trading day's close price for limit-up/down checks."""
        if self.prev_day_quotes is None:
            return None
        row = self.prev_day_quotes[self.prev_day_quotes["symbol"] == symbol]
        if row.empty:
            return None
        return float(row.iloc[0]["close"])

    @staticmethod
    def _is_suspended(quote_row: pd.DataFrame) -> bool:
        """Detect suspension from a single-symbol quote row.

        A suspended day typically has volume==0 and zero high-low range.
        We treat volume==0 (with a non-zero price) as suspended — AkShare
        returns 0 volume for halts while still echoing the last close.
        """
        if quote_row.empty:
            return False
        row = quote_row.iloc[0]
        vol = row.get("volume", None)
        if vol is not None and not pd.isna(vol) and float(vol) == 0:
            return True
        return False

    def _limit_up_ratio(self, symbol: str, quote_row: pd.DataFrame | None = None) -> float:
        """Return the A-share upper-limit multiplier for a symbol.

        ST precedence: explicit st_symbols set > name contains 'ST' > board code.
        ST  → +5%, STAR/ChiNext (300/301/688) → +20%, otherwise → +10%.
        """
        if symbol in self.st_symbols:
            return 1.05
        name = ""
        if quote_row is not None and not quote_row.empty and "name" in quote_row.columns:
            name = str(quote_row.iloc[0].get("name") or "")
        code = symbol.split(".")[0]
        if "ST" in name.upper():
            return 1.05
        if code.startswith(("300", "301", "688")):
            return 1.20
        return 1.10

    def _limit_down_ratio(self, symbol: str, quote_row: pd.DataFrame | None = None) -> float:
        """Return the A-share lower-limit multiplier for a symbol."""
        if symbol in self.st_symbols:
            return 0.95
        name = ""
        if quote_row is not None and not quote_row.empty and "name" in quote_row.columns:
            name = str(quote_row.iloc[0].get("name") or "")
        code = symbol.split(".")[0]
        if "ST" in name.upper():
            return 0.95
        if code.startswith(("300", "301", "688")):
            return 0.80
        return 0.90
