"""Lightweight event-driven backtest engine for A-shares."""

from dataclasses import dataclass

import pandas as pd

from ..models.base import BaseModel
from ..strategy.base import BaseStrategy


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
        initial_cash: float = 1_000_000.0,
        commission_rate: float = 0.0003,
        stamp_duty_rate: float = 0.001,  # A-share sell-side stamp duty
        min_commission: float = 5.0,
        slippage: float = 0.0,
        rebalance_freq: int = 5,
    ):
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.min_commission = min_commission
        self.slippage = slippage
        self.rebalance_freq = rebalance_freq

        self.cash: float = initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.daily_values: list[dict] = []

    def reset(self) -> None:
        self.cash = self.initial_cash
        self.positions = {}
        self.trades = []
        self.daily_values = []

    def run(
        self,
        quotes: pd.DataFrame,
        features: pd.DataFrame,
        model: BaseModel,
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

        # Add prediction scores if not already present (e.g. from rolling trainer)
        if "pred_score" not in features.columns:
            feat_cols = [c for c in features.columns if c in model.feature_names]
            features["pred_score"] = model.predict(features[feat_cols])

        last_rebalance = None
        target_symbols: set = set()

        for i, date in enumerate(dates):
            day_quotes = quotes[quotes["trade_date"] == date]
            day_features = features[features["trade_date"] == date]

            # Rebalance on first day and every rebalance_freq days
            if last_rebalance is None or (date - last_rebalance).days >= self.rebalance_freq:
                if not day_features.empty:
                    hold_symbols = set(self.positions.keys())
                    signals = strategy.generate_signals(
                        day_features,
                        current_date=date,
                        hold_symbols=list(hold_symbols),
                    )
                    selected = signals[signals["selected"]]["symbol"].tolist()
                    target_symbols = set(selected)
                    self._rebalance(date, day_quotes, target_symbols)
                    last_rebalance = date

            # Mark to market
            self._record_value(date, day_quotes)

        return pd.DataFrame(self.daily_values)

    def _rebalance(
        self,
        date: pd.Timestamp,
        day_quotes: pd.DataFrame,
        target_symbols: set,
    ) -> None:
        """Rebalance portfolio to target_symbols with equal weights."""
        # First, sell positions not in target
        for sym in list(self.positions.keys()):
            if sym not in target_symbols:
                self._sell_all(date, day_quotes, sym)

        if not target_symbols:
            return

        # Equal weight allocation
        target_value_per_stock = self.cash / len(target_symbols)
        for sym in target_symbols:
            row = day_quotes[day_quotes["symbol"] == sym]
            if row.empty:
                continue
            price = float(row.iloc[0]["close"])

            # Skip if hits upper limit (cannot buy)
            prev_close = self._prev_close(sym, day_quotes)
            if prev_close and price >= prev_close * 1.095:
                continue

            # A-shares: lot size 100 shares
            target_shares = int(target_value_per_stock / price / 100) * 100
            current_pos = self.positions.get(sym)
            current_shares = current_pos.shares if current_pos else 0

            if target_shares > current_shares:
                shares_to_buy = target_shares - current_shares
                self._buy(date, sym, shares_to_buy, price)
            elif target_shares < current_shares:
                shares_to_sell = current_shares - target_shares
                self._sell(date, sym, shares_to_sell, price)

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
    ) -> None:
        if shares <= 0:
            return
        pos = self.positions.get(symbol)
        if pos is None or pos.shares == 0:
            return
        shares = min(shares, pos.shares)

        # Skip sell if hits lower limit (cannot sell)
        if not force:
            prev_close = self._prev_close(symbol)
            if prev_close and price <= prev_close * 0.905:
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
    ) -> None:
        pos = self.positions.get(symbol)
        if pos is None or pos.shares == 0:
            return
        row = day_quotes[day_quotes["symbol"] == symbol]
        if row.empty:
            return
        price = float(row.iloc[0]["close"])
        self._sell(date, symbol, pos.shares, price)

    def _record_value(self, date: pd.Timestamp, day_quotes: pd.DataFrame) -> None:
        market_value = 0.0
        for sym, pos in self.positions.items():
            row = day_quotes[day_quotes["symbol"] == sym]
            if not row.empty:
                price = float(row.iloc[0]["close"])
                market_value += pos.shares * price
        total_value = self.cash + market_value
        self.daily_values.append(
            {
                "trade_date": date,
                "cash": self.cash,
                "market_value": market_value,
                "total_value": total_value,
            }
        )

    def _prev_close(self, symbol: str, day_quotes: pd.DataFrame | None = None) -> float | None:
        # Simplified: use cost basis as proxy; for accurate limit detection we'd need full history.
        pos = self.positions.get(symbol)
        if pos:
            return pos.cost_basis
        return None
