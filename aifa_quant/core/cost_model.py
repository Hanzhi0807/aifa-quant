"""Unified transaction cost model for backtest, paper trading and label construction.

All three layers (backtest engine, simulated broker, label cost adjustment) must
read from the same CostModel instance so that training targets and execution
realism stay consistent.  Previously the label hardcoded ``cost=0.0024`` while
the backtest defaulted to ``slippage=0.0`` — the two disagreed, so the model
was trained against a cost regime the simulator never enforced.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """A-share transaction cost parameters.

    Defaults reflect a realistic retail account:
      - commission 0.03% per side, minimum 5 CNY
      - stamp duty 0.1% sell-side only
      - slippage 0.1% (10 bps) per side as market-impact proxy

    The one-way total cost used by label construction is
    ``commission_rate + stamp_duty_rate + slippage``.  Round-trip is twice that
    minus the missing buy-side stamp duty.
    """

    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.001
    slippage: float = 0.001  # 10 bps per side

    def one_way_cost(self) -> float:
        """Total one-way cost (buy or sell) as a fraction of notional.

        Buy: commission + slippage (no stamp duty).
        Sell: commission + stamp duty + slippage.

        For label adjustment we use the buy-side cost as a conservative
        one-way estimate — labels are about "does this stock outperform
        after costs", so one-way is the right haircut.
        """
        return self.commission_rate + self.slippage

    def round_trip_cost(self) -> float:
        """Total round-trip cost (buy then sell) as a fraction of notional."""
        return (
            self.commission_rate * 2  # buy + sell commission
            + self.stamp_duty_rate  # sell-side stamp duty
            + self.slippage * 2  # both sides
        )

    def commission(self, amount: float) -> float:
        """Commission for a given notional, respecting the minimum."""
        return max(amount * self.commission_rate, self.min_commission)

    def stamp_duty(self, amount: float) -> float:
        """Sell-side stamp duty for a given notional."""
        return amount * self.stamp_duty_rate

    def buy_cost(self, amount: float) -> float:
        """Total cash out for a buy of ``amount`` notional (incl. commission + slippage)."""
        return amount + self.commission(amount)

    def sell_proceeds(self, amount: float) -> float:
        """Net cash in for a sell of ``amount`` notional (after commission + stamp duty + slippage)."""
        return amount - self.commission(amount) - self.stamp_duty(amount)


# Default singleton used across the codebase.
DEFAULT_COST_MODEL = CostModel()
