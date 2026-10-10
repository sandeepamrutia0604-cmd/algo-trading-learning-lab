import { $, api, money, percent, pnlClass, signedMoney, signedPercent, toast } from "../util.js";
import { store } from "../store.js";
import { SERIES_COLORS, drawEquityChart, drawMultiLineChart, drawPriceChart, loadChartData } from "../chart.js";
import * as rb from "../rulebuilder.js";
import { initMonteCarlo, showMonteCarlo } from "./montecarlo.js";
import { downloadCsv } from "../csv.js";
import { describeExitLevels, parseExitLevels } from "../exitlevels.js";

const MAX_COMPARE = 6;

const state = { result: null, request: null, running: false, compareList: [], ranges: {}, saved: [] };

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
  const benchSelect = $("bt-bench");
  if (benchSelect.options.length !== store.stocks.length + 1) {
    const wanted = benchSelect.value || (store.stocks.some((s) => s.symbol === "NSE500") ? "NSE500" : "");
    benchSelect.innerHTML = `<option value="">(nothing)</option>` + store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}</option>`).join("");
    benchSelect.value = store.stocks.some((s) => s.symbol === wanted) ? wanted : "";
  }
}

/* ---------------- date range ---------------- */

/** First and last stored date for a stock (backtests replay the whole history), cached per symbol. */
async function historyRange(symbol) {
  if (!state.ranges[symbol]) {
    const prices = await api(`/stocks/${symbol}/prices?full=true`);
    state.ranges[symbol] = prices.length ? { dates: prices.map((p) => p.date), first: prices[0].date, last: prices[prices.length - 1].date } : { dates: [], first: null, last: null };
  }
  return state.ranges[symbol];
}

async function refreshRange({ clear = false } = {}) {
  const symbol = $("bt-symbol").value;
  if (!symbol) return;
  let range;
  try {
    delete state.ranges[symbol]; // re-read: the stock may have been re-imported or regenerated since
    range = await historyRange(symbol);
  } catch (err) {
    return;
  }
  if ($("bt-symbol").value !== symbol) return; // the selection moved on while loading
  for (const id of ["bt-from", "bt-to"]) {
    $(id).min = range.first || "";
    $(id).max = range.last || "";
    if (clear) $(id).value = "";
  }
  $("bt-range-hint").textContent = range.first
    ? `${symbol} has ${range.dates.length.toLocaleString("en-IN")} stored trading days, ${range.first} to ${range.last}. Leave both dates empty to use all of it.`
    : `${symbol} has no stored price history.`;
}

async function applyPreset(kind) {
  const range = await historyRange($("bt-symbol").value);
  if (!range.dates.length) return;
  const middle = Math.floor(range.dates.length / 2);
  const [from, to] = { all: ["", ""], first: [range.first, range.dates[middle - 1]], second: [range.dates[middle], range.last] }[kind];
  $("bt-from").value = from;
  $("bt-to").value = to;
}

const isPartial = (r) => {
  const range = state.ranges[r.symbol];
  return Boolean(range && range.first && (r.period_start !== range.first || r.period_end !== range.last));
};

/* ---------------- run ---------------- */

async function runBacktest() {
  const quantity = parseInt($("bt-qty").value, 10);
  const initialCapital = parseFloat($("bt-capital").value);
  if (!(quantity >= 1)) return toast("Shares per trade must be at least 1", true);
  if (!(initialCapital > 0)) return toast("Initial capital must be greater than zero", true);

  const from = $("bt-from").value;
  const to = $("bt-to").value;
  if (from && to && from > to) return toast("The From date must be on or before the To date", true);
  const dates = { ...(from ? { start_date: from } : {}), ...(to ? { end_date: to } : {}) };

  const riskFree = parseFloat($("bt-rf").value);
  if (!(riskFree >= 0 && riskFree <= 30)) return toast("The risk-free rate must be between 0 and 30", true);
  const levels = parseExitLevels($("bt-sl").value, $("bt-tp").value);
  if (levels.error) return toast(levels.error, true);
  const extra = { risk_free_pct: riskFree, ...($("bt-bench").value ? { benchmark: $("bt-bench").value } : {}), ...levels.values };

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
          fill_mode: $("bt-fill").value,
          ...dates,
          ...extra,
        }
      : { symbol: $("bt-symbol").value, type: $("bt-type").value, params: readParams(), quantity, initial_capital: initialCapital, fill_mode: $("bt-fill").value, ...dates, ...extra };
    const result = await api("/backtests/run", { method: "POST", body: JSON.stringify(body) });
    await historyRange(result.symbol).catch(() => {}); // so the results can tell a partial period from the whole history
    state.result = result;
    state.request = body;
    await renderResults();
    return result;
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
  if (r.costs_applied) tiles.push(["Charges paid", money(r.total_fees), "down"], ["Slippage cost", money(r.slippage_cost), "down"]);
  $("bt-metrics").innerHTML = tiles.map(([label, value, cls]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
}

const ratio = (value) => (value === null || value === undefined ? "n/a" : value.toFixed(2));
const maybe = (value, format) => (value === null || value === undefined ? "n/a" : format(value));
const tone = (value) => (value === null || value === undefined ? "" : pnlClass(value));

/** The numbers beyond the headline return: see engine/metrics.py and the glossary under the panel. */
function renderMore(r) {
  const panel = $("bt-more-panel");
  const x = r.metrics;
  panel.hidden = !x; // a result saved before these existed has none
  if (!x) return;
  const ts = x.trade_stats;
  const tiles = (rows) => rows.map(([label, value, cls = ""]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
  $("bt-more-intro").textContent =
    `Worked out from ${x.trading_days.toLocaleString("en-IN")} trading days (${x.years.toFixed(1)} years) of the account's daily value` +
    (x.risk_free_pct ? `, with a ${x.risk_free_pct}% a year risk-free rate for Sharpe, Sortino and alpha` : ", with a 0% risk-free rate (as on the Performance page)") +
    ". Short or quiet backtests make ratios like these unreliable, so read them as clues.";

  $("bt-m-risk").innerHTML = tiles([
    ["Annual growth (CAGR)", maybe(x.cagr_pct, signedPercent), tone(x.cagr_pct)],
    ["Volatility (a year)", maybe(x.volatility_pct, percent)],
    ["Sharpe ratio", ratio(x.sharpe), tone(x.sharpe)],
    ["Sortino ratio", ratio(x.sortino), tone(x.sortino)],
    ["Calmar ratio", ratio(x.calmar), tone(x.calmar)],
    ["Longest time under water", `${x.longest_drawdown_days.toLocaleString("en-IN")} days`],
    ["Time in the market", `${percent(x.exposure_pct)} (${x.days_in_market.toLocaleString("en-IN")} days)`],
  ]);
  $("bt-m-trades").innerHTML = tiles([
    ["Profit factor", ratio(ts.profit_factor), ts.profit_factor === null ? "" : ts.profit_factor >= 1 ? "up" : "down"],
    ["Expectancy per trade", maybe(ts.expectancy, signedMoney), tone(ts.expectancy)],
    ["Average win", maybe(ts.average_win, money), "up"],
    ["Average loss", maybe(ts.average_loss, money), "down"],
    ["Payoff ratio (win ÷ loss)", ratio(ts.payoff_ratio)],
    ["Best trade", maybe(ts.best_trade, signedMoney), tone(ts.best_trade)],
    ["Worst trade", maybe(ts.worst_trade, signedMoney), tone(ts.worst_trade)],
    ["Longest losing streak", `${ts.max_consecutive_losses} trade${ts.max_consecutive_losses === 1 ? "" : "s"}`],
    ["Average time held", maybe(ts.average_holding_days, (d) => `${d.toFixed(1)} days`)],
  ]);

  const versus = [
    [`Buy & hold ${r.symbol}`, signedPercent(x.buy_hold.return_pct), tone(x.buy_hold.return_pct)],
    [x.buy_hold.excess_return_pct >= 0 ? "Beat buy & hold by" : "Trailed buy & hold by", `${Math.abs(x.buy_hold.excess_return_pct).toFixed(2)} points`, tone(x.buy_hold.excess_return_pct)],
  ];
  const b = x.benchmark;
  if (b && b.return_pct !== null) {
    versus.push(
      [`${b.symbol} over the same ${b.days.toLocaleString("en-IN")} days`, signedPercent(b.return_pct), tone(b.return_pct)],
      [b.excess_return_pct >= 0 ? `Beat ${b.symbol} by` : `Trailed ${b.symbol} by`, `${Math.abs(b.excess_return_pct).toFixed(2)} points`, tone(b.excess_return_pct)],
      [`Beta to ${b.symbol}`, ratio(b.beta)],
      ["Alpha (a year)", maybe(b.alpha_pct, signedPercent), tone(b.alpha_pct)],
      ["Correlation", ratio(b.correlation)],
    );
  } else if (b) {
    versus.push([`${b.symbol}`, `only ${b.days} shared days: too few to compare`]);
  }
  $("bt-m-versus").innerHTML = tiles(versus);
}

