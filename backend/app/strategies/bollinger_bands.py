"""Bollinger Bands: BUY when price drops below the lower band, SELL when it rises above the upper band."""

from ..engine.indicators import bollinger
from .base import GRAY, GREEN, RED, ChartSeries, ParamSpec, SignalEvent, StrategyDef, long_only_signals


def _generate(closes: list[float], p: dict) -> list[SignalEvent]:
    period, k = p["period"], p["num_std"]
    middle, upper, lower = bollinger(closes, period, k)

    def entry(i: int) -> SignalEvent | None:
        if i > 0 and lower[i] is not None and lower[i - 1] is not None and closes[i - 1] >= lower[i - 1] and closes[i] < lower[i]:
            return SignalEvent(
                index=i,
                side="BUY",
                headline=f"Close {closes[i]:.2f} < lower {lower[i]:.2f}",
                checks=[
                    f"Close ₹{closes[i]:.2f} fell below the lower band ₹{lower[i]:.2f} (middle ₹{middle[i]:.2f}, {k:g} standard deviations)",
                    f"The day before it was ₹{closes[i - 1]:.2f}, at or above the lower band (₹{lower[i - 1]:.2f})",
                    "Price is unusually low compared with its recent average, so this rule bets on a rebound",
                ],
                values={"close": closes[i], "lower": round(lower[i], 4), "middle": round(middle[i], 4), "upper": round(upper[i], 4)},
            )
        return None

    def exit_(i: int) -> SignalEvent | None:
        if i > 0 and upper[i] is not None and upper[i - 1] is not None and closes[i - 1] <= upper[i - 1] and closes[i] > upper[i]:
            return SignalEvent(
                index=i,
                side="SELL",
                headline=f"Close {closes[i]:.2f} > upper {upper[i]:.2f}",
                checks=[
                    f"Close ₹{closes[i]:.2f} rose above the upper band ₹{upper[i]:.2f} (middle ₹{middle[i]:.2f}, {k:g} standard deviations)",
                    f"The day before it was ₹{closes[i - 1]:.2f}, at or below the upper band (₹{upper[i - 1]:.2f})",
                    "Price is unusually high compared with its recent average, so this rule takes profit",
                ],
                values={"close": closes[i], "lower": round(lower[i], 4), "middle": round(middle[i], 4), "upper": round(upper[i], 4)},
            )
        return None

    return long_only_signals(len(closes), entry, exit_)


def _series(closes: list[float], p: dict) -> list[ChartSeries]:
    middle, upper, lower = bollinger(closes, p["period"], p["num_std"])
    return [
        ChartSeries("Lower band", "price", GREEN, lower, dash="dash", width=1.4),
        ChartSeries("Upper band", "price", RED, upper, dash="dash", width=1.4, fill_to_previous=True),
        ChartSeries(f"Middle SMA {p['period']}", "price", GRAY, middle, width=1.4),
    ]


BOLLINGER_BANDS = StrategyDef(
    key="bollinger",
    label="Bollinger Bands",
    summary="Draws bands a few standard deviations around a moving average. Buys when price dips below the lower band, sells when it rises above the upper band.",
    works_best="Sideways markets with regular swings.",
    struggles="Strong trends, where price can ride along one band for weeks.",
    params=(
        ParamSpec("period", "Band period", 20, 5, 100),
        ParamSpec("num_std", "Std deviations", 2.0, 0.5, 4.0, step=0.1, kind="float"),
    ),
    entry_text="close falls below the lower band ({period}-day, {num_std} std dev)",
    exit_text="close rises above the upper band",
    generate=_generate,
    chart_series=_series,
    name_fn=lambda p: f"Bollinger {p['period']}/{p['num_std']:g}",
)
