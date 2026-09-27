import { $, api, money, percent, pnlClass, signedPercent, toast } from "../util.js";
import { store } from "../store.js";
import { drawEquityChart, drawPriceChart, loadChartData } from "../chart.js";

const state = { result: null, running: false };

const typeOf = (key) => store.strategyTypes.find((t) => t.key === key);

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

function renderBuilder() {
  const typeSelect = $("bt-type");
  if (typeSelect.options.length !== store.strategyTypes.length) {
    typeSelect.innerHTML = store.strategyTypes.map((t) => `<option value="${t.key}">${t.label}</option>`).join("");
    renderTypeFields();
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
    const result = await api("/backtests/run", {
      method: "POST",
      body: JSON.stringify({
        symbol: $("bt-symbol").value,
        type: $("bt-type").value,
        params: readParams(),
        quantity,
        initial_capital: initialCapital,
      }),
    });
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

/* ---------------- public API ---------------- */

export async function renderBacktests() {
  renderBuilder();
  await renderResults();
}

export function initBacktests() {
  $("bt-type").addEventListener("change", renderTypeFields);
  $("bt-run").addEventListener("click", runBacktest);
}
