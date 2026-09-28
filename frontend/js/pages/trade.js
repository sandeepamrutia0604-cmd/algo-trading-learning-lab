import { $, api, money, pnlClass, signedMoney, signedPercent, sparkline, toast } from "../util.js";
import { hooks, positionBySymbol, stockBySymbol, store } from "../store.js";
import { SMA_COLORS, drawPriceChart, loadChartData, smaOverlays } from "../chart.js";

const MODEL_INFO = {
  random_walk: "Random walk: each day's move is random noise around the Trend. Yesterday tells you nothing about tomorrow.",
  trending: "Trending: moves carry momentum, so price keeps drifting in the Trend direction. Set a non-zero Trend (negative = downtrend).",
  volatile: "Volatile: like a random walk but daily swings are about 2.5x larger. More risk, bigger surprises.",
  sideways: "Sideways: price is pulled back toward its starting price, so it oscillates in a range instead of running away.",
};
const MODEL_LABEL = { random_walk: "Random walk", trending: "Trending", volatile: "Volatile", sideways: "Sideways" };

const roundTo = (n, digits) => Number(n.toFixed(digits));
const dayChange = (s) => (s && s.previous_close ? ((s.current_price - s.previous_close) / s.previous_close) * 100 : 0);

/* ---------------- watchlist + detail ---------------- */

function renderWatchlist() {
  const list = $("t-watch");
  list.innerHTML = store.stocks
    .map((s) => {
      const change = dayChange(s);
      return `<div class="trow ${s.symbol === store.symbol ? "sel" : ""}" data-symbol="${s.symbol}">
        <div><b>${s.symbol}</b><small>${s.name}</small></div>
        ${sparkline(s.recent_closes)}
        <div class="px">${money(s.current_price)}</div>
        <div class="px ${pnlClass(change)}" style="text-align:right;font-size:12px">${signedPercent(change)}</div>
      </div>`;
    })
    .join("");
  list.querySelectorAll(".trow").forEach((row) =>
    row.addEventListener("click", () => selectSymbol(row.dataset.symbol)),
  );

  const s = stockBySymbol(store.symbol);
  const cfg = store.configs[store.symbol];
  if (!s) return;
  const change = dayChange(s);
  $("t-detail").innerHTML = `
    <h3 style="padding:0 0 6px">Selected</h3>
    <div class="big">${money(s.current_price)}</div>
    <div class="${pnlClass(change)}" style="font-size:12px;margin-bottom:8px">${signedMoney(s.current_price - (s.previous_close ?? s.current_price))} (${signedPercent(change)}) today</div>
    ${
      cfg
        ? `<div class="sumrow"><span>Model</span><span class="chip">${MODEL_LABEL[cfg.model]}</span></div>
           <div class="sumrow"><span>Volatility</span><span>${roundTo(cfg.volatility * 100, 2)}% / day</span></div>
           <div class="sumrow"><span>Trend</span><span>${roundTo(cfg.trend * 100, 2)}% / day</span></div>`
        : ""
    }`;
}

/* ---------------- order ticket ---------------- */

function ticketState() {
  const stock = stockBySymbol(store.symbol);
  const qty = parseInt($("o-qty").value, 10) || 0;
  const position = positionBySymbol(store.symbol);
  const held = position ? position.quantity : 0;
  const p = store.portfolio;
  const price = stock.current_price;
  const value = qty * price;
  const buy = store.side === "BUY";
  const maxQty = buy ? Math.floor(p.cash / price) : held;
  const positionValue = held * price;
  const after = buy ? positionValue + value : positionValue - value;
  let warning = "";
  if (qty <= 0) warning = "Enter a quantity above 0.";
  else if (buy && value > p.cash) warning = `Not enough cash: this order costs ${money(value)} but you have ${money(p.cash)}.`;
  else if (!buy && qty > held) warning = `You hold only ${held} ${stock.symbol}.`;
  return { stock, qty, price, value, buy, maxQty, after, warning, cashAfter: buy ? p.cash - value : p.cash + value, pv: p.portfolio_value };
}

