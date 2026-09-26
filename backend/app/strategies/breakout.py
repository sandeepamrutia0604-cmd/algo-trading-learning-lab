"""Breakout: BUY on a new N-day high, SELL when price drops below the lowest close of the last M days."""

from ..engine.indicators import prev_max, prev_min
from .base import GREEN, RED, ChartSeries, ParamSpec, SignalEvent, StrategyDef, long_only_signals


def _generate(closes: list[float], p: dict) -> list[SignalEvent]:
    lookback, exit_lookback = p["lookback"], p["exit_lookback"]
    highs = prev_max(closes, lookback)
    lows = prev_min(closes, exit_lookback)

    def entry(i: int) -> SignalEvent | None:
        if highs[i] is not None and closes[i] > highs[i]:
            return SignalEvent(
                index=i,
                side="BUY",
                headline=f"Close {closes[i]:.2f} > {lookback}d high {highs[i]:.2f}",
                checks=[
                    f"Close ₹{closes[i]:.2f} is above the highest close of the previous {lookback} days (₹{highs[i]:.2f})",
                    "A new high suggests momentum, so this rule buys the breakout",
                ],
                values={"close": closes[i], "prior_high": highs[i]},
            )
        return None

    def exit_(i: int) -> SignalEvent | None:
        if lows[i] is not None and closes[i] < lows[i]:
            return SignalEvent(
                index=i,
                side="SELL",
                headline=f"Close {closes[i]:.2f} < {exit_lookback}d low {lows[i]:.2f}",
                checks=[
                    f"Close ₹{closes[i]:.2f} fell below the lowest close of the previous {exit_lookback} days (₹{lows[i]:.2f})",
                    "The breakout has faded, so this rule exits",
                ],
                values={"close": closes[i], "prior_low": lows[i]},
            )
        return None

    return long_only_signals(len(closes), entry, exit_)


def _series(closes: list[float], p: dict) -> list[ChartSeries]:
    return [
        ChartSeries(f"Highest close, previous {p['lookback']}d", "price", GREEN, prev_max(closes, p["lookback"]), dash="dot", width=1.4),
        ChartSeries(f"Lowest close, previous {p['exit_lookback']}d", "price", RED, prev_min(closes, p["exit_lookback"]), dash="dot", width=1.4),
    ]


def _validate(p: dict) -> None:
    if p["exit_lookback"] > p["lookback"]:
        raise ValueError("Exit lookback must not be longer than the entry lookback")


BREAKOUT = StrategyDef(
    key="breakout",
    label="Breakout",
    summary="Buys when price closes above its highest close of the last N days, and exits when it closes below the lowest close of the last M days.",
    works_best="Trending markets and big moves.",
    struggles="Choppy markets full of false breakouts that immediately reverse.",
    params=(
        ParamSpec("lookback", "Breakout days", 20, 2, 250),
        ParamSpec("exit_lookback", "Exit days", 10, 2, 250),
    ),
    entry_text="close is above the highest close of the previous {lookback} days",
    exit_text="close is below the lowest close of the previous {exit_lookback} days",
    generate=_generate,
    chart_series=_series,
    name_fn=lambda p: f"Breakout {p['lookback']}/{p['exit_lookback']}",
    validate=_validate,
)
