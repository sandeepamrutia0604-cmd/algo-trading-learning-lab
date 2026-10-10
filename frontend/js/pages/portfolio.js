// The Portfolio test page: one strategy traded across several stocks from one account (server side:
// backend/app/engine/portfolio_backtest.py). This file gathers the settings, shows the result and keeps saved runs;
// the small pure helpers are in ../portfolio.js.
import { $, api, money, percent, pnlClass, signedMoney, signedPercent, toast } from "../util.js";
import { store } from "../store.js";
import { drawEquityChart } from "../chart.js";
import { downloadCsv } from "../csv.js";
import { describeExitLevels, parseExitLevels } from "../exitlevels.js";
import { createStrategyBuilder } from "../strategybuilder.js";
import { basketLabel, checkSelection, inOrder, keepExisting, skipText } from "../portfolio.js";

const builder = createStrategyBuilder("pt");
const state = { result: null, request: null, running: false, picked: [], pickedTouched: false, stockKey: "", saved: [] };

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const savedOn = (iso) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const ratio = (value) => (value === null || value === undefined ? "n/a" : value.toFixed(2));
const maybe = (value, format) => (value === null || value === undefined ? "n/a" : format(value));
const tone = (value) => (value === null || value === undefined ? "" : pnlClass(value));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

/* ---------------- builder ---------------- */

function renderStocks() {
  const symbols = store.stocks.map((s) => s.symbol);
  const key = JSON.stringify(symbols);
  if (key !== state.stockKey) {
    state.stockKey = key;
    // Until you choose, start with the first three; afterwards keep your picks that still exist.
    state.picked = state.pickedTouched ? keepExisting(state.picked, symbols) : symbols.slice(0, 3);
    $("pt-stocks").innerHTML = store.stocks
      .map((s) => `<label class="pf-stock" title="${escapeHtml(s.name)}"><input type="checkbox" value="${s.symbol}" /> ${s.symbol}</label>`)
      .join("");
    $("pt-bench").innerHTML = `<option value="">(nothing)</option>` + symbols.map((s) => `<option value="${s}">${s}</option>`).join("");
    if (symbols.includes("NSE500")) $("pt-bench").value = "NSE500";
  }
  $("pt-stocks").querySelectorAll("input").forEach((box) => (box.checked = state.picked.includes(box.value)));
  const n = state.picked.length;
  $("pt-picked-n").textContent = n ? `(${n} chosen)` : "";
}

function setPicked(symbols) {
  state.picked = symbols;
  state.pickedTouched = true;
  renderStocks();
}

/* ---------------- run ---------------- */

function readRequest() {
  const quantity = parseInt($("pt-qty").value, 10);
  const initialCapital = parseFloat($("pt-capital").value);
  if (!(quantity >= 1)) return { error: "Shares per trade must be at least 1" };
  if (!(initialCapital > 0)) return { error: "Initial capital must be greater than zero" };
  const problem = checkSelection(state.picked);
  if (problem) return { error: problem };
  const from = $("pt-from").value;
  const to = $("pt-to").value;
  if (from && to && from > to) return { error: "The From date must be on or before the To date" };
  const riskFree = parseFloat($("pt-rf").value);
  if (!(riskFree >= 0 && riskFree <= 30)) return { error: "The risk-free rate must be between 0 and 30" };
  const levels = parseExitLevels($("pt-sl").value, $("pt-tp").value);
  if (levels.error) return { error: levels.error };
  return {
    body: {
      symbols: [...state.picked],
      ...builder.read(),
      quantity,
      initial_capital: initialCapital,
      fill_mode: $("pt-fill").value,
      ...(from ? { start_date: from } : {}),
      ...(to ? { end_date: to } : {}),
      risk_free_pct: riskFree,
      ...($("pt-bench").value ? { benchmark: $("pt-bench").value } : {}),
      ...levels.values,
    },
  };
}

async function runPortfolio() {
  const { body, error } = readRequest();
  if (error) return toast(error, true);
  state.running = true;
  $("pt-run").disabled = true;
  $("pt-run").textContent = "Running...";
  try {
    const result = await api("/portfolio-backtests/run", { method: "POST", body: JSON.stringify(body) });
    state.result = result;
    state.request = body;
    renderResults();
    return result;
  } catch (err) {
    toast(err.message, true);
  } finally {
    state.running = false;
    $("pt-run").disabled = false;
    $("pt-run").textContent = "Run portfolio backtest";
  }
}

/* ---------------- results ---------------- */

