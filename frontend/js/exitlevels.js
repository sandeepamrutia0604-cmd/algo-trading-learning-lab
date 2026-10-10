// The optional order-level stop-loss and take-profit a backtest, optimisation or walk-forward can use. Pure logic
// (no DOM), so it can be tested with `node --test frontend/js/exitlevels.test.mjs`. The server checks the same limits
// (backend/app/schemas.py): a stop is more than 0% and less than 100% below the entry, a target is more than 0% and
// up to 1000% above it. An empty box means "none".

const parse = (text) => {
  const trimmed = String(text ?? "").trim();
  return trimmed === "" ? null : Number(trimmed);
};

/**
 * @param {string} stopText    what is typed in the stop-loss box
 * @param {string} targetText  what is typed in the take-profit box
 * @returns {{values: {stop_loss_pct?: number, take_profit_pct?: number}, error: string|null}}
 *   `values` holds only the levels that are set, ready to spread into a request.
 */
export function parseExitLevels(stopText, targetText) {
  const stop = parse(stopText);
  const target = parse(targetText);
  if (stop !== null && !(stop > 0 && stop < 100)) {
    return { values: {}, error: "The stop-loss must be more than 0% and less than 100% below the entry price (or leave it empty)" };
  }
  if (target !== null && !(target > 0 && target <= 1000)) {
    return { values: {}, error: "The take-profit must be more than 0% above the entry price, up to 1000% (or leave it empty)" };
  }
  return {
    values: { ...(stop !== null ? { stop_loss_pct: stop } : {}), ...(target !== null ? { take_profit_pct: target } : {}) },
    error: null,
  };
}

/** A short phrase for headings and labels: "5% stop / 10% target", or "" when neither is set. */
export function describeExitLevels(stop, target) {
  const parts = [stop ? `${stop}% stop` : "", target ? `${target}% target` : ""].filter(Boolean);
  return parts.join(" / ");
}
