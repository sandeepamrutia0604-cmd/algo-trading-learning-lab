"""What a strategy says about a stock *right now*. Pure logic: no database, no I/O.

A backtest asks "what would this strategy have done over the whole history?". A scan asks the
question you ask each morning: "of all the stocks I follow, which ones is the strategy signalling
today, which are already in a trade, and which have nothing going on?". It reads the strategy's
own signal events (the same ones the chart, the auto-trader and the backtester use) for each stock
and keeps only what is true as of the stock's latest candle.

The strategies here are long-only and alternate BUY, SELL, BUY, SELL..., so the side of the *last*
signal says whether the strategy would be holding the stock at the moment: after a BUY it is in a
trade, after a SELL it is out.
"""

from dataclasses import dataclass

from ..strategies.base import SignalEvent


@dataclass(frozen=True)
class Reading:
    signal_today: SignalEvent | None  # a signal on the latest candle
    last_signal: SignalEvent | None  # the most recent signal ever (today's, if there is one)
    days_since: int | None  # trading days from the last signal to the latest candle (0 = today)
    state: str  # "in": last signal was a BUY; "out": it was a SELL; "none": no signal at all


def read(events: list[SignalEvent], candle_count: int) -> Reading:
    """The strategy's signals for a stock with `candle_count` candles, boiled down to today."""
    if candle_count < 1 or not events:
        return Reading(None, None, None, "none")
    last = max(events, key=lambda e: e.index)
    latest = candle_count - 1
    return Reading(
        signal_today=last if last.index == latest else None,
        last_signal=last,
        days_since=latest - last.index,
        state="in" if last.side == "BUY" else "out",
    )


def rank(reading: Reading) -> tuple[int, int]:
    """Sort key for a list of stocks: today's BUYs first, then today's SELLs, then stocks by how
    recently they signalled, then stocks with no signal at all."""
    if reading.signal_today is not None:
        return (0 if reading.signal_today.side == "BUY" else 1, 0)
    if reading.last_signal is not None:
        return (2, reading.days_since)
    return (3, 0)
