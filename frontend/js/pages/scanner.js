import { $, api, money, pnlClass, signedPercent, toast } from "../util.js";
import { hooks, store } from "../store.js";

const state = { result: null, runId: 0, running: false, optionKey: "" };

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const typeOf = (key) => store.strategyTypes.find((t) => t.key === key);
const mine = (id) => store.strategies.find((s) => String(s.id) === String(id));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const ago = (days) => (days === 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`);

/* ---------------- choosing the strategy ---------------- */

/** The strategies you can scan with: your own saved ones (they bring their settings, custom rules included)
 *  and each built-in type (with settings you can change here). */
function buildSources() {
  const key = JSON.stringify([store.strategyTypes.map((t) => t.key), store.strategies.map((s) => [s.id, s.name])]);
  if (key === state.optionKey) return;
  const wanted = $("sc-source").value;
  state.optionKey = key;
  const yours = store.strategies.map((s) => `<option value="mine:${s.id}">${escapeHtml(s.name)} (${s.symbol})</option>`).join("");
  const built = store.strategyTypes.map((t) => `<option value="type:${t.key}">${escapeHtml(t.label)}</option>`).join("");
  $("sc-source").innerHTML = (yours ? `<optgroup label="Your strategies">${yours}</optgroup>` : "") + `<optgroup label="Built-in strategy types">${built}</optgroup>`;
  const stillThere = [...$("sc-source").options].some((o) => o.value === wanted);
  $("sc-source").value = stillThere ? wanted : $("sc-source").options[0]?.value;
  renderSourceDetail();
}

function renderSourceDetail() {
  const [kind, id] = ($("sc-source").value || ":").split(":");
  const params = $("sc-params");
  if (kind === "mine") {
    const s = mine(id);
    params.innerHTML = "";
    $("sc-rule").innerHTML = s
      ? `<b>${escapeHtml(s.name)}</b>: ${escapeHtml(s.type_label)}, ${escapeHtml(s.param_summary)}. It is scanned across every stock with these settings; change them on the Strategies page.`
      : "";
    return;
  }
  const type = typeOf(id);
  if (!type) return;
  params.innerHTML = type.params
    .map(
      (p) => `<label class="field">${escapeHtml(p.label)}
        <input type="number" data-param="${p.name}" data-kind="${p.kind}" min="${p.min}" max="${p.max}" step="${p.step}" value="${p.default}" /></label>`,
    )
    .join("");
  const describe = () => {
    const values = readParams();
    const fill = (text) => text.replace(/\{(\w+)\}/g, (_, name) => (Number.isNaN(values[name]) || values[name] === undefined ? "?" : values[name]));
    $("sc-rule").innerHTML = `${escapeHtml(type.summary)}<br><b class="up">BUY</b> when ${fill(type.entry_text)}. <b class="down">SELL</b> when ${fill(type.exit_text)}.`;
  };
  params.querySelectorAll("input").forEach((input) => input.addEventListener("input", describe));
  describe();
}

function readParams() {
  const values = {};
  $("sc-params").querySelectorAll("input[data-param]").forEach((input) => {
    values[input.dataset.param] = input.dataset.kind === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
  });
  return values;
}

function request() {
  const [kind, id] = $("sc-source").value.split(":");
  if (kind === "mine") {
    const s = mine(id);
    return { type: s.type, params: s.params || {}, rules: s.rules || null };
  }
  return { type: id, params: readParams() };
}

/* ---------------- results ---------------- */

const chip = (side) => `<span class="sc-chip ${side === "BUY" ? "buy" : "sell"}">${side}</span>`;

function signalCell(signal) {
  if (!signal) return `<span class="muted">-</span>`;
  return `${chip(signal.side)} <span title="${escapeHtml(signal.checks.join("\n"))}">${escapeHtml(signal.headline)}</span>`;
}

function lastCell(signal) {
  if (!signal) return `<span class="muted">no signal yet</span>`;
  return `${signal.side === "BUY" ? "Bought" : "Sold"} <span class="muted">${ago(signal.days_ago)} (${signal.date})</span>`;
}

const STATE_TEXT = {
  in: `<span class="up">In a trade</span>`,
  out: `<span class="muted">Out</span>`,
  none: `<span class="muted">-</span>`,
};

function rowHtml(r) {
  const today = r.signal_today ? (r.signal_today.side === "BUY" ? "sc-buy" : "sc-sell") : "";
  return `<tr class="${today}" data-symbol="${escapeHtml(r.symbol)}">
    <td><b>${escapeHtml(r.symbol)}</b><small class="muted">${escapeHtml(r.name)}</small></td>
    <td class="num">${money(r.price)}</td>
    <td class="num ${r.change_pct === null ? "" : pnlClass(r.change_pct)}">${r.change_pct === null ? "-" : signedPercent(r.change_pct)}</td>
    <td>${signalCell(r.signal_today)}</td>
    <td>${lastCell(r.last_signal)}</td>
    <td>${STATE_TEXT[r.state]}</td>
    <td class="num">${r.held ? r.held : `<span class="muted">-</span>`}</td>
    <td><button class="btn" data-open="${escapeHtml(r.symbol)}">Open</button></td>
  </tr>`;
}

function renderResults() {
  const result = state.result;
  if (!result) return;
  const { buy_today: buys, sell_today: sells } = result;
  $("sc-summary").innerHTML =
    `<b>${escapeHtml(result.strategy)}</b> across ${plural(result.scanned, "stock")} as of <b>${result.market_date || "-"}</b>: ` +
    `<b class="up">${plural(buys, "BUY")}</b> and <b class="down">${plural(sells, "SELL")}</b> today, ${result.in_trade} currently in a trade.`;

  const onlyToday = $("sc-only").checked;
  const rows = onlyToday ? result.rows.filter((r) => r.signal_today) : result.rows;
  if (!rows.length) {
    $("sc-results").innerHTML = `<p class="empty">No stock is signalling today with this strategy. Untick the box to see each stock's most recent signal, or press +1 day to move the market on.</p>`;
    return;
  }
  $("sc-results").innerHTML = `<table class="sc-table">
    <thead><tr><th>Stock</th><th class="num">Price</th><th class="num">Day</th><th>Signal today</th><th>Last signal</th><th>Strategy</th><th class="num">You hold</th><th></th></tr></thead>
    <tbody>${rows.map(rowHtml).join("")}</tbody></table>`;
}

async function runScan({ quiet = false } = {}) {
  if (state.running || !$("sc-source").value) return;
  state.running = true;
  const button = $("sc-run");
  button.disabled = true;
  const runId = ++state.runId;
  try {
    const result = await api("/scanner/run", { method: "POST", body: JSON.stringify(request()) });
    if (runId !== state.runId) return;
    state.result = result;
    renderResults();
  } catch (err) {
    if (!quiet) toast(err.message, true);
    $("sc-summary").innerHTML = "";
    $("sc-results").innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
  } finally {
    state.running = false;
    button.disabled = false;
  }
}

/* Entering the page, and every refresh after the market or your strategies change, scans again, so
   the list always describes the market date shown in the top bar. */
export async function renderScanner() {
  buildSources();
  await runScan({ quiet: true });
}

export function initScanner() {
  $("sc-source").addEventListener("change", () => {
    renderSourceDetail();
    runScan();
  });
  $("sc-run").addEventListener("click", () => runScan());
  $("sc-only").addEventListener("change", renderResults);
  $("sc-results").addEventListener("click", (e) => {
    const open = e.target.closest("[data-open]");
    if (!open) return;
    store.symbol = open.dataset.open;
    hooks.navigate("trade");
  });
}
