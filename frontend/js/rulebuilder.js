/** A reusable IF/AND/OR condition editor for custom strategies. Mounted twice (Strategies
 * and Backtests builders) against different container elements; each mount owns its own DOM,
 * this module has no shared state. */

export const PERIOD_MIN = 2;
export const PERIOD_MAX = 500;
export const MAX_CONDITIONS_PER_SIDE = 5;

export const INDICATORS = [
  { key: "price", label: "Price", needsPeriod: false, periodDefault: null },
  { key: "sma", label: "SMA", needsPeriod: true, periodDefault: 20 },
  { key: "rsi", label: "RSI", needsPeriod: true, periodDefault: 14 },
];

export const OPERATORS = [
  { key: ">", label: ">", indicatorRight: false },
  { key: "<", label: "<", indicatorRight: false },
  { key: ">=", label: "≥", indicatorRight: false },
  { key: "<=", label: "≤", indicatorRight: false },
  { key: "crosses_above", label: "crosses above", indicatorRight: true },
  { key: "crosses_below", label: "crosses below", indicatorRight: true },
];

const OP_META = Object.fromEntries(OPERATORS.map((o) => [o.key, o]));

export const DEFAULT_RULES = {
  entry: { logic: "AND", conditions: [{ left: { indicator: "sma", period: 20 }, operator: "crosses_above", right: { indicator: "sma", period: 50 } }] },
  exit: { logic: "AND", conditions: [{ left: { indicator: "sma", period: 20 }, operator: "crosses_below", right: { indicator: "sma", period: 50 } }] },
};

function termLabel(term) {
  if (term.indicator === "price") return "Price";
  if (term.indicator) return `${term.indicator.toUpperCase()}(${term.period})`;
  return `${term.value}`;
}

function sideText(side) {
  return side.conditions.map((c) => `${termLabel(c.left)} ${OP_META[c.operator].label} ${termLabel(c.right)}`).join(` ${side.logic} `);
}

export function ruleSummaryText(rules) {
  return `BUY when ${sideText(rules.entry)}; SELL when ${sideText(rules.exit)}.`;
}

function options(list, selected) {
  return list.map((o) => `<option value="${o.key}" ${o.key === selected ? "selected" : ""}>${o.label}</option>`).join("");
}

function rowHtml(cond) {
  const rightIsIndicator = OP_META[cond.operator].indicatorRight;
  const leftNeedsPeriod = cond.left.indicator === "sma" || cond.left.indicator === "rsi";
  const rightKind = rightIsIndicator ? cond.right.indicator : "sma";
  const rightNeedsPeriod = rightIsIndicator && (cond.right.indicator === "sma" || cond.right.indicator === "rsi");
  return `<div class="cond-row">
    <select class="cond-left-kind">${options(INDICATORS, cond.left.indicator)}</select>
    <input type="number" class="cond-left-period" min="${PERIOD_MIN}" max="${PERIOD_MAX}" value="${cond.left.period ?? 20}" ${leftNeedsPeriod ? "" : "hidden"} />
    <select class="cond-op">${options(OPERATORS, cond.operator)}</select>
    <input type="number" class="cond-right-value" value="${cond.right.value ?? 100}" ${rightIsIndicator ? "hidden" : ""} />
    <select class="cond-right-kind" ${rightIsIndicator ? "" : "hidden"}>${options(INDICATORS, rightKind)}</select>
    <input type="number" class="cond-right-period" min="${PERIOD_MIN}" max="${PERIOD_MAX}" value="${cond.right.period ?? 50}" ${rightNeedsPeriod ? "" : "hidden"} />
    <button type="button" class="cond-remove btn btn-sell" title="Remove condition">&times;</button>
  </div>`;
}

function togglePeriod(row, side) {
  const kindSel = row.querySelector(`.cond-${side}-kind`);
  const periodInput = row.querySelector(`.cond-${side}-period`);
  const needsPeriod = kindSel.value === "sma" || kindSel.value === "rsi";
  periodInput.hidden = kindSel.hidden || !needsPeriod;
}

function updateRowVisibility(row) {
  const op = row.querySelector(".cond-op").value;
  const indicatorRight = OP_META[op].indicatorRight;
  row.querySelector(".cond-right-value").hidden = indicatorRight;
  row.querySelector(".cond-right-kind").hidden = !indicatorRight;
  togglePeriod(row, "left");
  togglePeriod(row, "right");
}

function readConditionRow(row) {
  const leftKind = row.querySelector(".cond-left-kind").value;
  const left = leftKind === "price" ? { indicator: "price" } : { indicator: leftKind, period: parseInt(row.querySelector(".cond-left-period").value, 10) };
  const operatorKey = row.querySelector(".cond-op").value;
  let right;
  if (OP_META[operatorKey].indicatorRight) {
    const rightKind = row.querySelector(".cond-right-kind").value;
    right = rightKind === "price" ? { indicator: "price" } : { indicator: rightKind, period: parseInt(row.querySelector(".cond-right-period").value, 10) };
  } else {
    right = { value: parseFloat(row.querySelector(".cond-right-value").value) };
  }
  return { left, operator: operatorKey, right };
}

/** Render a side's condition rows into `container` (its own logic <select> is managed by the caller). */
export function renderSide(container, side) {
  container.innerHTML = side.conditions.map(rowHtml).join("");
  container.querySelectorAll(".cond-row").forEach(updateRowVisibility);
}

export function addRow(container) {
  if (container.children.length >= MAX_CONDITIONS_PER_SIDE) return;
  container.insertAdjacentHTML("beforeend", rowHtml({ left: { indicator: "price" }, operator: ">", right: { value: 100 } }));
  updateRowVisibility(container.lastElementChild);
}

export function readSide(container, logic) {
  return { logic, conditions: [...container.querySelectorAll(".cond-row")].map(readConditionRow) };
}

/** Wire one side's row container: operator/indicator changes toggle inputs, remove deletes a row.
 * Event delegation means rows added later (via addRow) need no extra wiring. */
export function initSide(container, onChange) {
  container.addEventListener("change", (e) => {
    const row = e.target.closest(".cond-row");
    if (!row) return;
    if (e.target.classList.contains("cond-op") || e.target.classList.contains("cond-left-kind") || e.target.classList.contains("cond-right-kind")) {
      updateRowVisibility(row);
    }
    onChange?.();
  });
  container.addEventListener("input", (e) => {
    if (e.target.matches("input")) onChange?.();
  });
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".cond-remove");
    if (!btn) return;
    if (container.children.length > 1) btn.closest(".cond-row").remove();
    onChange?.();
  });
}
