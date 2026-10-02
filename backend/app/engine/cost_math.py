"""Pure trading-cost formulas shared between paper trading (trading_service, against the real
DB portfolio) and the backtest engine (against a backtest's own simulated cash) -- so a backtest
pays exactly the slippage and charges a live paper trade would, and the two can never drift.

Two kinds of cost:
  * slippage: you rarely trade at the exact quoted price. A BUY fills a little above it and a
    SELL a little below, by `slippage_pct` -- the price you actually get.
  * charges: brokerage (a % of the trade value, optionally capped at a flat amount per order, the
    way discount brokers price) plus taxes and statutory levies (modelled as one % of the trade
    value -- an approximation, not an exact STT/GST/stamp-duty calculation).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CostConfig:
    enabled: bool = False
    slippage_pct: float = 0.0
    brokerage_pct: float = 0.0
    brokerage_cap: float = 0.0  # most brokerage charged on one order, in rupees; 0 = no cap
    other_charges_pct: float = 0.0


def fill_price(price: float, side: str, cost: CostConfig) -> float:
    """The price a market order actually fills at: slippage moves it against you."""
    if not cost.enabled or not cost.slippage_pct:
        return price
    move = cost.slippage_pct / 100
    return round(price * (1 + move if side == "BUY" else 1 - move), 2)


def charges(trade_value: float, cost: CostConfig) -> float:
    """Brokerage plus taxes/levies on one order of `trade_value` (the fill price x quantity)."""
    if not cost.enabled or trade_value <= 0:
        return 0.0
    brokerage = trade_value * cost.brokerage_pct / 100
    if cost.brokerage_cap:
        brokerage = min(brokerage, cost.brokerage_cap)
    return round(brokerage + trade_value * cost.other_charges_pct / 100, 2)
