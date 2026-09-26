"""Combined: an MA crossover that only buys when RSI, price and volatility checks all agree."""

from ..engine.indicators import rsi, sma, volatility_pct
from .base import FAST_COLOR, GRAY, PURPLE, RED, SLOW_COLOR, ChartSeries, ParamSpec, SignalEvent, StrategyDef, long_only_signals
from .ma_crossover import crossover_checks, ma_crossover_signals


def _generate(closes: list[float], p: dict) -> list[SignalEvent]:
    fast, slow = p["fast"], p["slow"]
    rsi_period, rsi_max = p["rsi_period"], p["rsi_max"]
    vol_window, max_vol = p["vol_window"], p["max_vol"]

    crossovers = {s.index: s for s in ma_crossover_signals(closes, fast, slow)}
    fast_ma = sma(closes, fast)
    rsi_values = rsi(closes, rsi_period)
    vol = volatility_pct(closes, vol_window)

    def entry(i: int) -> SignalEvent | None:
        cross = crossovers.get(i)
        if cross is None or cross.side != "BUY":
            return None
        if rsi_values[i] is None or vol[i] is None:
            return None
        if not (rsi_values[i] <= rsi_max and closes[i] > fast_ma[i] and vol[i] <= max_vol):
            return None
        return SignalEvent(
            index=i,
            side="BUY",
            headline=f"Crossover + RSI {rsi_values[i]:.1f} + vol {vol[i]:.1f}%",
            checks=crossover_checks(cross, fast, slow)[:1]
            + [
                f"RSI({rsi_period}) = {rsi_values[i]:.1f}, at or below {rsi_max}: not overbought",
                f"Price ₹{closes[i]:.2f} is above the {fast}-day average (₹{fast_ma[i]:.2f})",
                f"Volatility {vol[i]:.2f}% per day is within the {max_vol:g}% limit",
            ],
            values={"fast_ma": round(cross.fast_ma, 4), "slow_ma": round(cross.slow_ma, 4), "rsi": round(rsi_values[i], 2), "volatility_pct": round(vol[i], 3)},
        )

    def exit_(i: int) -> SignalEvent | None:
        cross = crossovers.get(i)
        if cross is None or cross.side != "SELL":
            return None
        return SignalEvent(
            index=i,
            side="SELL",
            headline=f"{fast}d {cross.fast_ma:.2f} < {slow}d {cross.slow_ma:.2f}",
            checks=crossover_checks(cross, fast, slow)
            + ["Exits are never blocked by the entry filters: getting out matters more"],
            values={"fast_ma": round(cross.fast_ma, 4), "slow_ma": round(cross.slow_ma, 4)},
        )

    return long_only_signals(len(closes), entry, exit_)


def _series(closes: list[float], p: dict) -> list[ChartSeries]:
    n = len(closes)
    return [
        ChartSeries(f"SMA {p['fast']}", "price", FAST_COLOR, sma(closes, p["fast"])),
        ChartSeries(f"SMA {p['slow']}", "price", SLOW_COLOR, sma(closes, p["slow"])),
        ChartSeries(f"RSI {p['rsi_period']}", "osc", PURPLE, rsi(closes, p["rsi_period"]), y_range=(0, 100)),
        ChartSeries(f"RSI limit {p['rsi_max']}", "osc", RED, [p["rsi_max"]] * n, dash="dot", width=1.2),
    ]


def _validate(p: dict) -> None:
    if p["fast"] >= p["slow"]:
        raise ValueError("Fast period must be smaller than slow period")


COMBINED = StrategyDef(
    key="combined",
    label="Combined",
    summary="A trend-following crossover that only buys when three extra checks agree: RSI is not overbought, price is above the fast average, and daily volatility is within a limit.",
    works_best="Calm, steady uptrends.",
    struggles="Fast reversals, and it skips some good entries because the filters are strict.",
    params=(
        ParamSpec("fast", "Fast SMA", 20, 2, 499),
        ParamSpec("slow", "Slow SMA", 50, 3, 500),
        ParamSpec("rsi_period", "RSI period", 14, 2, 100),
        ParamSpec("rsi_max", "RSI at most", 70, 30, 100),
        ParamSpec("vol_window", "Volatility days", 20, 3, 100),
        ParamSpec("max_vol", "Max volatility %", 4.0, 0.5, 20.0, step=0.1, kind="float"),
    ),
    entry_text="SMA {fast}/{slow} crosses up AND RSI({rsi_period}) is at most {rsi_max} AND price is above the fast SMA AND volatility is at most {max_vol}% a day",
    exit_text="Fast SMA crosses below Slow SMA",
    generate=_generate,
    chart_series=_series,
    name_fn=lambda p: f"Combined {p['fast']}/{p['slow']} + RSI",
    validate=_validate,
)
