import { $, api, money, percent, pnlClass, signedPercent, toast } from "../util.js";
import { store } from "../store.js";
import { drawEquityChart, drawMultiLineChart, drawPriceChart, loadChartData } from "../chart.js";
import * as rb from "../rulebuilder.js";

const MAX_COMPARE = 6;
const COMPARE_COLORS = ["#4c8dff", "#f5a524", "#a78bfa", "#26a69a", "#ef5350", "#8a94a3"];

const state = { result: null, running: false, compareList: [] };

const typeOf = (key) => store.strategyTypes.find((t) => t.key === key);
const isCustom = () => $("bt-type").value === "custom";

/* ---------------- builder ---------------- */

function readParams() {
  const values = {};
  $("bt-params").querySelectorAll("input[data-param]").forEach((input) => {
    values[input.dataset.param] = input.dataset.kind === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
  });
  return values;
}

function renderRule() {
  const type = typeOf($("bt-type").value);
  if (!type) return;
  const values = readParams();
  const fill = (text) => text.replace(/\{(\w+)\}/g, (_, key) => (Number.isNaN(values[key]) || values[key] === undefined ? "?" : values[key]));
  $("bt-rule").innerHTML = `<div><b class="up">BUY</b> when ${fill(type.entry_text)}</div><div><b class="down">SELL</b> when ${fill(type.exit_text)}</div>`;
}

function renderTypeFields() {
  const type = typeOf($("bt-type").value);
  if (!type) return;
  $("bt-desc").innerHTML = `<p>${type.summary}</p>
    <p><b class="up">Works best:</b> ${type.works_best}</p>
    <p><b class="down">Struggles:</b> ${type.struggles}</p>`;
  $("bt-params").innerHTML = type.params
    .map(
      (p) => `<label class="field">${p.label}
        <input type="number" data-param="${p.name}" data-kind="${p.kind}" min="${p.min}" max="${p.max}" step="${p.step}" value="${p.default}" />
      </label>`,
    )
    .join("");
  $("bt-params").querySelectorAll("input").forEach((input) => input.addEventListener("input", renderRule));
  renderRule();
}

function updateCustomPreview() {
  const rules = { entry: rb.readSide($("bt-entry-rows"), $("bt-entry-logic").value), exit: rb.readSide($("bt-exit-rows"), $("bt-exit-logic").value) };
  $("bt-custom-preview").textContent = rb.ruleSummaryText(rules);
}

function renderCustomRules(rules) {
  $("bt-entry-logic").value = rules.entry.logic;
  $("bt-exit-logic").value = rules.exit.logic;
  rb.renderSide($("bt-entry-rows"), rules.entry);
  rb.renderSide($("bt-exit-rows"), rules.exit);
  updateCustomPreview();
}

function switchBuilderMode() {
  const custom = isCustom();
  $("bt-desc").hidden = custom;
  $("bt-params").hidden = custom;
  $("bt-rule").hidden = custom;
  $("bt-custom").hidden = !custom;
}

function applyBuilderDefaults() {
  switchBuilderMode();
  if (isCustom()) renderCustomRules(rb.DEFAULT_RULES);
  else renderTypeFields();
}

