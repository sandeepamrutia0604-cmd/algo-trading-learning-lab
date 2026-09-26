"""RSI: BUY when RSI falls below the oversold line, SELL when it rises above the overbought line."""

from ..engine.indicators import rsi
from .base import GREEN, PURPLE, RED, ChartSeries, ParamSpec, SignalEvent, StrategyDef, long_only_signals


def _generate(closes: list[float], p: dict) -> list[SignalEvent]:
    period, oversold, overbought = p["period"], p["oversold"], p["overbought"]
    values = rsi(closes, period)

    def entry(i: int) -> SignalEvent | None:
        if i > 0 and values[i] is not None and values[i - 1] is not None and values[i - 1] >= oversold > values[i]:
            return SignalEvent(
                index=i,
                side="BUY",
                headline=f"RSI {values[i]:.1f}",
                checks=[
                    f"RSI({period}) fell to {values[i]:.1f}, below the oversold line of {oversold}",
                    f"The day before it was {values[i - 1]:.1f} (at or above {oversold})",
                    "Oversold means the price fell quickly, so this rule bets on a bounce",
                ],
                values={"rsi": round(values[i], 2), "prev_rsi": round(values[i - 1], 2)},
            )
        return None

    def exit_(i: int) -> SignalEvent | None:
        if i > 0 and values[i] is not None and values[i - 1] is not None and values[i - 1] <= overbought < values[i]:
            return SignalEvent(
                index=i,
                side="SELL",
                headline=f"RSI {values[i]:.1f}",
                checks=[
                    f"RSI({period}) rose to {values[i]:.1f}, above the overbought line of {overbought}",
                    f"The day before it was {values[i - 1]:.1f} (at or below {overbought})",
                    "Overbought means the price rose quickly, so this rule takes profit",
                ],
                values={"rsi": round(values[i], 2), "prev_rsi": round(values[i - 1], 2)},
            )
        return None

    return long_only_signals(len(closes), entry, exit_)


def _series(closes: list[float], p: dict) -> list[ChartSeries]:
    n = len(closes)
    return [
        ChartSeries(f"RSI {p['period']}", "osc", PURPLE, rsi(closes, p["period"]), y_range=(0, 100)),
        ChartSeries(f"Oversold {p['oversold']}", "osc", GREEN, [p["oversold"]] * n, dash="dot", width=1.2),
        ChartSeries(f"Overbought {p['overbought']}", "osc", RED, [p["overbought"]] * n, dash="dot", width=1.2),
    ]


def _validate(p: dict) -> None:
    if p["oversold"] >= p["overbought"]:
        raise ValueError("Oversold level must be below the overbought level")


RSI_REVERSAL = StrategyDef(
    key="rsi",
    label="RSI",
    summary="RSI scores how fast the price has moved recently from 0 to 100. Low means oversold (buy), high means overbought (sell).",
    works_best="Range-bound markets where price bounces between extremes.",
    struggles="Strong trends, where RSI can stay overbought or oversold for a long time.",
    params=(
        ParamSpec("period", "RSI period", 14, 2, 100),
        ParamSpec("oversold", "Oversold below", 30, 5, 50),
        ParamSpec("overbought", "Overbought above", 70, 50, 95),
    ),
    entry_text="RSI({period}) falls below {oversold}",
    exit_text="RSI({period}) rises above {overbought}",
    generate=_generate,
    chart_series=_series,
    name_fn=lambda p: f"RSI {p['period']} ({p['oversold']}/{p['overbought']})",
    validate=_validate,
)
