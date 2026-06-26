"""Paper trading engine: generate signals and execute via SimulatedBroker."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..config.settings import Settings
from ..core.trading_config import TradingConfig
from ..data.storage import DuckDBStore
from ..execution.broker import SimulatedBroker
from ..features import FeatureBuilder
from ..models.lgb_ranker import LGBRankerModel
from ..models.registry import ModelRegistry
from ..strategy import TopKDropoutStrategy


@dataclass
class PaperTradeResult:
    """Result of one paper trading run."""

    trade_date: pd.Timestamp
    signals: pd.DataFrame
    orders: list[dict[str, Any]]
    cash: float
    market_value: float
    total_value: float
    positions: dict[str, int]


class PaperTradingEngine:
    """Run a single-day paper trading cycle using cached market data."""

    def __init__(
        self,
        settings: Settings | None = None,
        config: TradingConfig | None = None,
        model_name: str = "lgb_stock_selector",
        top_k: int = 5,
        rebalance_freq: int = 5,
        initial_cash: float = 1_000_000.0,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        stamp_duty_rate: float = 0.001,
        slippage: float = 0.0,
        include_fundamental: bool = True,
        include_macro: bool = True,
        include_sentiment: bool = False,
        corr_threshold: float | None = 0.95,
    ):
        self.settings = settings or Settings()
        self.store = DuckDBStore(self.settings)
        self.model_name = model_name
        self.top_k = top_k
        self.rebalance_freq = rebalance_freq
        self.include_fundamental = include_fundamental
        self.include_macro = include_macro
        self.include_sentiment = include_sentiment
        self.corr_threshold = corr_threshold

        if config is None:
            config = TradingConfig(
                initial_cash=initial_cash,
                commission_rate=commission_rate,
                min_commission=min_commission,
                stamp_duty_rate=stamp_duty_rate,
                slippage=slippage,
                rebalance_freq=rebalance_freq,
                top_k=top_k,
            )
        self.config = config
        self.initial_cash = config.initial_cash
        self.commission_rate = config.commission_rate
        self.min_commission = config.min_commission
        self.stamp_duty_rate = config.stamp_duty_rate
        self.slippage = config.slippage

    def run(
        self,
        trade_date: str | pd.Timestamp | None = None,
        dry_run: bool = False,
    ) -> PaperTradeResult:
        """Run one paper trading cycle.

        Args:
            trade_date: Date to trade. Defaults to the latest cached trade date.
            dry_run: If True, compute signals and planned trades but do not persist.
        """
        trade_date = self._resolve_trade_date(trade_date)
        trade_date_str = trade_date.strftime("%Y%m%d")

        # Load model
        registry = ModelRegistry(self.settings)
        model_path = registry.path(self.model_name)
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        model = LGBRankerModel()
        model.load(str(model_path))

        # Build features for prediction (no future labels)
        builder = FeatureBuilder(self.settings)
        lookback_start = (trade_date - pd.Timedelta(days=180)).strftime("%Y%m%d")
        features = builder.build_features(
            start_date=lookback_start,
            end_date=trade_date_str,
            include_fundamental=self.include_fundamental,
            include_macro=self.include_macro,
            include_sentiment=self.include_sentiment,
            corr_threshold=self.corr_threshold,
            cache_only=True,
            prediction_mode=True,
        )
        if features.empty:
            raise RuntimeError("No features available for the selected date")

        feature_cols = builder.feature_columns(features)
        # Ensure model features exist
        missing_features = [c for c in model.feature_names if c not in feature_cols]
        if missing_features:
            raise RuntimeError(f"Model expects missing features: {missing_features}")

        day_features = features[features["trade_date"] == trade_date].copy()
        if day_features.empty:
            raise RuntimeError(f"No feature data for {trade_date.date()}")

        day_features = day_features.dropna(subset=feature_cols)
        day_features["pred_score"] = model.predict(day_features[feature_cols])

        # Load current broker state
        broker = SimulatedBroker(config=self.config, store=self.store)
        broker.connect()

        # Generate signals
        strategy = TopKDropoutStrategy(top_k=self.top_k, rebalance_freq=self.rebalance_freq)
        current_positions = broker.query_positions()
        signals = strategy.generate_signals(
            day_features,
            current_date=trade_date,
            hold_symbols=list(current_positions.keys()),
        )
        selected_symbols = signals[signals["selected"]]["symbol"].tolist()

        # Load market data for the target universe
        universe_symbols = features["symbol"].unique().tolist()
        quotes = self.store.load_daily_quotes(
            universe_symbols,
            start_date=(trade_date - pd.Timedelta(days=10)).strftime("%Y%m%d"),
            end_date=trade_date_str,
        )
        if quotes.empty:
            raise RuntimeError("No cached daily quotes available for execution")
        quotes["trade_date"] = pd.to_datetime(quotes["trade_date"])

        day_quotes = quotes[quotes["trade_date"] == trade_date]
        prev_quotes = quotes[quotes["trade_date"] < trade_date]
        prev_close_map = (
            prev_quotes.groupby("symbol")["close"].last().to_dict() if not prev_quotes.empty else {}
        )

        broker.set_quotes(trade_date, day_quotes, prev_close_map)

        # Compute planned trades
        planned_orders = self._plan_rebalance(
            broker=broker,
            selected_symbols=selected_symbols,
            day_quotes=day_quotes,
        )

        if dry_run:
            total_value = broker.query_cash() + broker._market_value(day_quotes)
            return PaperTradeResult(
                trade_date=trade_date,
                signals=signals,
                orders=planned_orders,
                cash=broker.query_cash(),
                market_value=total_value - broker.query_cash(),
                total_value=total_value,
                positions=current_positions,
            )

        # Execute trades
        for order in planned_orders:
            broker.submit_order(
                symbol=order["symbol"],
                side=order["side"],
                quantity=order["quantity"],
                order_type=order["order_type"],
                price=order.get("price"),
            )

        # Record end-of-day NAV
        market_value = broker._market_value(day_quotes)
        total_value = broker.query_cash() + market_value
        broker._save_state()

        return PaperTradeResult(
            trade_date=trade_date,
            signals=signals,
            orders=broker.query_orders(),
            cash=broker.query_cash(),
            market_value=market_value,
            total_value=total_value,
            positions=broker.query_positions(),
        )

    def _resolve_trade_date(self, trade_date: str | pd.Timestamp | None) -> pd.Timestamp:
        if trade_date is None:
            latest = self.store.get_latest_trade_date()
            if latest is None:
                raise RuntimeError("No cached daily quotes; cannot determine trade date")
            return latest
        return pd.to_datetime(trade_date)

    def _plan_rebalance(
        self,
        broker: SimulatedBroker,
        selected_symbols: list[str],
        day_quotes: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """Return planned orders to move current positions to equal-weight targets."""
        current_positions = broker.query_positions()
        cash = broker.query_cash()

        # Mark-to-market current portfolio
        market_value = broker._market_value(day_quotes)
        total_value = cash + market_value

        orders: list[dict[str, Any]] = []

        # Sell positions not in target
        for sym, shares in list(current_positions.items()):
            if sym not in set(selected_symbols):
                orders.append(
                    {
                        "symbol": sym,
                        "side": "sell",
                        "quantity": shares,
                        "order_type": "market",
                        "price": None,
                    }
                )

        if not selected_symbols:
            return orders

        target_value_per_stock = total_value / len(selected_symbols)

        for sym in selected_symbols:
            row = day_quotes[day_quotes["symbol"] == sym]
            if row.empty:
                continue
            price = float(row.iloc[0]["close"])
            target_shares = int(target_value_per_stock / price / 100) * 100
            current_shares = current_positions.get(sym, 0)

            if target_shares > current_shares:
                orders.append(
                    {
                        "symbol": sym,
                        "side": "buy",
                        "quantity": target_shares - current_shares,
                        "order_type": "market",
                        "price": None,
                    }
                )
            elif target_shares < current_shares:
                orders.append(
                    {
                        "symbol": sym,
                        "side": "sell",
                        "quantity": current_shares - target_shares,
                        "order_type": "market",
                        "price": None,
                    }
                )

        return orders

    def reset(self, cash: float | None = None) -> None:
        """Reset paper trading state to cash only."""
        reset_config = TradingConfig(
            initial_cash=cash if cash is not None else self.initial_cash,
            commission_rate=self.commission_rate,
            min_commission=self.min_commission,
            stamp_duty_rate=self.stamp_duty_rate,
            slippage=self.slippage,
        )
        broker = SimulatedBroker(config=reset_config, store=self.store)
        broker.connect()
        broker.reset_state()
