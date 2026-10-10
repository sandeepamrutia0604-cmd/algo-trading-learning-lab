// Small pure helpers for the Portfolio backtest page (no DOM), tested with `node --test frontend/js/portfolio.test.mjs`.
// The server enforces the same limits (backend/app/services/portfolio_backtest_service.py).

export const MIN_STOCKS = 2;
export const MAX_STOCKS = 20;

/** A plain message if `symbols` is not a usable basket, else null. */
export function checkSelection(symbols) {
  const n = new Set(symbols).size;
  if (n < MIN_STOCKS) return `Choose at least ${MIN_STOCKS} stocks (you have ${n})`;
  if (n > MAX_STOCKS) return `Choose at most ${MAX_STOCKS} stocks (you have ${n})`;
  return null;
}

const REASONS = [
  ["cash", (n) => `${n} for lack of cash`],
  ["max_positions", (n) => `${n} because the maximum number of open positions was reached`],
  ["allocation", (n) => `${n} for being over the maximum share of the account in one stock`],
  ["size", (n) => `${n} because the position size worked out to zero shares`],
];

/** "3 for lack of cash, 1 because ..." from the server's skipped_by_reason; "" when nothing was skipped. */
export function skipText(byReason) {
  return REASONS.filter(([key]) => byReason && byReason[key] > 0)
    .map(([key, say]) => say(byReason[key]))
    .join(", ");
}

/** Trades oldest first, ties in symbol order: the order they happened in. Does not change the list it is given. */
export function inOrder(trades) {
  return [...trades].sort((a, b) => (a.entry_date < b.entry_date ? -1 : a.entry_date > b.entry_date ? 1 : a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0));
}

/** The basket to show as chosen after the list of stocks changes: keeps picks that still exist, in list order. */
export function keepExisting(picked, available) {
  const have = new Set(available);
  return available.filter((s) => picked.includes(s) && have.has(s));
}

/** "ALPHA, BETA, GAMMA +2" for a long basket. */
export function basketLabel(symbols, show = 4) {
  return symbols.slice(0, show).join(", ") + (symbols.length > show ? ` +${symbols.length - show}` : "");
}
