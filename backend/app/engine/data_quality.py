"""Checks on a stock's daily candles: does the history look trustworthy? Pure logic: no database, no I/O.

Every backtest, indicator and chart is only as good as the prices under it, and bad prices rarely
look bad: a stock split that one data source adjusted for and another didn't shows up as a
"-50% day" that the strategy dutifully trades around; a missing fortnight silently stretches every
moving average; a candle whose high is below its close is simply impossible. These checks look for
those patterns and say what they found in plain words. They never change the data, and most of
what they flag is a *question* ("this looks like an unadjusted split -- is it?"), not a verdict:
real events (results, crashes, circuit-breaker days) can look the same.

Severity:
  error    -- impossible data (a high below the low, a price of zero). Something is corrupt.
  warning  -- unusual enough that it could distort results; worth a look.
  info     -- worth knowing, probably harmless (a long holiday gap, a short history).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from ..adapters.base import Candle

BIG_MOVE_PCT = 20.0  # most NSE stocks can't move more than 20% in a day
WIDE_RANGE_PCT = 25.0  # a day's high is this far above its low
STALE_RUN_DAYS = 3  # this many flat (open = high = low = close) candles in a row
GAP_WARNING_WEEKDAYS = 6  # this many weekdays with no candle between two candles
GAP_INFO_WEEKDAYS = 3  # holidays explain up to a few; more is worth a mention
SHORT_HISTORY_WARNING = 60  # too little for a 50-day average to mean much
SHORT_HISTORY_INFO = 250  # under about a year

# Ratios a split or bonus issue leaves behind: 1:2 split is x0.5, 1:5 is x0.2, a 3:2 bonus is x0.667...
# A reverse split is the same ratio upside down. Only checked on a move of at least SPLIT_MIN_MOVE_PCT.
SPLIT_RATIOS = (1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 10, 1 / 20, 2 / 3)
SPLIT_MIN_MOVE_PCT = 30.0
SPLIT_TOLERANCE = 0.04  # how close to a ratio, as a fraction of it

SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class Issue:
    kind: str
    severity: str
    message: str
    date: date | None = None
    value: float | None = None  # the number behind the message (a % move, a day count)


def _weekdays_between(first: date, last: date) -> int:
    """Weekdays strictly between two dates."""
    count, day = 0, first + timedelta(days=1)
    while day < last:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def _split_ratio(ratio: float) -> float | None:
    """The split or bonus ratio a close-to-close ratio resembles, or None."""
    if abs(ratio - 1) * 100 < SPLIT_MIN_MOVE_PCT:
        return None
    for target in SPLIT_RATIOS:
        for candidate in (target, 1 / target):
            if abs(ratio / candidate - 1) <= SPLIT_TOLERANCE:
                return candidate
    return None


def _ratio_words(ratio: float) -> str:
    """A split ratio in words: 0.5 -> 'a 1-for-2 split (or a 1:1 bonus)', 2 -> 'a 2-for-1 reverse split'."""
    if ratio < 1:
        shares = round(1 / ratio, 2)
        shares = int(shares) if shares == int(shares) else shares
        return f"a split or bonus issue that multiplied the share count by {shares}"
    factor = int(ratio) if ratio == int(ratio) else round(ratio, 2)
    return f"a reverse split that divided the share count by {factor}"


def check_prices(candles: list[Candle]) -> list[Issue]:
    issues: list[Issue] = []
    for c in candles:
        if min(c.open, c.high, c.low, c.close) <= 0:
            issues.append(Issue("non_positive", "error", "A price is zero or negative, which can't be real.", c.date))
        elif c.high < c.low:
            issues.append(Issue("bad_ohlc", "error", f"The day's high ({c.high:g}) is below its low ({c.low:g}).", c.date))
        elif c.high < max(c.open, c.close):
            issues.append(
                Issue("bad_ohlc", "error", f"The day's high ({c.high:g}) is below its open or close, which can't happen.", c.date)
            )
        elif c.low > min(c.open, c.close):
            issues.append(
                Issue("bad_ohlc", "error", f"The day's low ({c.low:g}) is above its open or close, which can't happen.", c.date)
            )
        elif c.low > 0 and (c.high / c.low - 1) * 100 >= WIDE_RANGE_PCT:
            move = (c.high / c.low - 1) * 100
            issues.append(
                Issue("wide_range", "warning", f"The day's high was {move:.0f}% above its low, an unusually wild single day.", c.date, move)
            )
    return issues


def check_jumps(candles: list[Candle]) -> list[Issue]:
    """Big close-to-close moves, and the ones that look like an unadjusted split or bonus issue."""
    issues: list[Issue] = []
    for previous, c in zip(candles, candles[1:]):
        if previous.close <= 0 or c.close <= 0:
            continue
        ratio = c.close / previous.close
        move = (ratio - 1) * 100
        if abs(move) < BIG_MOVE_PCT:
            continue
        split = _split_ratio(ratio)
        if split is not None:
            issues.append(
                Issue(
                    "possible_split",
                    "warning",
                    f"The close moved {move:+.1f}% in a day, almost exactly what {_ratio_words(split)} would cause. "
                    "If so, the history before this date is on a different scale from the history after it. "
                    "This often happens when two data sources were merged and only one adjusted for the split.",
                    c.date,
                    move,
                )
            )
        else:
            issues.append(
                Issue(
                    "big_jump",
                    "warning",
                    f"The close moved {move:+.1f}% in a single day. Real news can do that, but so can a data error; "
                    "a strategy will treat it as a real gain or loss either way.",
                    c.date,
                    move,
                )
            )
    return issues


def check_dates(candles: list[Candle]) -> list[Issue]:
    issues: list[Issue] = []
    for c in candles:
        if c.date.weekday() >= 5:
            issues.append(
                Issue(
                    "weekend_candle",
                    "info",
                    f"This candle is on a {c.date.strftime('%A')}. The exchange sometimes trades on a weekend (for example "
                    "Muhurat trading on Diwali), but it can also mean a wrong date.",
                    c.date,
                )
            )
    for previous, c in zip(candles, candles[1:]):
        missing = _weekdays_between(previous.date, c.date)
        if missing >= GAP_WARNING_WEEKDAYS:
            issues.append(
                Issue(
                    "missing_days",
                    "warning",
                    f"{missing} weekdays have no candle between {previous.date} and {c.date}. That is longer than any "
                    "holiday stretch, so some days are probably missing; averages and signals will treat the gap as one day.",
                    c.date,
                    float(missing),
                )
            )
        elif missing >= GAP_INFO_WEEKDAYS:
            issues.append(
                Issue(
                    "missing_days",
                    "info",
                    f"{missing} weekdays have no candle between {previous.date} and {c.date}. Market holidays can explain this.",
                    c.date,
                    float(missing),
                )
            )
    return issues


def check_flat_runs(candles: list[Candle]) -> list[Issue]:
    """Runs of candles where nothing moved at all: a halted or illiquid stock, or days someone filled in."""
    issues: list[Issue] = []
    run: list[Candle] = []

    def close_run():
        if len(run) >= STALE_RUN_DAYS:
            issues.append(
                Issue(
                    "flat_run",
                    "warning",
                    f"The price didn't move at all for {len(run)} days in a row (open, high, low and close identical at "
                    f"{run[0].close:g}). The stock may have been halted or barely traded, or the days were filled in.",
                    run[0].date,
                    float(len(run)),
                )
            )

    for c in candles:
        flat = c.open == c.high == c.low == c.close
        if flat and (not run or run[-1].close == c.close):
            run.append(c)
            continue
        close_run()
        run = [c] if flat else []
    close_run()
    return issues


def check_volume(candles: list[Candle]) -> list[Issue]:
    zero = [c for c in candles if c.volume <= 0]
    if not zero:
        return []
    if len(zero) == len(candles):
        return [Issue("no_volume", "info", "The file has no volume figures, so nothing here can use volume.")]
    return [
        Issue(
            "zero_volume",
            "info",
            f"{len(zero)} days show zero volume although the stock trades on other days, which usually means the volume is missing.",
            zero[0].date,
            float(len(zero)),
        )
    ]


def check_length(candles: list[Candle]) -> list[Issue]:
    n = len(candles)
    if n < SHORT_HISTORY_WARNING:
        return [
            Issue(
                "short_history",
                "warning",
                f"Only {n} days of history. A 50-day average needs more than that to mean anything, and a backtest on this "
                "few days proves very little.",
                value=float(n),
            )
        ]
    if n < SHORT_HISTORY_INFO:
        return [
            Issue(
                "short_history",
                "info",
                f"{n} days of history, less than a year. Enough to try things out, but results from so little data are easily luck.",
                value=float(n),
            )
        ]
    return []


def scan(candles: list[Candle]) -> list[Issue]:
    """Every issue found in `candles` (oldest first), most serious first, then by date."""
    if not candles:
        return []
    issues = check_prices(candles) + check_jumps(candles) + check_dates(candles) + check_flat_runs(candles)
    issues += check_volume(candles) + check_length(candles)
    order = {severity: rank for rank, severity in enumerate(SEVERITIES)}
    return sorted(issues, key=lambda i: (order[i.severity], i.date or date.min, i.kind))


def counts(issues: list[Issue]) -> dict[str, int]:
    return {severity: sum(1 for i in issues if i.severity == severity) for severity in SEVERITIES}


def status(issues: list[Issue]) -> str:
    """'problems' if anything is corrupt, 'check' if anything is worth a look, else 'clean'."""
    found = counts(issues)
    if found["error"]:
        return "problems"
    return "check" if found["warning"] else "clean"