function renderMetrics(r) {
  const tiles = [
    ["Final capital", money(r.final_capital), ""],
    ["Total return", signedPercent(r.total_return_pct), pnlClass(r.total_return_pct)],
    ["Total trades", r.total_trades, ""],
    ["Winning", r.winning_trades, r.winning_trades ? "up" : ""],
    ["Losing", r.losing_trades, r.losing_trades ? "down" : ""],
    ["Win rate", percent(r.win_rate_pct), ""],
    ["Max drawdown", percent(r.max_drawdown_pct), r.max_drawdown_pct > 0 ? "down" : ""],
    ["Most held at once", `${plural(r.peak_positions, "stock")}`, ""],
  ];
  if (r.costs_applied) tiles.push(["Charges paid", money(r.total_fees), "down"], ["Slippage cost", money(r.slippage_cost), "down"]);
  $("pt-metrics").innerHTML = tiles.map(([label, value, cls]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
}

function renderMore(r) {
  const x = r.metrics;
  const ts = x.trade_stats;
  const tiles = (rows) => rows.map(([label, value, cls = ""]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
  $("pt-more-intro").textContent =
    `Worked out from ${x.trading_days.toLocaleString("en-IN")} trading days (${x.years.toFixed(1)} years) of the account's daily value` +
    (x.risk_free_pct ? `, with a ${x.risk_free_pct}% a year risk-free rate for Sharpe, Sortino and alpha` : ", with a 0% risk-free rate") +
    ". Short or quiet backtests make ratios like these unreliable, so read them as clues.";
  $("pt-m-risk").innerHTML = tiles([
    ["Annual growth (CAGR)", maybe(x.cagr_pct, signedPercent), tone(x.cagr_pct)],
    ["Volatility (a year)", maybe(x.volatility_pct, percent)],
    ["Sharpe ratio", ratio(x.sharpe), tone(x.sharpe)],
    ["Sortino ratio", ratio(x.sortino), tone(x.sortino)],
    ["Calmar ratio", ratio(x.calmar), tone(x.calmar)],
    ["Longest time under water", `${x.longest_drawdown_days.toLocaleString("en-IN")} days`],
    ["Time in the market", `${percent(x.exposure_pct)} (${x.days_in_market.toLocaleString("en-IN")} days)`],
  ]);
  $("pt-m-trades").innerHTML = tiles([
    ["Profit factor", ratio(ts.profit_factor), ts.profit_factor === null ? "" : ts.profit_factor >= 1 ? "up" : "down"],
    ["Expectancy per trade", maybe(ts.expectancy, signedMoney), tone(ts.expectancy)],
    ["Average win", maybe(ts.average_win, money), "up"],
    ["Average loss", maybe(ts.average_loss, money), "down"],
    ["Payoff ratio (win ÷ loss)", ratio(ts.payoff_ratio)],
    ["Best trade", maybe(ts.best_trade, signedMoney), tone(ts.best_trade)],
    ["Worst trade", maybe(ts.worst_trade, signedMoney), tone(ts.worst_trade)],
    ["Longest losing streak", plural(ts.max_consecutive_losses, "trade")],
    ["Average time held", maybe(ts.average_holding_days, (d) => `${d.toFixed(1)} days`)],
  ]);
  const versus = [
    ["Holding all equally", signedPercent(x.buy_hold.return_pct), tone(x.buy_hold.return_pct)],
    [x.buy_hold.excess_return_pct >= 0 ? "Beat holding them by" : "Trailed holding them by", `${Math.abs(x.buy_hold.excess_return_pct).toFixed(2)} points`, tone(x.buy_hold.excess_return_pct)],
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
    versus.push([b.symbol, `only ${b.days} shared days: too few to compare`]);
  }
  $("pt-m-versus").innerHTML = tiles(versus);
}

function renderStockTable(r) {
  document.querySelector("#pt-stock-table tbody").innerHTML = r.per_stock
    .map(
      (s) => `<tr>
        <td><b>${s.symbol}</b></td>
        <td class="num">${s.trades}</td>
        <td class="num">${s.trades ? percent(s.win_rate_pct) : "-"}</td>
        <td class="num ${pnlClass(s.realized_pnl)}">${signedMoney(s.realized_pnl)}</td>
        <td class="num ${pnlClass(s.open_pnl)}">${s.open_pnl ? signedMoney(s.open_pnl) : "-"}</td>
        <td class="num ${pnlClass(s.total_pnl)}">${signedMoney(s.total_pnl)}</td>
        <td class="num ${pnlClass(s.contribution_pct)}">${signedPercent(s.contribution_pct)}</td>
        <td class="num ${pnlClass(s.stock_return_pct)}">${signedPercent(s.stock_return_pct)}</td>
      </tr>`,
    )
    .join("");
}

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
  const rows = inOrder(r.trades);
  $("pt-trades-empty").hidden = rows.length > 0;
  document.querySelector("#pt-trades-table tbody").innerHTML = rows
    .map(
      (t) => `<tr>
        <td><b>${t.symbol}</b></td>
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

function renderResults() {
  const r = state.result;
  $("pt-empty").hidden = Boolean(r);
  $("pt-results").hidden = !r;
  if (!r) return;
  $("pt-title").textContent = `${r.type_label} on ${plural(r.symbols.length, "stock")}`;
  const skipped = skipText(r.skipped_by_reason);
  $("pt-sub").textContent =
    `${basketLabel(r.symbols, 8)} · ${r.rule} · started with ${money(r.initial_capital)} · traded ${r.period_start} to ${r.period_end}` +
    (r.fill_mode === "next_open" ? " · every trade made at the next day's opening price" : "") +
    (r.unfilled_signals ? ` · ${plural(r.unfilled_signals, "decision")} on the last days had no next day to trade on` : "") +
    (r.risk_managed
      ? ` · sized and stop-lossed using your Risk management settings${r.max_open_positions ? `, at most ${plural(r.max_open_positions, "position")} open` : ""}`
      : " · Risk management is off, so no limit on open positions or share of the account in one stock") +
    (r.stop_loss_pct || r.take_profit_pct ? ` · order-level exits: ${describeExitLevels(r.stop_loss_pct, r.take_profit_pct)}` : "") +
    (r.costs_applied ? " · slippage, brokerage and taxes applied from your Trading costs settings" : "") +
    (skipped ? ` · buy signals skipped: ${skipped}` : "") +
    (r.stopped_out ? ` · ${plural(r.stopped_out, "position")} closed by stop-loss` : "") +
    (r.take_profits ? ` · ${r.take_profits} closed by take-profit` : "");
  renderMetrics(r);
  renderMore(r);
  renderStockTable(r);
  drawEquityChart($("pt-equity"), {
    dates: r.equity_curve.map((p) => p.date),
    values: r.equity_curve.map((p) => p.value),
    baseline: r.baseline_curve.map((p) => p.value),
    valueLabel: "Your account",
    baselineLabel: "Holding all equally",
  });
  renderTrades(r);
}

/* ---------------- CSV exports (from the result on the page: nothing is run again) ---------------- */

function exportTrades() {
  const r = state.result;
  if (!r) return toast("Run a portfolio backtest first", true);
  if (!r.trades.length) return toast("This run made no trades to export", true);
  downloadCsv(`portfolio-backtest-${r.type}-trades.csv`, [
    { header: "Stock", value: "symbol" },
    { header: "Entry date", value: "entry_date" },
    { header: "Entry price", value: "entry_price" },
    { header: "Exit date", value: "exit_date" },
    { header: "Exit price", value: "exit_price" },
    { header: "Quantity", value: "quantity" },
    { header: "P&L", value: "pnl" },
    { header: "P&L %", value: "pnl_pct" },
    { header: "Status", value: exitStatus },
    { header: "Stop distance %", value: "stop_pct" },
  ], inOrder(r.trades));
  toast(`Exported ${r.trades.length} trades`);
}

function exportEquity() {
  const r = state.result;
  if (!r) return toast("Run a portfolio backtest first", true);
  const baseline = new Map(r.baseline_curve.map((p) => [p.date, p.value]));
  downloadCsv(`portfolio-backtest-${r.type}-equity.csv`, [
    { header: "Date", value: "date" },
    { header: "Account value", value: "value" },
    { header: "Holding all equally", value: (p) => baseline.get(p.date) },
  ], r.equity_curve);
  toast("Exported the equity curve");
}

/* ---------------- saved runs ---------------- */

async function loadSavedList() {
  try {
    state.saved = await api("/portfolio-backtests/saved");
  } catch (err) {
    toast(err.message, true);
    return;
  }
  renderSaved();
}

function renderSaved() {
  const rows = state.saved;
  $("pt-saved-n").textContent = rows.length ? `(${rows.length})` : "";
  $("pt-saved-empty").hidden = rows.length > 0;
  $("pt-saved-table").hidden = rows.length === 0;
  const body = document.querySelector("#pt-saved-table tbody");
  body.innerHTML = rows
    .map(
      (r) => `<tr>
        <td class="name" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}</td>
        <td class="muted">${r.period_start} to ${r.period_end}</td>
        <td class="num ${pnlClass(r.total_return_pct)}">${signedPercent(r.total_return_pct)}</td>
        <td class="num">${money(r.final_capital)}</td>
        <td class="num">${r.total_trades}</td>
        <td class="num">${percent(r.win_rate_pct)}</td>
        <td class="num ${r.max_drawdown_pct > 0 ? "down" : ""}">${percent(r.max_drawdown_pct)}</td>
        <td class="muted">${savedOn(r.created_at)}</td>
        <td class="num"><div class="row-actions">
          <button class="btn" data-saved-load="${r.id}">Load</button>
          <button class="btn btn-sell" data-saved-delete="${r.id}">Delete</button>
        </div></td>
      </tr>`,
    )
    .join("");
  body.querySelectorAll("[data-saved-load]").forEach((b) => b.addEventListener("click", () => loadSavedRun(Number(b.dataset.savedLoad))));
  body.querySelectorAll("[data-saved-delete]").forEach((b) => b.addEventListener("click", () => deleteSavedRun(Number(b.dataset.savedDelete))));
}

async function saveRun() {
  if (!state.result || !state.request) return;
  const button = $("pt-save");
  button.disabled = true;
  try {
    const saved = await api("/portfolio-backtests/saved", { method: "POST", body: JSON.stringify({ name: $("pt-save-name").value.trim() || null, request: state.request }) });
    toast(`Saved "${saved.name}"`);
    $("pt-save-name").value = "";
    await loadSavedList();
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadSavedRun(id) {
  let saved;
  try {
    saved = await api(`/portfolio-backtests/saved/${id}`);
  } catch (err) {
    toast(err.message, true);
    return loadSavedList();
  }
  const req = saved.request;
  const missing = req.symbols.filter((s) => !store.stocks.some((x) => x.symbol === s));
  if (missing.length) return toast(`${missing.join(", ")} no longer exist${missing.length === 1 ? "s" : ""}, so this run can't be repeated.`, true);

  builder.write(req);
  setPicked(req.symbols);
  $("pt-qty").value = req.quantity;
  $("pt-capital").value = req.initial_capital;
  $("pt-fill").value = req.fill_mode || "signal_close";
  $("pt-sl").value = req.stop_loss_pct ?? "";
  $("pt-tp").value = req.take_profit_pct ?? "";
  $("pt-rf").value = req.risk_free_pct ?? 0;
  $("pt-bench").value = req.benchmark || "";
  $("pt-from").value = req.start_date || "";
  $("pt-to").value = req.end_date || "";
  $("pt-save-name").value = saved.name;

  const result = await runPortfolio();
  if (!result) return;
  const was = saved.result;
  const same = Math.abs(result.final_capital - was.final_capital) < 0.005 && result.total_trades === was.total_trades;
  toast(
    same
      ? `Loaded "${saved.name}". Same numbers as when you saved it.`
      : `Loaded "${saved.name}", but it gives different numbers now (${signedPercent(result.total_return_pct)} vs ${signedPercent(was.total_return_pct)} when saved). A stock's data, or your risk or cost settings, have changed since.`,
    !same,
  );
  $("pt-results").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function deleteSavedRun(id) {
  const row = state.saved.find((r) => r.id === id);
  if (!confirm(`Delete the saved portfolio backtest "${row ? row.name : id}"?`)) return;
  try {
    await api(`/portfolio-backtests/saved/${id}`, { method: "DELETE" });
  } catch (err) {
    toast(err.message, true);
  }
  await loadSavedList();
}

/* ---------------- public API ---------------- */

export async function renderPortfolioTest() {
  builder.render();
  renderStocks();
  loadSavedList();
  renderResults();
}

export function initPortfolioTest() {
  builder.init();
  $("pt-stocks").addEventListener("change", (event) => {
    if (event.target.type !== "checkbox") return;
    setPicked(store.stocks.map((s) => s.symbol).filter((s) => (s === event.target.value ? event.target.checked : state.picked.includes(s))));
  });
  $("pt-all").addEventListener("click", () => setPicked(store.stocks.map((s) => s.symbol).slice(0, 20)));
  $("pt-none").addEventListener("click", () => setPicked([]));
  $("pt-run").addEventListener("click", runPortfolio);
  $("pt-save").addEventListener("click", saveRun);
  $("pt-export-trades").addEventListener("click", exportTrades);
  $("pt-export-equity").addEventListener("click", exportEquity);
}
