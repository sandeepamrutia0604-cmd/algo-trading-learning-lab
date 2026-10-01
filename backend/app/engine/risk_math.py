"""Pure risk-management formulas shared between live auto-trading (risk_service, which
resolves them against the real DB portfolio) and the backtest engine (which resolves them
against a backtest's own simulated capital) — so a backtest's position sizing and stop-loss
exactly match what live auto-trading would have done with the same settings."""


def position_size(equity: float, price: float, max_risk_pct: float, stop_loss_pct: float, fallback_qty: int) -> int:
    """Risk-based share count: (equity * risk%) / (price * stop-loss%), the sizing formula
    from the plan's worked example. Falls back to `fallback_qty` (a fixed quantity) when the
    formula isn't fully configured."""
    if not max_risk_pct or not stop_loss_pct:
        return fallback_qty
    risk_amount = equity * max_risk_pct / 100
    risk_per_share = price * stop_loss_pct / 100
    if risk_per_share <= 0:
        return fallback_qty
    return max(0, int(risk_amount // risk_per_share))


def stop_loss_price(entry_price: float, stop_loss_pct: float) -> float:
    return entry_price * (1 - stop_loss_pct / 100)