async function renderResults() {
  const r = state.result;
  $("bt-empty").hidden = Boolean(r);
  $("bt-results").hidden = !r;
  if (!r) return;
  showMonteCarlo(r); // a different result clears any earlier Monte Carlo analysis

  $("bt-title").textContent = `${r.type_label} on ${r.symbol}`;
  $("bt-sub").textContent =
    `${r.rule} · ${r.quantity} shares per trade · started with ${money(r.initial_capital)}` +
    ` · traded ${r.period_start} to ${r.period_end}` +
    (r.fill_mode === "next_open" ? " · every trade made at the next day's opening price" : "") +
    (r.unfilled_signal ? " · a decision on the last day had no next day to trade on, so it was not carried out" : "") +
    (r.risk_managed ? ` · sized and stop-lossed using your Risk management settings${r.volatility_stops ? " (each stop set from the stock's volatility on the day of the buy)" : ""}` : "") +
    (r.stop_loss_pct || r.take_profit_pct ? ` · order-level exits: ${describeExitLevels(r.stop_loss_pct, r.take_profit_pct)}, checked against each day's low and high` : "") +
    (r.costs_applied ? " · slippage, brokerage and taxes applied from your Trading costs settings" : "") +
    (r.skipped_buys ? ` · ${r.skipped_buys} buy signal${r.skipped_buys === 1 ? "" : "s"} skipped (insufficient cash or over a risk limit)` : "") +
    (r.stopped_out ? ` · ${r.stopped_out} position${r.stopped_out === 1 ? "" : "s"} closed by stop-loss` : "") +
    (r.take_profits ? ` · ${r.take_profits} closed by take-profit` : "");
  renderMetrics(r);
  renderMore(r);

  const everyPrice = (await loadChartData(r.symbol, [], { full: true })).prices;
  if (state.result !== r) return;
  const prices = everyPrice.filter((p) => p.date >= r.period_start && p.date <= r.period_end);
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

/** The little label after an exit date: why the trade closed, when it wasn't just the strategy's own sell signal. */
function exitChip(t) {
  if (t.exit_reason === "take_profit") return ' <span class="chip">take-profit</span>';
  if (t.exit_reason === "risk_stop") return ' <span class="chip">risk stop</span>';
  return t.stopped_out ? ' <span class="chip">stop-loss</span>' : "";
}

function exitStatus(t) {
  if (t.open) return "open";
  if (t.exit_reason === "take_profit") return "closed by take-profit";
  if (t.exit_reason === "risk_stop") return "closed by risk stop";
  return t.stopped_out ? "closed by stop-loss" : "closed";
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
        <td>${t.exit_date ? t.exit_date + exitChip(t) : "-"}</td>
        <td class="num">${t.exit_date ? money(t.exit_price) : `<span class="muted">open</span>`}</td>
        <td class="num">${t.quantity}</td>
        <td class="num ${t.pnl == null ? "" : pnlClass(t.pnl)}">${t.pnl == null ? "-" : money(t.pnl)}</td>
        <td class="num ${t.pnl_pct == null ? "" : pnlClass(t.pnl_pct)}">${t.pnl_pct == null ? "-" : percent(t.pnl_pct)}</td>
        <td class="num muted">${t.stop_pct == null ? "-" : percent(t.stop_pct)}</td>
      </tr>`,
    )
    .join("");
}

/* ---------------- CSV exports (from the result on the page: nothing is run again) ---------------- */

function exportBacktestTrades() {
  const r = state.result;
  if (!r) return toast("Run a backtest first", true);
  if (!r.trades.length) return toast("This run made no trades to export", true);
  downloadCsv(`backtest-${r.symbol}-${r.type}-trades.csv`, [
    { header: "Entry date", value: "entry_date" },
    { header: "Entry price", value: "entry_price" },
    { header: "Exit date", value: "exit_date" },
    { header: "Exit price", value: "exit_price" },
    { header: "Quantity", value: "quantity" },
    { header: "P&L", value: "pnl" },
    { header: "P&L %", value: "pnl_pct" },
    { header: "Status", value: exitStatus },
    { header: "Stop distance %", value: "stop_pct" },
  ], r.trades);
  toast(`Exported ${r.trades.length} trades`);
}

function exportBacktestEquity() {
  const r = state.result;
  if (!r) return toast("Run a backtest first", true);
  downloadCsv(`backtest-${r.symbol}-${r.type}-equity.csv`, [
    { header: "Date", value: "date" },
    { header: "Strategy value", value: "value" },
  ], r.equity_curve);
  toast("Exported the equity curve");
}

function exportSavedList() {
  if (!state.saved.length) return toast("There are no saved backtests to export", true);
  downloadCsv("saved-backtests.csv", [
    { header: "Name", value: "name" },
    { header: "Symbol", value: "symbol" },
    { header: "Strategy", value: "type_label" },
    { header: "Period start", value: "period_start" },
    { header: "Period end", value: "period_end" },
    { header: "Starting capital", value: "initial_capital" },
    { header: "Final capital", value: "final_capital" },
    { header: "Return %", value: "total_return_pct" },
    { header: "Trades", value: "total_trades" },
    { header: "Win rate %", value: "win_rate_pct" },
    { header: "Max drawdown %", value: "max_drawdown_pct" },
    { header: "Risk managed", value: "risk_managed" },
    { header: "Costs applied", value: "costs_applied" },
    { header: "Saved on", value: "created_at" },
  ], state.saved);
  toast(`Exported ${state.saved.length} saved backtests`);
}

/* ---------------- comparison ---------------- */

function addToComparison() {
  if (!state.result) return;
  if (state.compareList.length >= MAX_COMPARE) {
    toast(`You can compare up to ${MAX_COMPARE} strategies at a time. Remove one first.`, true);
    return;
  }
  const label =
    `${state.result.type_label} on ${state.result.symbol}` +
    (isPartial(state.result) ? ` (${state.result.period_start} to ${state.result.period_end})` : "") +
    (state.result.fill_mode === "next_open" ? " (next open)" : "") +
    (state.result.risk_managed ? " (risk-managed)" : "") +
    (state.result.stop_loss_pct || state.result.take_profit_pct ? ` (${describeExitLevels(state.result.stop_loss_pct, state.result.take_profit_pct)})` : "") +
    (state.result.costs_applied ? " (with costs)" : "");
  pushComparison(label, state.result);
}

function pushComparison(label, result) {
  if (state.compareList.length >= MAX_COMPARE) {
    toast(`You can compare up to ${MAX_COMPARE} strategies at a time. Remove one first.`, true);
    return;
  }
  state.compareList.push({ id: `${Date.now()}-${Math.random()}`, label, result });
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
        <td class="num">${row.result.metrics && row.result.metrics.sharpe !== null ? row.result.metrics.sharpe.toFixed(2) : "-"}</td>
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
        color: SERIES_COLORS[i % SERIES_COLORS.length],
      })),
    );
  }
}

/* ---------------- saved backtests ---------------- */

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
// The server stores UTC without a zone marker; say so, or the browser reads it as local time.
const savedOn = (iso) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

async function loadSavedList() {
  try {
    state.saved = await api("/backtests/saved");
  } catch (err) {
    toast(err.message, true);
    return;
  }
  renderSaved();
}

function renderSaved() {
  const rows = state.saved;
  $("bt-saved-n").textContent = rows.length ? `(${rows.length})` : "";
  $("bt-saved-empty").hidden = rows.length > 0;
  $("bt-saved-table").hidden = rows.length === 0;
  const body = document.querySelector("#bt-saved-table tbody");
  body.innerHTML = rows
    .map(
      (r) => `<tr>
        <td class="name" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}${r.costs_applied ? ' <span class="chip">costs</span>' : ""}${r.risk_managed ? ' <span class="chip">risk</span>' : ""}</td>
        <td class="muted">${r.period_start} to ${r.period_end}</td>
        <td class="num ${pnlClass(r.total_return_pct)}">${signedPercent(r.total_return_pct)}</td>
        <td class="num">${money(r.final_capital)}</td>
        <td class="num">${r.total_trades}</td>
        <td class="num">${percent(r.win_rate_pct)}</td>
        <td class="num ${r.max_drawdown_pct > 0 ? "down" : ""}">${percent(r.max_drawdown_pct)}</td>
        <td class="muted">${savedOn(r.created_at)}</td>
        <td class="num"><div class="row-actions">
          <button class="btn" data-saved-load="${r.id}">Load</button>
          <button class="btn" data-saved-compare="${r.id}">Compare</button>
          <button class="btn btn-sell" data-saved-delete="${r.id}">Delete</button>
        </div></td>
      </tr>`,
    )
    .join("");
  body.querySelectorAll("[data-saved-load]").forEach((b) => b.addEventListener("click", () => loadSavedRun(Number(b.dataset.savedLoad))));
  body.querySelectorAll("[data-saved-compare]").forEach((b) => b.addEventListener("click", () => compareSavedRun(Number(b.dataset.savedCompare))));
  body.querySelectorAll("[data-saved-delete]").forEach((b) => b.addEventListener("click", () => deleteSavedRun(Number(b.dataset.savedDelete))));
}

async function saveRun() {
  if (!state.result || !state.request) return;
  const button = $("bt-save");
  button.disabled = true;
  try {
    const saved = await api("/backtests/saved", { method: "POST", body: JSON.stringify({ name: $("bt-save-name").value.trim() || null, request: state.request }) });
    toast(`Saved "${saved.name}"`);
    $("bt-save-name").value = "";
    await loadSavedList();
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
  }
}

/** Put a saved run's settings back in the builder and run it again. */
async function loadSavedRun(id) {
  let saved;
  try {
    saved = await api(`/backtests/saved/${id}`);
  } catch (err) {
    toast(err.message, true);
    return loadSavedList();
  }
  const req = saved.request;
  if (!store.stocks.some((s) => s.symbol === req.symbol)) {
    return toast(`${req.symbol} no longer exists, so this run can't be repeated. You can still compare the saved result.`, true);
  }

  $("bt-type").value = req.type;
  applyBuilderDefaults();
  if (req.type === "custom") {
    renderCustomRules(req.rules);
  } else {
    for (const [name, value] of Object.entries(req.params || {})) {
      const input = $("bt-params").querySelector(`input[data-param="${name}"]`);
      if (input) input.value = value;
    }
    renderRule();
  }
  $("bt-symbol").value = req.symbol;
  $("bt-qty").value = req.quantity;
  $("bt-capital").value = req.initial_capital;
  $("bt-fill").value = req.fill_mode || "signal_close";
  updateFillHint();
  $("bt-sl").value = req.stop_loss_pct ?? "";
  $("bt-tp").value = req.take_profit_pct ?? "";
  $("bt-rf").value = req.risk_free_pct ?? 0;
  $("bt-bench").value = req.benchmark || "";
  await refreshRange(); // sets the date limits for this stock; then put the saved dates back
  $("bt-from").value = req.start_date || "";
  $("bt-to").value = req.end_date || "";
  $("bt-save-name").value = saved.name;

  const result = await runBacktest();
  if (!result) return;
  const was = saved.result;
  const same = Math.abs(result.final_capital - was.final_capital) < 0.005 && result.total_trades === was.total_trades;
  toast(
    same
      ? `Loaded "${saved.name}". Same numbers as when you saved it.`
      : `Loaded "${saved.name}", but it gives different numbers now (${signedPercent(result.total_return_pct)} vs ${signedPercent(was.total_return_pct)} when saved). The stock's data, or your risk or cost settings, have changed since.`,
    !same,
  );
  $("bt-results").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function compareSavedRun(id) {
  try {
    const saved = await api(`/backtests/saved/${id}`);
    pushComparison(saved.name, saved.result);
  } catch (err) {
    toast(err.message, true);
    loadSavedList();
  }
}