function renderBuilder() {
  const typeSelect = $("bt-type");
  if (typeSelect.options.length !== store.strategyTypes.length + 1) {
    typeSelect.innerHTML =
      store.strategyTypes.map((t) => `<option value="${t.key}">${t.label}</option>`).join("") +
      `<option value="custom">Custom (build your own rules)</option>`;
    applyBuilderDefaults();
  }
  const symbolSelect = $("bt-symbol");
  if (symbolSelect.options.length !== store.stocks.length) {
    symbolSelect.innerHTML = store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}</option>`).join("");
    symbolSelect.value = store.symbol;
  }
}

/* ---------------- run ---------------- */

async function runBacktest() {
  const quantity = parseInt($("bt-qty").value, 10);
  const initialCapital = parseFloat($("bt-capital").value);
  if (!(quantity >= 1)) return toast("Shares per trade must be at least 1", true);
  if (!(initialCapital > 0)) return toast("Initial capital must be greater than zero", true);

  state.running = true;
  $("bt-run").disabled = true;
  $("bt-run").textContent = "Running...";
  try {
    const body = isCustom()
      ? {
          symbol: $("bt-symbol").value,
          type: "custom",
          rules: { entry: rb.readSide($("bt-entry-rows"), $("bt-entry-logic").value), exit: rb.readSide($("bt-exit-rows"), $("bt-exit-logic").value) },
          quantity,
          initial_capital: initialCapital,
        }
      : { symbol: $("bt-symbol").value, type: $("bt-type").value, params: readParams(), quantity, initial_capital: initialCapital };
    const result = await api("/backtests/run", { method: "POST", body: JSON.stringify(body) });
    state.result = result;
    await renderResults();
  } catch (err) {
    toast(err.message, true);
  } finally {
    state.running = false;
    $("bt-run").disabled = false;
    $("bt-run").textContent = "Run backtest";
  }
}

/* ---------------- results ---------------- */

function toChartTrades(result) {
  const rows = [];
  for (const t of result.trades) {
    rows.push({ symbol: result.symbol, side: "BUY", market_date: t.entry_date, price: t.entry_price, quantity: t.quantity, source: "Backtest" });
    if (!t.open) rows.push({ symbol: result.symbol, side: "SELL", market_date: t.exit_date, price: t.exit_price, quantity: t.quantity, source: "Backtest" });
  }
  return rows;
}

function renderMetrics(r) {
  const tiles = [
    ["Final capital", money(r.final_capital), ""],
    ["Total return", signedPercent(r.total_return_pct), pnlClass(r.total_return_pct)],
    ["Total trades", r.total_trades, ""],
    ["Winning", r.winning_trades, r.winning_trades ? "up" : ""],
    ["Losing", r.losing_trades, r.losing_trades ? "down" : ""],
    ["Win rate", percent(r.win_rate_pct), ""],
    ["Max drawdown", percent(r.max_drawdown_pct), r.max_drawdown_pct > 0 ? "down" : ""],
  ];
  $("bt-metrics").innerHTML = tiles.map(([label, value, cls]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
}

async function renderResults() {
  const r = state.result;
  $("bt-empty").hidden = Boolean(r);
  $("bt-results").hidden = !r;
  if (!r) return;

  $("bt-title").textContent = `${r.type_label} on ${r.symbol}`;
  $("bt-sub").textContent =
    `${r.rule} · ${r.quantity} shares per trade · started with ${money(r.initial_capital)}` +
    (r.skipped_buys ? ` · ${r.skipped_buys} buy signal${r.skipped_buys === 1 ? "" : "s"} skipped for insufficient cash` : "");
  renderMetrics(r);

  const { prices } = await loadChartData(r.symbol, []);
  if (state.result !== r) return;
  const dates = prices.map((p) => p.date);
  const buyHold = prices.map((p) => (r.initial_capital / prices[0].close) * p.close);
  drawEquityChart($("bt-equity"), {
    dates,
    values: r.equity_curve.map((p) => p.value),
    baseline: buyHold,
    valueLabel: "Strategy",
    baselineLabel: "Buy & hold",
  });

  if (typeof Plotly === "undefined") {
    $("bt-chart").textContent = "Chart library failed to load (check your internet connection).";
  } else {
    drawPriceChart($("bt-chart"), { symbol: r.symbol, prices, overlays: r.series, trades: toChartTrades(r), signals: [] });
  }
  $("bt-legend").innerHTML =
    r.series.map((s) => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("") +
    `<span class="up">&#9650; BUY</span><span class="down">&#9660; SELL</span>`;

  renderTrades(r);
}

