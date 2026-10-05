"""Pure risk-management formulas shared between live auto-trading (risk_service, which
resolves them against the real DB portfolio) and the backtest engine (which resolves them
against a backtest's own simulated capital) — so a backtest's position sizing and stop-loss
exactly match what live auto-trading would have done with the same settings."""

from . import indicators


def position_size(
    equity: float,
    price: float,
    max_risk_pct: float,
    stop_loss_pct: float,
    fallback_qty: int,
    max_allocation_pct: float = 0.0,
) -> int:
    """Risk-based share count: (equity * risk%) / (price * stop-loss%), the sizing formula
    from the plan's worked example. Falls back to `fallback_qty` (a fixed quantity) when the
    formula isn't fully configured.

    With `max_allocation_pct`, a risk-sized count is shrunk to fit that share of equity instead
    of being left to breach it: a 2% risk with a 5% stop sizes a position at 40% of equity, so
    without this the default 20% allocation cap would reject every such buy. The fixed fallback
    quantity is never shrunk -- it's the user's explicit choice, so the cap still blocks it."""
    if not max_risk_pct or not stop_loss_pct:
        return fallback_qty
    risk_amount = equity * max_risk_pct / 100
    risk_per_share = price * stop_loss_pct / 100
    if risk_per_share <= 0:
        return fallback_qty
    quantity = max(0, int(risk_amount // risk_per_share))
    if max_allocation_pct and price > 0:
        quantity = min(quantity, int((equity * max_allocation_pct / 100 + 1e-9) // price))
    return quantity


# How the stop distance is chosen. "fixed" is a set percentage below the entry. "volatility" is a
# multiple of the stock's recent daily volatility, so a calm stock gets a tight stop (and so a
# bigger position for the same risk) and a jumpy one a wide stop (and a smaller position): the
# money at risk per trade stays about the same either way.
STOP_MODES = ("fixed", "volatility")
MIN_STOP_PCT = 0.5  # a volatility stop is kept between these, whatever the stock has been doing
MAX_STOP_PCT = 30.0


def latest_volatility_pct(closes: list[float], window: int) -> float | None:
    """Standard deviation of the last `window` daily returns, in percent, as of the last close
    in `closes`; None until there are `window` + 1 closes. Same figure as indicators.volatility_pct
    at that day, so a live decision and a backtest of the same day agree."""
    if window < 2 or len(closes) < window + 1:
        return None
    return indicators.volatility_pct(closes[-(window + 1):], window)[-1]


def volatility_stop_pct(daily_volatility_pct: float | None, multiplier: float, fallback_pct: float) -> float:
    """The stop distance, in percent, for a stock whose daily volatility is `daily_volatility_pct`:
    `multiplier` times it, kept within MIN_STOP_PCT..MAX_STOP_PCT. With no usable volatility (too
    little history, or a price that has not moved) the fixed `fallback_pct` is used instead."""
    if daily_volatility_pct is None or daily_volatility_pct <= 0 or multiplier <= 0:
        return fallback_pct
    return min(MAX_STOP_PCT, max(MIN_STOP_PCT, multiplier * daily_volatility_pct))


def entry_stop_pct(closes: list[float], mode: str, window: int, multiplier: float, fixed_pct: float) -> float:
    """The stop distance, in percent, for a position opened on the last close in `closes`."""
    if mode == "volatility":
        return volatility_stop_pct(latest_volatility_pct(closes, window), multiplier, fixed_pct)
    return fixed_pct


def stop_loss_price(entry_price: float, stop_loss_pct: float) -> float:
    return entry_price * (1 - stop_loss_pct / 100)
