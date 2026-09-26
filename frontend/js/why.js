import { money, pnlClass, signedMoney } from "./util.js";

export function signalOutcome(s) {
  if (s.executed) {
    const verb = s.signal === "BUY" ? "Bought" : "Sold";
    const pnl =
      s.realized_pnl === null || s.realized_pnl === undefined
        ? ""
        : ` · P&L <b class="${pnlClass(s.realized_pnl)}">${signedMoney(s.realized_pnl)}</b>`;
    return `${verb} ${s.trade_quantity} at ${money(s.trade_price)}${pnl}`;
  }
  return s.note || "No trade placed";
}

// Signals saved before strategies were generalized only have moving-average fields.
function legacyChecks(s) {
  const d = s.details;
  const buy = s.signal === "BUY";
  return [
    `${d.fast_period}-day average (${money(d.fast_ma)}) ${buy ? "crossed above" : "crossed below"} the ${d.slow_period}-day average (${money(d.slow_ma)})`,
    `The day before it was ${buy ? "at or below" : "at or above"} it: ${money(d.prev_fast_ma)} vs ${money(d.prev_slow_ma)}`,
  ];
}

export function signalHeadline(s) {
  const d = s.details;
  if (d.headline) return d.headline;
  if (d.fast_ma !== undefined) return `${d.fast_period}d ${d.fast_ma.toFixed(2)} vs ${d.slow_period}d ${d.slow_ma.toFixed(2)}`;
  return "";
}

export function whyCard(s) {
  const buy = s.signal === "BUY";
  const d = s.details;
  const checks = d.checks || legacyChecks(s);
  return `<div class="why">
    <b class="t">WHY DID I ${buy ? "BUY" : "SELL"}?</b>
    <ul>
      ${checks.map((line) => `<li>${line}</li>`).join("")}
      <li>Price on that day: ${money(s.price)}</li>
    </ul>
    <div class="why-rule">Rule: ${d.rule}</div>
    <div class="why-outcome">Outcome: ${signalOutcome(s)}</div>
  </div>`;
}