function renderTrades(r) {
  const closed = r.trades.filter((t) => !t.open);
  const open = r.trades.filter((t) => t.open);
  const rows = [...closed, ...open];
  $("bt-trades-empty").hidden = rows.length > 0;
  document.querySelector("#bt-trades-table tbody").innerHTML = rows
    .map(
      (t) => `<tr>
        <td>${t.entry_date}</td>
        <td class="num">${money(t.entry_price)}</td>
        <td>${t.exit_date || "-"}</td>
        <td class="num">${t.exit_date ? money(t.exit_price) : `<span class="muted">open</span>`}</td>
        <td class="num">${t.quantity}</td>
        <td class="num ${t.pnl == null ? "" : pnlClass(t.pnl)}">${t.pnl == null ? "-" : money(t.pnl)}</td>
        <td class="num ${t.pnl_pct == null ? "" : pnlClass(t.pnl_pct)}">${t.pnl_pct == null ? "-" : percent(t.pnl_pct)}</td>
      </tr>`,
    )
    .join("");
}

/* ---------------- comparison ---------------- */

function addToComparison() {
  if (!state.result) return;
  if (state.compareList.length >= MAX_COMPARE) {
    toast(`You can compare up to ${MAX_COMPARE} strategies at a time. Remove one first.`, true);
    return;
  }
  state.compareList.push({ id: `${Date.now()}-${Math.random()}`, label: `${state.result.type_label} on ${state.result.symbol}`, result: state.result });
  renderComparison();
  toast("Added to comparison.");
}

function removeFromComparison(id) {
  state.compareList = state.compareList.filter((row) => row.id !== id);
  renderComparison();
}

function renderComparison() {
  const rows = state.compareList;
  $("bt-compare-empty").hidden = rows.length > 0;
  $("bt-compare-content").hidden = rows.length === 0;
  $("bt-clear-compare").hidden = rows.length === 0;
  if (!rows.length) return;

  const ranked = [...rows].sort((a, b) => b.result.total_return_pct - a.result.total_return_pct);
  document.querySelector("#bt-compare-table tbody").innerHTML = ranked
    .map(
      (row) => `<tr>
        <td>${row.label}</td>
        <td class="num">${money(row.result.initial_capital)}</td>
        <td class="num">${money(row.result.final_capital)}</td>
        <td class="num ${pnlClass(row.result.total_return_pct)}">${signedPercent(row.result.total_return_pct)}</td>
        <td class="num">${row.result.total_trades}</td>
        <td class="num">${percent(row.result.win_rate_pct)}</td>
        <td class="num ${row.result.max_drawdown_pct > 0 ? "down" : ""}">${percent(row.result.max_drawdown_pct)}</td>
        <td class="num"><button class="btn btn-sell" data-remove="${row.id}">Remove</button></td>
      </tr>`,
    )
    .join("");
  document.querySelector("#bt-compare-table tbody").querySelectorAll("[data-remove]").forEach((btn) =>
    btn.addEventListener("click", () => removeFromComparison(btn.dataset.remove)),
  );

  if (typeof Plotly !== "undefined") {
    drawMultiLineChart(
      $("bt-compare-chart"),
      rows.map((row, i) => ({
        label: row.label,
        dates: row.result.equity_curve.map((p) => p.date),
        values: row.result.equity_curve.map((p) => p.value),
        color: COMPARE_COLORS[i % COMPARE_COLORS.length],
      })),
    );
  }
}

/* ---------------- public API ---------------- */

export async function renderBacktests() {
  renderBuilder();
  await renderResults();
  renderComparison();
}

export function initBacktests() {
  $("bt-type").addEventListener("change", applyBuilderDefaults);
  $("bt-run").addEventListener("click", runBacktest);

  $("bt-entry-add").addEventListener("click", () => {
    rb.addRow($("bt-entry-rows"));
    updateCustomPreview();
  });
  $("bt-exit-add").addEventListener("click", () => {
    rb.addRow($("bt-exit-rows"));
    updateCustomPreview();
  });
  rb.initSide($("bt-entry-rows"), updateCustomPreview);
  rb.initSide($("bt-exit-rows"), updateCustomPreview);
  $("bt-entry-logic").addEventListener("change", updateCustomPreview);
  $("bt-exit-logic").addEventListener("change", updateCustomPreview);

  $("bt-add-compare").addEventListener("click", addToComparison);
  $("bt-clear-compare").addEventListener("click", () => {
    state.compareList = [];
    renderComparison();
  });
}
