"""Price alerts. Pure logic: no database, no I/O.

An alert says "tell me when this stock trades above (or below) this price". It never trades; it
only notices. The lab's market moves one day at a time, so an alert is checked against that day's
candle, with the same rules as the stop-loss and take-profit exits (engine/exit_math.py):

  - Did the day reach the level? An "above" alert is reached if the day's high touched it, a
    "below" alert if the day's low did.
  - What price was seen? Normally the level itself. If the stock *opened* beyond the level (it
    gapped overnight), the level never traded: the alert reports the open instead.
"""

from dataclasses import dataclass

KINDS = ("above", "below")


@dataclass(frozen=True)
class AlertHit:
    price: float  # the price the alert reports: the level, or the open after a gap
    gapped: bool  # the day opened beyond the level


def check_level(kind: str, level: float, price: float) -> str | None:
    """Why an alert can't be set at `level` while the stock is at `price`, or None when it can: an
    "above" level must sit over the price and a "below" level under it, or it would fire at once."""
    if kind not in KINDS:
        return "An alert is either 'above' or 'below' a price."
    if level <= 0:
        return "The alert price must be above zero."
    if kind == "above" and level <= price:
        return f"An 'above' alert (₹{level:,.2f}) must be over the current price (₹{price:,.2f}), or it would fire straight away."
    if kind == "below" and level >= price:
        return f"A 'below' alert (₹{level:,.2f}) must be under the current price (₹{price:,.2f}), or it would fire straight away."
    return None


def alert_hit(kind: str, level: float, open_: float, high: float, low: float) -> AlertHit | None:
    """Whether a day's candle reaches the alert's level, and at what price."""
    if kind == "above":
        if open_ >= level:
            return AlertHit(open_, gapped=True)
        if high >= level:
            return AlertHit(level, gapped=False)
    elif kind == "below":
        if open_ <= level:
            return AlertHit(open_, gapped=True)
        if low <= level:
            return AlertHit(level, gapped=False)
    return None
