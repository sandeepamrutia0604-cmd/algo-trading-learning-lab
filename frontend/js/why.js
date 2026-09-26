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

export function whyCard(s) {
  const buy = s.signal === "BUY";
  const d = s.details;
  const above = buy ? "crossed above" : "crossed below";
  const before = buy ? "at or below" : "at or above";
  return `<div class="why">
    <b class="t">WHY DID I ${buy ? "BUY" : "SELL"}?</b>
    <ul>
      <li>${d.fast_period}-day average (${money(d.fast_ma)}) ${above} the ${d.slow_period}-day average (${money(d.slow_ma)})</li>
      <li>The day before it was ${before} it: ${money(d.prev_fast_ma)} vs ${money(d.prev_slow_ma)}</li>
      <li>Price on that day: ${money(s.price)}</li>
    </ul>
    <div class="why-rule">Rule: ${d.rule}</div>
    <div class="why-outcome">Outcome: ${signalOutcome(s)}</div>
  </div>`;
}
