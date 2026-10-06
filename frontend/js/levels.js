// Which price lines to draw on the Trade chart for the selected stock. Pure logic (no DOM) so it
// can be tested with `node --test frontend/js/levels.test.mjs`.
//
// There are two sources. A position you hold gives its entry (average price) and any stop-loss and
// take-profit it carries. An order being composed on the ticket gives a *preview* of the levels it
// would set, so you can see where they sit among the recent candles before buying. A valid
// preview takes precedence, since that is what you are looking at; a half-typed one (a stop above
// the price, say) is ignored and the position's own lines show instead.

/** A level this far from the current price (as a fraction of it) is drawn only if it is within reach;
 *  a target 60% away would otherwise flatten every candle to make room for its line. */
export const MAX_AWAY = 0.25;

const away = (level, price) => (price > 0 ? (level / price - 1) * 100 : 0);

/**
 * @param {number} price     the stock's current price
 * @param {object|null} position  { average_price, quantity, stop_price, target_price } or null
 * @param {object|null} order     { stop, target, quantity, problems } from the order ticket, or null
 * @returns {{kind: "entry"|"stop"|"target", price: number, preview: boolean, awayPct: number,
 *            quantity: number, ifHit: number|null}[]}
 *   awayPct: how far the level is from the current price, in percent.
 *   ifHit:   the profit or loss, in rupees before costs, if the position closed there (stop and target only).
 */
export function buildLevels({ price, position = null, order = null }) {
  const previewing = order && (order.stop != null || order.target != null) && !(order.problems && order.problems.length);
  const source = previewing
    ? { preview: true, entry: price, quantity: order.quantity > 0 ? order.quantity : 0, stop: order.stop, target: order.target }
    : position
      ? { preview: false, entry: position.average_price, quantity: position.quantity, stop: position.stop_price, target: position.target_price }
      : null;
  if (!source) return [];

  const make = (kind, level) => ({
    kind,
    price: level,
    preview: source.preview,
    awayPct: away(level, price),
    quantity: source.quantity,
    ifHit: kind === "entry" || source.quantity <= 0 ? null : (level - source.entry) * source.quantity,
  });
  const levels = [make("entry", source.entry)];
  if (source.stop != null) levels.push(make("stop", source.stop));
  if (source.target != null) levels.push(make("target", source.target));
  return levels;
}

/** The prices the chart's axis should make room for: the levels within MAX_AWAY of `price`. */
export function reachableLevelPrices(levels, price, maxAway = MAX_AWAY) {
  return levels.map((l) => l.price).filter((p) => Math.abs(p / price - 1) <= maxAway);
}
