"""Monte Carlo analysis of a backtest's trades. Pure logic: no database, no I/O.

A backtest is one path through history. Its max drawdown and even its final result depend partly
on luck: the order the wins and losses happened to arrive in, and which trades happened at all.
Monte Carlo re-plays the same trades many times to show how wide that luck is.

Each closed trade is reduced to its return on the account at the moment it was opened. Trades
never overlap (a strategy holds one position at a time), so the account's value just before a
trade is exactly the starting capital plus the profit and loss of every earlier trade, which makes
that return exact. A simulated path then compounds those returns in a new order:

  shuffle    the same trades in a random order. The total is unchanged (compounding does not
             care about order), so this isolates *sequence risk*: how bad the drawdown could
             have been had the same wins and losses come in another order.
  bootstrap  the same number of trades drawn at random *with replacement* from the originals.
             Some trades repeat and some never appear, so the total changes too: it shows how
             much of the result was down to which trades happened to occur.

Both assume the future's trades will look like the past's and that one trade does not influence
the next. They measure the luck inside one backtest; they do not predict the future.

Drawdown here is measured between closed trades (the account after each trade), so it is a little
smaller than the daily mark-to-market drawdown a backtest reports.
"""

import random

METHODS = ("shuffle", "bootstrap")
PERCENTILES = (5, 25, 50, 75, 95)
HISTOGRAM_BINS = 30
MAX_FAN_POINTS = 60  # points along the trade axis kept for the fan chart, however many trades there are
DRAWDOWN_THRESHOLDS = (10, 20, 30, 40, 50)


def percentile(sorted_values: list[float], pct: float) -> float:
    """The pct-th percentile of already-sorted values, interpolating between neighbours."""
    if not sorted_values:
        raise ValueError("no values")
    position = (len(sorted_values) - 1) * pct / 100
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def account_returns(initial_capital: float, pnls: list[float]) -> list[float]:
    """Each trade's profit or loss as a fraction of the account just before it opened.
    Stops at the first trade that would start with an empty account."""
    returns, equity = [], initial_capital
    for pnl in pnls:
        if equity <= 0:
            break
        returns.append(pnl / equity)
        equity += pnl
    return returns


def _path(initial_capital: float, returns: list[float]) -> list[float]:
    equity, path = initial_capital, [initial_capital]
    for r in returns:
        equity = max(0.0, equity * (1 + r))  # an account cannot go below zero
        path.append(equity)
    return path


def max_drawdown_pct(path: list[float]) -> float:
    peak, worst = path[0], 0.0
    for value in path:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100)
    return worst


def _fan_indices(steps: int) -> list[int]:
    """Which trade numbers (0 .. steps) to keep for the fan chart: all of them when there are few."""
    if steps + 1 <= MAX_FAN_POINTS:
        return list(range(steps + 1))
    return sorted({round(i * steps / (MAX_FAN_POINTS - 1)) for i in range(MAX_FAN_POINTS)})


def _histogram(values: list[float]) -> dict:
    low, high = min(values), max(values)
    if high - low < 1e-9:  # every simulation agreed (a shuffle's total, say): one bar
        return {"edges": [low, high if high > low else low + 1e-6], "counts": [len(values)]}
    width = (high - low) / HISTOGRAM_BINS
    counts = [0] * HISTOGRAM_BINS
    for value in values:
        counts[min(HISTOGRAM_BINS - 1, int((value - low) / width))] += 1
    return {"edges": [low + i * width for i in range(HISTOGRAM_BINS + 1)], "counts": counts}


def _summary(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "mean": sum(values) / len(values),
        "min": ordered[0],
        "max": ordered[-1],
        "percentiles": {str(p): percentile(ordered, p) for p in PERCENTILES},
        "histogram": _histogram(values),
    }


def simulate(
    initial_capital: float,
    returns: list[float],
    simulations: int,
    method: str = "bootstrap",
    seed: int | None = None,
) -> dict:
    """Run `simulations` re-orderings (or resamplings) of `returns`, and summarise what happened.
    `returns` are per-trade account returns as fractions (0.02 is +2%), see account_returns."""
    if method not in METHODS:
        raise ValueError(f"Unknown method '{method}'. Choose one of: {', '.join(METHODS)}")
    if not returns:
        raise ValueError("There are no trades to simulate")
    if simulations < 1:
        raise ValueError("Run at least one simulation")

    rng = random.Random(seed)
    steps = len(returns)
    keep = _fan_indices(steps)
    final_returns: list[float] = []
    drawdowns: list[float] = []
    columns: list[list[float]] = [[] for _ in keep]

    for _ in range(simulations):
        if method == "shuffle":
            order = returns[:]
            rng.shuffle(order)
        else:
            order = rng.choices(returns, k=steps)
        path = _path(initial_capital, order)
        final_returns.append((path[-1] / initial_capital - 1) * 100)
        drawdowns.append(max_drawdown_pct(path))
        for slot, index in enumerate(keep):
            columns[slot].append(path[index])

    original = _path(initial_capital, returns)
    original_return = (original[-1] / initial_capital - 1) * 100
    original_drawdown = max_drawdown_pct(original)
    bands = {str(p): [percentile(sorted(column), p) for column in columns] for p in PERCENTILES}

    return {
        "method": method,
        "simulations": simulations,
        "trade_count": steps,
        "original": {"return_pct": original_return, "max_drawdown_pct": original_drawdown},
        "final_return": _summary(final_returns),
        "max_drawdown": _summary(drawdowns),
        "probability_of_loss_pct": sum(1 for r in final_returns if r < 0) / simulations * 100,
        "drawdown_exceeds_pct": [
            {"threshold": t, "pct": sum(1 for d in drawdowns if d >= t) / simulations * 100} for t in DRAWDOWN_THRESHOLDS
        ],
        # How the actual backtest compares with the simulations: the share of them it beat.
        "original_drawdown_worse_than_pct": sum(1 for d in drawdowns if d < original_drawdown - 1e-9) / simulations * 100,
        "original_return_better_than_pct": sum(1 for r in final_returns if r < original_return - 1e-9) / simulations * 100,
        "fan": {
            "trade_numbers": keep,
            "bands": bands,
            "original": [original[i] for i in keep],
        },
    }