function renderTicket() {
  const symbolSelect = $("o-symbol");
  if (symbolSelect.options.length !== store.stocks.length) {
    symbolSelect.innerHTML = store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}</option>`).join("");
  }
  symbolSelect.value = store.symbol;

  const t = ticketState();
  $("o-side").className = "seg" + (t.buy ? "" : " sell");
  $("o-side").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.side === store.side));
  $("o-max").textContent = `max ${t.maxQty}`;

  const row = (label, value) => `<div class="sumrow"><span>${label}</span><span>${value}</span></div>`;
  $("o-summary").innerHTML =
    row("Market price", money(t.price)) +
    row("Order value", money(t.value)) +
    row(t.buy ? "Cash after" : "Cash after sale", money(t.cashAfter)) +
    row("Position after", `${money(t.after)} (${t.pv ? ((t.after / t.pv) * 100).toFixed(1) : "0.0"}% of portfolio)`);

  const warn = $("o-warn");
  warn.hidden = !t.warning || t.qty <= 0;
  warn.textContent = t.warning;

  const submit = $("o-submit");
  submit.className = "btn big " + (t.buy ? "btn-buy" : "btn-sell");
  submit.textContent = `${t.buy ? "Buy" : "Sell"} ${t.qty > 0 ? t.qty : ""} ${t.stock.symbol}`.replace("  ", " ");
  submit.disabled = Boolean(t.warning);
}

async function placeOrder(side, symbol, quantity) {
  try {
    await api(`/orders/${side.toLowerCase()}`, { method: "POST", body: JSON.stringify({ symbol, quantity }) });
    toast(`${side} ${quantity} ${symbol} executed`);
    await hooks.refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------- bottom panel ---------------- */

function switchTab(name) {
  document.querySelectorAll("#t-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  for (const pane of ["positions", "trades", "market", "risk"]) $(`tab-${pane}`).hidden = pane !== name;
}

function renderPositions() {
  const rows = store.positions;
  $("tab-pos-n").textContent = rows.length;
  $("positions-empty").hidden = rows.length > 0;
  const tbody = document.querySelector("#positions-table tbody");
  tbody.innerHTML = rows
    .map(
      (p) => `<tr>
        <td><span class="sym-link" data-symbol="${p.symbol}">${p.symbol}</span></td>
        <td class="num">${p.quantity}</td>
        <td class="num">${money(p.average_price)}</td>
        <td class="num">${money(p.current_price)}</td>
        <td class="num">${money(p.market_value)}</td>
        <td class="num ${pnlClass(p.unrealized_pnl)}">${signedMoney(p.unrealized_pnl)}</td>
        <td class="num ${pnlClass(p.day_pnl)}">${signedMoney(p.day_pnl)}</td>
        <td><div class="row-actions">
          <button class="btn" data-add="${p.symbol}">+ Add</button>
          <button class="btn btn-sell" data-exit="${p.symbol}">Exit</button>
        </div></td>
      </tr>`,
    )
    .join("");

  tbody.querySelectorAll(".sym-link").forEach((el) => el.addEventListener("click", () => selectSymbol(el.dataset.symbol)));
  tbody.querySelectorAll("[data-add]").forEach((btn) =>
    btn.addEventListener("click", () => {
      store.side = "BUY";
      selectSymbol(btn.dataset.add);
      $("o-qty").focus();
    }),
  );
  tbody.querySelectorAll("[data-exit]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const p = positionBySymbol(btn.dataset.exit);
      if (p && confirm(`Sell all ${p.quantity} ${p.symbol} at the market price?`)) placeOrder("SELL", p.symbol, p.quantity);
    }),
  );
}

function renderTrades() {
  const trades = store.trades;
  $("tab-trd-n").textContent = trades.length;
  $("trades-empty").hidden = trades.length > 0;
  document.querySelector("#trades-table tbody").innerHTML = trades
    .slice(0, 100)
    .map((t) => {
      const pnl =
        t.realized_pnl === null || t.realized_pnl === undefined
          ? "-"
          : `<span class="${pnlClass(t.realized_pnl)}">${signedMoney(t.realized_pnl)}</span>`;
      return `<tr>
        <td>${t.market_date || "-"}</td>
        <td>${new Date(t.timestamp).toLocaleString("en-IN")}</td>
        <td>${t.symbol}</td>
        <td class="side-${t.side.toLowerCase()}">${t.side}</td>
        <td class="num">${t.quantity}</td>
        <td class="num">${money(t.price)}</td>
        <td class="num">${pnl}</td>
        <td class="muted">${t.source}</td>
      </tr>`;
    })
    .join("");
}

function renderSettings() {
  $("s-symbol").textContent = store.symbol;
  const cfg = store.configs[store.symbol];
  if (!cfg) return;
  $("m-model").value = cfg.model;
  $("m-vol").value = roundTo(cfg.volatility * 100, 3);
  $("m-trend").value = roundTo(cfg.trend * 100, 3);
  $("m-model-desc").textContent = MODEL_INFO[cfg.model];
}

async function applyConfig() {
  const body = {
    model: $("m-model").value,
    volatility: parseFloat($("m-vol").value) / 100,
    trend: parseFloat($("m-trend").value) / 100,
  };
  try {
    const saved = await api(`/market/config/${store.symbol}`, { method: "PUT", body: JSON.stringify(body) });
    store.configs[saved.symbol] = saved;
    renderSettings();
    renderWatchlist();
    toast(`${saved.symbol} set to ${MODEL_LABEL[saved.model]}. Applies to new days (Advance or Regenerate).`);
  } catch (err) {
    toast(err.message, true);
  }
}

async function regenerateHistory() {
  const days = parseInt($("m-days").value, 10);
  if (!days || days < 2 || days > 1000) {
    toast("History days must be between 2 and 1000", true);
    return;
  }
  try {
    await api("/market/generate", { method: "POST", body: JSON.stringify({ days }) });
    toast(`Generated ${days} days of new history for all stocks`);
    await hooks.refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

function riskExample() {
  const risk = parseFloat($("rk-risk").value) || 0;
  const stop = parseFloat($("rk-stop").value) || 0;
  const pv = store.portfolio?.portfolio_value || 0;
  const example = $("rk-example");
  if (!risk || !stop || !pv) {
    example.textContent = "";
    return;
  }
  const riskAmount = (pv * risk) / 100;
  const entryPrice = 100;
  const riskPerShare = (entryPrice * stop) / 100;
  const qty = Math.floor(riskAmount / riskPerShare);
  example.textContent = `Example: ${money(pv)} portfolio × ${risk}% risk = ${money(riskAmount)} max risk per trade. A ₹100 entry with a ${stop}% stop risks ${money(riskPerShare)} per share, so a signal would size to ${qty} shares.`;
}

function renderRisk() {
  const r = store.riskSettings;
  if (!r) return;
  $("rk-enabled").checked = r.enabled;
  $("rk-risk").value = r.max_risk_per_trade_pct;
  $("rk-stop").value = r.stop_loss_pct;
  $("rk-positions").value = r.max_open_positions;
  $("rk-allocation").value = r.max_allocation_pct;
  riskExample();
}

async function applyRiskSettings() {
  const body = {
    enabled: $("rk-enabled").checked,
    max_risk_per_trade_pct: parseFloat($("rk-risk").value),
    stop_loss_pct: parseFloat($("rk-stop").value),
    max_open_positions: parseInt($("rk-positions").value, 10),
    max_allocation_pct: parseFloat($("rk-allocation").value),
  };
  try {
    store.riskSettings = await api("/risk-settings", { method: "PATCH", body: JSON.stringify(body) });
    toast(store.riskSettings.enabled ? "Risk management is on." : "Risk management is off.");
    renderRisk();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------- chart ---------------- */

function chartOptions() {
  const smas = [];
  for (const kind of ["fast", "slow"]) {
    const value = parseInt($(`ind-${kind}`).value, 10);
    if ($(`ind-${kind}-on`).checked && value >= 2 && value <= 500) smas.push({ period: value, color: SMA_COLORS[kind] });
  }
  return { smas, showTrades: $("ind-trades").checked, showSignals: $("ind-signals").checked };
}

async function renderChart() {
  const chartEl = $("chart");
  if (typeof Plotly === "undefined") {
    chartEl.textContent = "Chart library failed to load (check your internet connection).";
    return;
  }
  const symbol = store.symbol;
  const { smas, showTrades, showSignals } = chartOptions();
  const [{ prices, indicators }, signals] = await Promise.all([
    loadChartData(symbol, smas),
    showSignals ? api(`/signals?symbol=${symbol}`) : [],
  ]);
  if (symbol !== store.symbol) return; // selection changed while loading

  $("c-sym").textContent = symbol;
  const last = prices[prices.length - 1];
  const prev = prices[prices.length - 2];
  if (last) {
    const change = prev ? ((last.close - prev.close) / prev.close) * 100 : 0;
    $("c-ohlc").innerHTML = `O ${last.open.toFixed(2)} &nbsp;H ${last.high.toFixed(2)} &nbsp;L ${last.low.toFixed(2)} &nbsp;C ${last.close.toFixed(2)} &nbsp;<span class="${pnlClass(change)}">${signedPercent(change)}</span>`;
  } else {
    $("c-ohlc").textContent = "No price history yet. Use Regenerate history in Market settings.";
  }

  drawPriceChart(chartEl, { symbol, prices, overlays: smaOverlays(smas, indicators), trades: showTrades ? store.trades : [], signals });
}

/* ---------------- public API ---------------- */

export function selectSymbol(symbol) {
  if (!stockBySymbol(symbol)) return;
  store.symbol = symbol;
  renderWatchlist();
  renderTicket();
  renderSettings();
  renderChart();
}

export async function renderTrade() {
  renderWatchlist();
  renderTicket();
  renderPositions();
  renderTrades();
  renderSettings();
  renderRisk();
  await renderChart();
}

export function initTrade() {
  $("o-side").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-side]");
    if (!btn) return;
    store.side = btn.dataset.side;
    renderTicket();
  });
  $("o-symbol").addEventListener("change", (e) => selectSymbol(e.target.value));
  $("o-qty").addEventListener("input", renderTicket);
  $("o-max").addEventListener("click", () => {
    $("o-qty").value = Math.max(ticketState().maxQty, 1);
    renderTicket();
  });
  $("o-submit").addEventListener("click", () => {
    const t = ticketState();
    if (!t.warning) placeOrder(store.side, t.stock.symbol, t.qty);
  });

  for (const id of ["ind-fast-on", "ind-fast", "ind-slow-on", "ind-slow", "ind-trades", "ind-signals"]) $(id).addEventListener("change", renderChart);

  $("t-tabs").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-tab]");
    if (btn) switchTab(btn.dataset.tab);
  });

  $("m-apply").addEventListener("click", applyConfig);
  $("m-regen").addEventListener("click", regenerateHistory);
  $("m-model").addEventListener("change", (e) => {
    $("m-model-desc").textContent = MODEL_INFO[e.target.value];
    if (e.target.value === "trending" && parseFloat($("m-trend").value) === 0) $("m-trend").value = 0.3;
  });

  $("rk-apply").addEventListener("click", applyRiskSettings);
  for (const id of ["rk-risk", "rk-stop"]) $(id).addEventListener("input", riskExample);
}