async function deleteSavedRun(id) {
  const row = state.saved.find((r) => r.id === id);
  if (!confirm(`Delete the saved backtest "${row ? row.name : id}"?`)) return;
  try {
    await api(`/backtests/saved/${id}`, { method: "DELETE" });
  } catch (err) {
    toast(err.message, true);
  }
  await loadSavedList();
}

/* ---------------- public API ---------------- */

export async function renderBacktests() {
  renderBuilder();
  refreshRange();
  loadSavedList();
  await renderResults();
  renderComparison();
}

const FILL_HINT = {
  signal_close: "Each decision is carried out at the close of the day its signal appears. That close is the very price the signal was computed from, so it assumes you could have traded on it after the fact: optimistic.",
  next_open: "Each decision (a signal, or a stop-loss) is carried out at the next trading day's opening price: the first price you could really have got. Overnight gaps now count for or against you.",
};

function updateFillHint() {
  $("bt-fill-hint").textContent = FILL_HINT[$("bt-fill").value];
}

export function initBacktests() {
  $("bt-fill").addEventListener("change", updateFillHint);
  updateFillHint();
  $("bt-type").addEventListener("change", applyBuilderDefaults);
  $("bt-run").addEventListener("click", runBacktest);
  $("bt-symbol").addEventListener("change", () => refreshRange({ clear: true }));
  $("bt-presets").querySelectorAll("[data-range]").forEach((btn) => btn.addEventListener("click", () => applyPreset(btn.dataset.range)));

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
  $("bt-save").addEventListener("click", saveRun);
  $("bt-export-trades").addEventListener("click", exportBacktestTrades);
  $("bt-export-equity").addEventListener("click", exportBacktestEquity);
  $("bt-export-saved").addEventListener("click", exportSavedList);
  initMonteCarlo(() => state.request);
  $("bt-clear-compare").addEventListener("click", () => {
    state.compareList = [];
    renderComparison();
  });
}
