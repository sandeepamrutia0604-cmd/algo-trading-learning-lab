"""Stop-loss and take-profit exits for an open position. Pure logic: no database, no I/O.

A stop-loss sells if the price falls to a level you chose; a take-profit sells if it rises to
one. The lab's market moves one day at a time, so each exit is checked against that day's candle
(open, high, low) rather than a stream of ticks. That raises three questions a real exchange
answers on its own, so the rules are spelled out here:

  - Did the day reach the level? A stop is reached if the day's low touched it, a target if the
    day's high did.
  - What price do you get? Normally the level itself. But if the stock *opened* beyond the level
    (it gapped overnight, on news), the level was never available: the order fills at the open,
    which is worse than a stop for a gap down and better than a target for a gap up.
  - What if one day reached both? A daily candle doesn't say which came first, so the stop wins.
    That is the cautious choice: a backtest that assumes the target came first flatters itself.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExitFill:
    kind: str  # "stop" or "target"
    price: float  # what the position sells at, before any slippage
    level: float  # the stop or target that was set
    gapped: bool  # the day opened beyond the level, so the fill is the open, not the level


def check_levels(stop: float | None, target: float | None, price: float) -> str | None:
    """Why these levels can't be used with a position priced at `price`, or None when they can:
    a stop must sit below the price and a target above it, or the exit would fire at once."""
    if stop is not None and stop <= 0:
        return "The stop-loss price must be above zero."
    if target is not None and target <= 0:
        return "The take-profit price must be above zero."
    if stop is not None and stop >= price:
        return f"The stop-loss (₹{stop:,.2f}) must be below the current price (₹{price:,.2f}), or it would sell straight away."
    if target is not None and target <= price:
        return f"The take-profit (₹{target:,.2f}) must be above the current price (₹{price:,.2f}), or it would sell straight away."
    return None


def exit_fill(open_: float, high: float, low: float, stop: float | None, target: float | None) -> ExitFill | None:
    """Whether a day's candle triggers the stop or the target of a long position, and at what price."""
    if stop is not None and open_ <= stop:
        return ExitFill("stop", open_, stop, gapped=True)
    if target is not None and open_ >= target:
        return ExitFill("target", open_, target, gapped=True)
    if stop is not None and low <= stop:
        return ExitFill("stop", stop, stop, gapped=False)
    if target is not None and high >= target:
        return ExitFill("target", target, target, gapped=False)
    return None
