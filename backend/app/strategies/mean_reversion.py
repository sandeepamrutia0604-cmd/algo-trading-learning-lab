"""Mean reversion: BUY when price is unusually far below its average, SELL when it returns to the average."""

from ..engine.indicators import rolling_std, sma
from .base import GRAY, GREEN, ChartSeries, ParamSpec, SignalEvent, StrategyDef, long_only_signals


def _zscores(closes: list[float], middle: list, std: list) -> list:
    return [
        None if m is None or s is None or s == 0 else (c - m) / s
        for c, m, s in zip(closes, middle, std)
    ]


def _generate(closes: list[float], p: dict) -> list[SignalEvent]:
    period, entry_z = p["period"], p["entry_z"]
    middle = sma(closes, period)
    std = rolling_std(closes, period)
    z = _zscores(closes, middle, std)

    def entry(i: int) -> SignalEvent | None:
        if i > 0 and z[i] is not None and z[i - 1] is not None and z[i - 1] >= -entry_z > z[i]:
            return SignalEvent(
                index=i,
                side="BUY",
                headline=f"z-score {z[i]:.2f}",
                checks=[
                    f"Close ₹{closes[i]:.2f} is {abs(z[i]):.2f} standard deviations below its {period}-day average (₹{middle[i]:.2f}), past the -{entry_z:g} threshold",
                    f"The day before the z-score was {z[i - 1]:.2f} (not past the threshold)",
                    "Prices far below their average tend to drift back, so this rule buys",
                ],
                values={"z_score": round(z[i], 3), "prev_z_score": round(z[i - 1], 3), "average": round(middle[i], 4)},
            )
        return None

    def exit_(i: int) -> SignalEvent | None:
        if i > 0 and middle[i] is not None and middle[i - 1] is not None and closes[i - 1] < middle[i - 1] and closes[i] >= middle[i]:
            return SignalEvent(
                index=i,
                side="SELL",
                headline=f"Close {closes[i]:.2f} back at avg {middle[i]:.2f}",
                checks=[
                    f"Close ₹{closes[i]:.2f} moved back up to its {period}-day average (₹{middle[i]:.2f})",
                    f"The day before it was below the average (₹{closes[i - 1]:.2f} vs ₹{middle[i - 1]:.2f})",
                    "The price has reverted to its average, so this rule takes profit",
                ],
                values={"close": closes[i], "average": round(middle[i], 4)},
            )
        return None

    return long_only_signals(len(closes), entry, exit_)


def _series(closes: list[float], p: dict) -> list[ChartSeries]:
    middle = sma(closes, p["period"])
    std = rolling_std(closes, p["period"])
    entry_line = [None if m is None or s is None else m - p["entry_z"] * s for m, s in zip(middle, std)]
    return [
        ChartSeries(f"Average {p['period']}d", "price", GRAY, middle, width=1.4),
        ChartSeries(f"Entry line (-{p['entry_z']:g} std)", "price", GREEN, entry_line, dash="dash", width=1.4),
    ]


MEAN_REVERSION = StrategyDef(
    key="mean_reversion",
    label="Mean Reversion",
    summary="Bets that a price far below its recent average will come back to it: buys the dip, sells when the average is reached.",
    works_best="Sideways markets.",
    struggles="Falling markets, where a cheap price keeps getting cheaper (catching a falling knife).",
    params=(
        ParamSpec("period", "Average period", 20, 5, 100),
        ParamSpec("entry_z", "Entry z-score", 1.5, 0.5, 4.0, step=0.1, kind="float"),
    ),
    entry_text="the z-score of the close vs its {period}-day average drops below -{entry_z}",
    exit_text="the close returns to its {period}-day average",
    generate=_generate,
    chart_series=_series,
    name_fn=lambda p: f"Mean Reversion {p['period']} (z {p['entry_z']:g})",
)
