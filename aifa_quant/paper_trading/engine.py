"""Paper trading engine: generate signals and execute via SimulatedBroker.

Integrates ATR stop-loss, volatility position sizing, and market oscillation filter
from the risk module.
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..config.settings import Settings
from ..core.trading_config import TradingConfig
from ..data.storage import DuckDBStore
from ..execution.broker import SimulatedBroker
from ..features import FeatureBuilder
from ..models.lgb_ranker import LGBRankerModel
from ..models.registry import ModelRegistry
from ..risk import ATRStopManager, VolatilityPositionSizer, detect_oscillation
from ..strategy import TopKDropoutStrategy
from ..strategy.profiles import apply_profile_score, get_profile


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
    stop_signals: list = field(default_factory=list)
    market_choppy: bool = False


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
        use_atr_stops: bool = True,
        use_vol_sizing: bool = True,
        use_market_filter: bool = True,
        profile: str = "balanced",
        weighting: str = "vol",  # "vol" | "qp" | "equal"
    ):
        self.settings = settings or Settings()
        self.store = DuckDBStore(self.settings)
        self.model_name = model_name

        # Load profile configuration
        self.profile_id = profile
        pf = get_profile(profile)
        if pf:
            self.top_k = pf.top_k
            self.risk_config = {
                "stop_loss_atr": pf.atr_stop_loss,
                "stop_win_atr": pf.atr_take_profit,
                "crash_atr": pf.atr_crash,
                "drawdown_atr": pf.atr_drawdown,
            }
            self.vol_config = {"target_risk_pct": pf.target_risk_pct}
        else:
            self.top_k = top_k
            self.risk_config = {}
            self.vol_config = {}

        self.rebalance_freq = rebalance_freq
        self.include_fundamental = include_fundamental
        self.include_macro = include_macro
        self.include_sentiment = include_sentiment
        self.corr_threshold = corr_threshold
        self.use_atr_stops = use_atr_stops
        self.use_vol_sizing = use_vol_sizing
        self.use_market_filter = use_market_filter
        self.weighting = weighting

        if config is None:
            config = TradingConfig(
                initial_cash=initial_cash,
                commission_rate=commission_rate,
                min_commission=min_commission,
                stamp_duty_rate=stamp_duty_rate,
                slippage=slippage,
                rebalance_freq=rebalance_freq,
                top_k=self.top_k,
            )
        self.config = config
        self.initial_cash = config.initial_cash
        self.commission_rate = config.commission_rate
        self.min_commission = config.min_commission
        self.stamp_duty_rate = config.stamp_duty_rate
        self.slippage = config.slippage

        # Risk module instances with profile-specific params
        self.atr_stop_mgr = ATRStopManager(**self.risk_config) if self.risk_config else ATRStopManager()
        self.position_sizer = (
            VolatilityPositionSizer(**self.vol_config) if self.vol_config else VolatilityPositionSizer()
        )

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
        day_features = apply_profile_score(day_features, self.profile_id, feature_cols)

        # Load current broker state (with ST symbols for limit ratios)
        st_symbols: set[str] = set()
        try:
            universe = self.store.load_stock_universe()
            if "is_st" in universe.columns:
                st_symbols = set(universe.loc[universe["is_st"].astype(bool), "symbol"].tolist())
        except Exception:
            pass
        self._last_st_symbols = st_symbols  # cache for reset()
        broker = SimulatedBroker(
            config=self.config, store=self.store, profile=self.profile_id, st_symbols=st_symbols
        )
        broker.connect()

        # Load industry map for concentration control
        industry_map: dict[str, str] | None = None
        try:
            universe = self.store.conn.execute(
                "SELECT symbol, industry FROM stock_universe WHERE industry IS NOT NULL"
            ).fetchdf()
            if not universe.empty:
                industry_map = dict(zip(universe["symbol"], universe["industry"]))
        except Exception:
            pass

        # Determine max_industry_pct from profile
        max_industry_pct = 0.30
        from ..strategy.profiles import get_profile as _get_profile
        pf = _get_profile(self.profile_id)
        if pf:
            max_industry_pct = pf.max_industry_pct

        # Generate signals
        strategy = TopKDropoutStrategy(
            top_k=self.top_k, rebalance_freq=self.rebalance_freq,
            max_industry_pct=max_industry_pct,
        )
        current_positions = broker.query_positions()
        signals = strategy.generate_signals(
            day_features,
            current_date=trade_date,
            hold_symbols=list(current_positions.keys()),
            industry_map=industry_map,
        )
        selected_symbols = signals[signals["selected"]]["symbol"].tolist()

        # Load market data for the target universe
        universe_symbols = features["symbol"].unique().tolist()
        quotes = self.store.load_daily_quotes(
            universe_symbols,
            start_date=(trade_date - pd.Timedelta(days=120)).strftime("%Y%m%d"),
            end_date=trade_date_str,
        )
        if quotes.empty:
            raise RuntimeError("No cached daily quotes available for execution")
        quotes["trade_date"] = pd.to_datetime(quotes["trade_date"])

        day_quotes = quotes[quotes["trade_date"] == trade_date]
        prev_quotes = quotes[quotes["trade_date"] < trade_date]
        prev_close_map = prev_quotes.groupby("symbol")["close"].last().to_dict() if not prev_quotes.empty else {}

        broker.set_quotes(trade_date, day_quotes, prev_close_map)

        # ---- T+1 execution: fill pending orders from the previous day at today's open ----
        # Paper trading runs once per day after close. Signals generated on T must
        # execute on T+1's open to match what is achievable in live trading.
        # Pending orders persist in paper_pending_orders and are filled here first.
        filled_today = self._fill_pending_orders(broker, day_quotes)

        # Market oscillation check — skip new buys in choppy markets
        market_choppy = False
        if self.use_market_filter:
            benchmark_quotes = self.store.load_daily_quotes(
                ["000300.SH"],
                start_date=(trade_date - pd.Timedelta(days=60)).strftime("%Y%m%d"),
                end_date=trade_date_str,
            )
            if not benchmark_quotes.empty:
                benchmark_close = benchmark_quotes.set_index("trade_date")["close"]
                market_choppy, _ = detect_oscillation(benchmark_close, verbose=True)

        # Apply ATR stops to current positions (pass full quote history).
        # Stops generate signals today; they become pending orders filled tomorrow.
        stop_signals = []
        if self.use_atr_stops:
            stop_signals = self._apply_stops(broker, quotes, prev_close_map)

        # Compute planned trades (skip new buys if market is choppy).
        # These are also staged as pending for next-day open execution.
        score_map = dict(zip(day_features["symbol"], day_features["pred_score"])) if "pred_score" in day_features.columns else None
        planned_orders = self._plan_rebalance(
            broker=broker,
            selected_symbols=selected_symbols,
            quotes=quotes,
            market_choppy=market_choppy,
            scores=score_map,
            industry_map=industry_map,
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
                stop_signals=stop_signals,
                market_choppy=market_choppy,
            )

        # Stage today's stop + rebalance orders as pending for T+1 open fill.
        new_pending = self._stop_signals_to_orders(stop_signals, broker, day_quotes) + planned_orders
        self._save_pending_orders(new_pending, trade_date)

        # Record end-of-day NAV (mark-to-market at today's close).
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
            stop_signals=stop_signals,
            market_choppy=market_choppy,
        )

    def _fill_pending_orders(self, broker: SimulatedBroker, day_quotes: pd.DataFrame) -> list[dict]:
        """Fill previously-pending orders at today's open price. Returns filled order records."""
        pending_df = self.store.load_paper_pending_orders(self.profile_id)
        if pending_df.empty:
            return []
        filled: list[dict] = []
        for _, row in pending_df.iterrows():
            symbol = str(row["symbol"])
            order_row = day_quotes[day_quotes["symbol"] == symbol]
            if order_row.empty or "open" not in order_row.columns:
                # Stock has no quote today (still suspended or delisted). Keep pending.
                continue
            open_price = float(order_row.iloc[0]["open"])
            if pd.isna(open_price) or open_price <= 0:
                continue
            result = broker.submit_order(
                symbol=symbol,
                side=str(row["side"]),
                quantity=int(row["quantity"]),
                order_type=str(row["order_type"]),
                price=open_price,
            )
            if result.get("status") == "filled":
                self.store.delete_paper_pending_order(str(row["pending_id"]), self.profile_id)
                filled.append(result)
            elif result.get("status", "").startswith("rejected"):
                # Rejected (limit-up / suspended / no cash). Drop the pending; it
                # would never fill and would block future rebalances.
                self.store.delete_paper_pending_order(str(row["pending_id"]), self.profile_id)
        return filled

    def _save_pending_orders(self, orders: list[dict], signal_date: pd.Timestamp) -> None:
        """Persist today's planned orders as pending for T+1 execution."""
        if not orders:
            return
        import uuid
        rows = []
        for o in orders:
            rows.append({
                "pending_id": f"pend_{uuid.uuid4().hex[:12]}",
                "signal_date": signal_date,
                "symbol": o["symbol"],
                "side": o["side"],
                "quantity": int(o["quantity"]),
                "order_type": o.get("order_type", "market"),
                "reason": o.get("reason", "rebalance"),
            })
        self.store.save_paper_pending_orders(pd.DataFrame(rows), self.profile_id)

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
        quotes: pd.DataFrame,
        market_choppy: bool = False,
        scores: dict[str, float] | None = None,
        industry_map: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return planned orders using volatility / QP / equal weighting.

        In choppy markets, only sell (no new buys).
        """
        current_positions = broker.query_positions()
        cash = broker.query_cash()
        trade_date = quotes["trade_date"].max()
        day_quotes = quotes[quotes["trade_date"] == trade_date]
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

        # In choppy markets, skip new buys
        if market_choppy:
            # Still sell non-target positions, but don't buy new ones
            return orders

        # Compute target shares per weighting mode.
        target_shares: dict[str, int] = {}
        if self.weighting == "qp" and scores:
            target_shares = self._qp_target_shares(
                selected_symbols, scores, quotes, total_value, current_positions, industry_map
            )
        elif self.use_vol_sizing:
            target_shares = self.position_sizer.size_positions(
                total_value=total_value,
                selected_symbols=selected_symbols,
                quotes=quotes,
                cash=cash,
            )
        else:
            # Equal-weight fallback
            target_value_per_stock = total_value / len(selected_symbols)
            for sym in selected_symbols:
                row = day_quotes[day_quotes["symbol"] == sym]
                if not row.empty:
                    price = float(row.iloc[0]["close"])
                    target_shares[sym] = int(target_value_per_stock / price / 100) * 100

        for sym in selected_symbols:
            target = target_shares.get(sym, 0)
            current = current_positions.get(sym, 0)
            if target > current:
                orders.append(
                    {
                        "symbol": sym,
                        "side": "buy",
                        "quantity": target - current,
                        "order_type": "market",
                        "price": None,
                    }
                )
            elif target < current:
                orders.append(
                    {
                        "symbol": sym,
                        "side": "sell",
                        "quantity": current - target,
                        "order_type": "market",
                        "price": None,
                    }
                )

        return orders

    def _qp_target_shares(
        self,
        selected_symbols: list[str],
        scores: dict[str, float],
        quotes: pd.DataFrame,
        total_value: float,
        current_positions: dict[str, int],
        industry_map: dict[str, str] | None,
    ) -> dict[str, int]:
        """Compute target shares via the mean-variance optimizer."""
        from ..strategy.optimizer import MeanVarianceOptimizer, OptimizerConfig

        if not hasattr(self, "_optimizer"):
            self._optimizer = MeanVarianceOptimizer(OptimizerConfig())
        score_series = pd.Series({s: scores.get(s, 0.0) for s in selected_symbols})
        # Build wide returns from quotes (pivot on close).
        px = quotes.pivot(index="trade_date", columns="symbol", values="close").sort_index()
        returns_df = px.pct_change()
        # Previous weights from current positions.
        prev_w: dict[str, float] = {}
        last_date = quotes["trade_date"].max()
        day_quotes = quotes[quotes["trade_date"] == last_date]
        mv_total = float(broker._market_value(day_quotes)) or 1.0
        for sym, shares in current_positions.items():
            row = day_quotes[day_quotes["symbol"] == sym]
            if not row.empty:
                prev_w[sym] = (shares * float(row.iloc[0]["close"])) / mv_total
        try:
            w = self._optimizer.optimize(
                score_series, returns_df,
                prev_weights=pd.Series(prev_w),
                industry_map=industry_map,
            )
        except Exception:
            # Fall back to equal weight.
            w = pd.Series({s: 1.0 / len(selected_symbols) for s in selected_symbols})

        target_shares: dict[str, int] = {}
        for sym in selected_symbols:
            row = day_quotes[day_quotes["symbol"] == sym]
            if row.empty:
                continue
            price = float(row.iloc[0]["close"])
            target_value = total_value * float(w.get(sym, 0.0))
            target_shares[sym] = int(target_value / price / 100) * 100
        return target_shares

    def _apply_stops(
        self,
        broker: SimulatedBroker,
        quotes: pd.DataFrame,
        prev_close_map: dict[str, float] | None,
    ) -> list:
        """Check ATR stop signals for all current positions."""
        positions = broker.query_positions()
        cost_basis_map = broker.query_cost_basis()

        all_signals = []
        for sym, shares in positions.items():
            sym_quotes = quotes[quotes["symbol"] == sym].sort_values("trade_date")
            if sym_quotes.empty or shares <= 0:
                continue

            prev_close = (prev_close_map or {}).get(sym)
            signals = self.atr_stop_mgr.check_all(
                symbol=sym,
                position_shares=shares,
                cost_basis=cost_basis_map.get(sym, 0),
                daily_quotes=sym_quotes,
                prev_close=prev_close,
            )
            all_signals.extend(signals)

        return all_signals

    @staticmethod
    def _stop_signals_to_orders(
        stop_signals: list,
        broker: SimulatedBroker,
        day_quotes: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """Convert StopSignal objects to broker orders."""
        orders = []
        for sig in stop_signals:
            shares = broker.query_positions().get(sig.symbol, 0)
            if shares <= 0:
                continue
            orders.append(
                {
                    "symbol": sig.symbol,
                    "side": "sell",
                    "quantity": shares,
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
        broker = SimulatedBroker(
            config=reset_config, store=self.store, profile=self.profile_id,
            st_symbols=getattr(self, "_last_st_symbols", set()),
        )
        broker.connect()
        broker.reset_state()
