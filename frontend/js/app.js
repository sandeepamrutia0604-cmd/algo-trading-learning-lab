const money = (n) => {
  const rounded = Math.round(Number(n) * 100) / 100;
  const text = Math.abs(rounded).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (rounded < 0 ? "-₹" : "₹") + text;
};

const percent = (n) => {
  const rounded = Math.round(Number(n) * 100) / 100;
  return (rounded === 0 ? 0 : rounded).toFixed(2) + "%";
};

const pnlClass = (n) => (n > 0 ? "positive" : n < 0 ? "negative" : "");

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "toast" + (isError ? " error" : "");
  toast.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => (toast.hidden = true), 3500);
}

async function api(path, options) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

async function checkHealth() {
  const statusEl = document.getElementById("status");
  try {
    const data = await api("/health");
    statusEl.textContent = `Backend ${data.status.toUpperCase()}`;
    statusEl.className = "ok";
  } catch (err) {
    statusEl.textContent = "Backend unreachable";
    statusEl.className = "error";
  }
}

async function loadWallet() {
  const w = await api("/portfolio");
  document.getElementById("w-cash").textContent = money(w.cash);
  document.getElementById("w-invested").textContent = money(w.invested);
  document.getElementById("w-portfolio-value").textContent = money(w.portfolio_value);

  const unrealizedEl = document.getElementById("w-unrealized");
  unrealizedEl.textContent = money(w.unrealized_pnl);
  unrealizedEl.className = "stat-value " + pnlClass(w.unrealized_pnl);

  const realizedEl = document.getElementById("w-realized");
  realizedEl.textContent = money(w.realized_pnl);
  realizedEl.className = "stat-value " + pnlClass(w.realized_pnl);

  const totalEl = document.getElementById("w-total");
  totalEl.textContent = `${money(w.total_pnl)} (${percent(w.return_pct)})`;
  totalEl.className = "stat-value " + pnlClass(w.total_pnl);
}

async function loadStocks() {
  const stocks = await api("/stocks");
  const positions = await api("/positions");
  const heldQty = Object.fromEntries(positions.map((p) => [p.symbol, p.quantity]));

  const tbody = document.querySelector("#stocks-table tbody");
  tbody.innerHTML = "";
  for (const s of stocks) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="symbol-link" data-symbol="${s.symbol}" title="Show chart">${s.symbol}</td>
      <td>${s.name}</td>
      <td>${money(s.current_price)}</td>
      <td class="qty-input"><input type="number" min="1" value="1" id="qty-${s.symbol}" /></td>
      <td>
        <button class="btn btn-buy" data-symbol="${s.symbol}" data-side="BUY">Buy</button>
        <button class="btn btn-sell" data-symbol="${s.symbol}" data-side="SELL" ${
      !heldQty[s.symbol] ? "disabled" : ""
    }>Sell</button>
      </td>
    `;
    tbody.appendChild(tr);
  }

  tbody.querySelectorAll("button[data-side]").forEach((btn) => {
    btn.addEventListener("click", () => placeOrder(btn.dataset.symbol, btn.dataset.side));
  });
  bindSymbolLinks(tbody);
}

async function loadPositions() {
  const positions = await api("/positions");
  const tbody = document.querySelector("#positions-table tbody");
  tbody.innerHTML = "";
  document.getElementById("positions-empty").hidden = positions.length > 0;

  for (const p of positions) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="symbol-link" data-symbol="${p.symbol}" title="Show chart">${p.symbol}</td>
      <td>${p.quantity}</td>
      <td>${money(p.average_price)}</td>
      <td>${money(p.current_price)}</td>
      <td>${money(p.market_value)}</td>
      <td class="pnl ${pnlClass(p.unrealized_pnl)}">${money(p.unrealized_pnl)}</td>
    `;
    tbody.appendChild(tr);
  }
  bindSymbolLinks(tbody);
}

async function loadTrades() {
  const trades = await api("/trades");
  const tbody = document.querySelector("#trades-table tbody");
  tbody.innerHTML = "";
  document.getElementById("trades-empty").hidden = trades.length > 0;

  for (const t of trades) {
    const tr = document.createElement("tr");
    const time = new Date(t.timestamp).toLocaleString("en-IN");
    const pnl =
      t.realized_pnl === null || t.realized_pnl === undefined
        ? "-"
        : `<span class="${pnlClass(t.realized_pnl)}">${money(t.realized_pnl)}</span>`;
    tr.innerHTML = `
      <td>${t.market_date || "-"}</td>
      <td>${time}</td>
      <td>${t.symbol}</td>
      <td class="side-${t.side.toLowerCase()}">${t.side}</td>
      <td>${t.quantity}</td>
      <td>${money(t.price)}</td>
      <td>${pnl}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshMarketViews() {
  await Promise.all([loadWallet(), loadStocks(), loadPositions(), loadChart()]);
}

async function refreshAll() {
  await Promise.all([loadWallet(), loadStocks(), loadPositions(), loadTrades(), loadChart()]);
}

async function placeOrder(symbol, side) {
  const qtyInput = document.getElementById(`qty-${symbol}`);
  const quantity = parseInt(qtyInput.value, 10);
  if (!quantity || quantity <= 0) {
    showToast("Enter a quantity greater than 0", true);
    return;
  }

  try {
    await api(`/orders/${side.toLowerCase()}`, {
      method: "POST",
      body: JSON.stringify({ symbol, quantity }),
    });
    showToast(`${side} ${quantity} ${symbol} executed`);
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function resetSimulation() {
  if (!confirm("Reset the simulation? This clears all trades and positions.")) return;
  try {
    stopPlaying();
    await api("/reset", { method: "POST" });
    showToast("Simulation reset");
    await loadMarketConfigs();
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

const MODEL_INFO = {
  random_walk:
    "Random walk: each day's move is random noise around the Trend. Yesterday tells you nothing about tomorrow.",
  trending:
    "Trending: moves carry momentum, so price keeps drifting in the Trend direction. Set a non-zero Trend (negative = downtrend).",
  volatile:
    "Volatile: like a random walk but daily swings are about 2.5x larger. More risk, bigger surprises.",
  sideways:
    "Sideways: price is pulled back toward its starting price, so it oscillates in a range instead of running away.",
};

const market = { symbol: null, configs: {}, timer: null, busy: false };

const roundTo = (n, digits) => Number(n.toFixed(digits));

function showConfig() {
  const cfg = market.configs[market.symbol];
  if (!cfg) return;
  document.getElementById("m-model").value = cfg.model;
  document.getElementById("m-vol").value = roundTo(cfg.volatility * 100, 3);
  document.getElementById("m-trend").value = roundTo(cfg.trend * 100, 3);
  document.getElementById("m-model-desc").textContent = MODEL_INFO[cfg.model];
}

async function loadMarketConfigs() {
  const configs = await api("/market/config");
  market.configs = Object.fromEntries(configs.map((c) => [c.symbol, c]));

  const select = document.getElementById("m-symbol");
  if (select.options.length === 0) {
    for (const c of configs) select.add(new Option(c.symbol, c.symbol));
  }
  if (!market.symbol || !market.configs[market.symbol]) market.symbol = configs[0].symbol;
  select.value = market.symbol;
  showConfig();
}

function selectSymbol(symbol) {
  if (!market.configs[symbol]) return;
  market.symbol = symbol;
  document.getElementById("m-symbol").value = symbol;
  showConfig();
  loadChart();
}

function bindSymbolLinks(container) {
  container.querySelectorAll(".symbol-link").forEach((cell) => {
    cell.addEventListener("click", () => {
      selectSymbol(cell.dataset.symbol);
      document.getElementById("chart").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

function chartOptions() {
  const smas = [];
  for (const [kind, color] of [["fast", "#2563eb"], ["slow", "#f59e0b"]]) {
    const enabled = document.getElementById(`ind-${kind}-on`).checked;
    const value = parseInt(document.getElementById(`ind-${kind}`).value, 10);
    if (enabled && value >= 2 && value <= 500) smas.push({ period: value, color });
  }
  return { smas, showTrades: document.getElementById("ind-trades").checked };
}

async function loadChart() {
  if (!market.symbol) return;
  const chartEl = document.getElementById("chart");
  if (typeof Plotly === "undefined") {
    chartEl.textContent = "Chart library failed to load (check your internet connection).";
    return;
  }

  const { smas, showTrades } = chartOptions();
  const smaQuery = smas.map((m) => `sma=${m.period}`).join("&");
  const [prices, indicators, trades] = await Promise.all([
    api(`/stocks/${market.symbol}/prices`),
    smas.length ? api(`/stocks/${market.symbol}/indicators?${smaQuery}`) : { sma: {} },
    showTrades ? api("/trades") : [],
  ]);
  document.getElementById("m-date").textContent = prices.length ? prices[prices.length - 1].date : "-";

  const traces = [
    {
      type: "candlestick",
      name: market.symbol,
      x: prices.map((p) => p.date),
      open: prices.map((p) => p.open),
      high: prices.map((p) => p.high),
      low: prices.map((p) => p.low),
      close: prices.map((p) => p.close),
      increasing: { line: { color: "#16a34a" } },
      decreasing: { line: { color: "#dc2626" } },
    },
  ];

  for (const m of smas) {
    const points = indicators.sma[String(m.period)] || [];
    traces.push({
      type: "scatter",
      mode: "lines",
      name: `SMA ${m.period}`,
      x: points.map((pt) => pt.date),
      y: points.map((pt) => pt.value),
      line: { color: m.color, width: 1.8 },
      hovertemplate: `SMA ${m.period}: ₹%{y:.2f}<extra></extra>`,
    });
  }

  const mine = trades.filter((t) => t.symbol === market.symbol && t.market_date);
  for (const side of ["BUY", "SELL"]) {
    const list = mine.filter((t) => t.side === side);
    if (!list.length) continue;
    const buy = side === "BUY";
    traces.push({
      type: "scatter",
      mode: "markers",
      name: side,
      x: list.map((t) => t.market_date),
      y: list.map((t) => t.price),
      text: list.map((t) => `${side} ${t.quantity} @ ${money(t.price)}`),
      hoverinfo: "text",
      marker: {
        symbol: buy ? "triangle-up" : "triangle-down",
        size: 13,
        color: buy ? "#15803d" : "#b91c1c",
        line: { color: "white", width: 1.5 },
      },
    });
  }

  const layout = {
    margin: { l: 55, r: 15, t: 30, b: 35 },
    xaxis: { rangeslider: { visible: false }, rangebreaks: [{ bounds: ["sat", "mon"] }] },
    yaxis: { title: "Price (₹)", tickprefix: "₹" },
    legend: { orientation: "h", y: 1.1, x: 0 },
    paper_bgcolor: "rgba(0,0,0,0)",
  };
  Plotly.react(chartEl, traces, layout, { displayModeBar: false, responsive: true });
}

async function applyConfig() {
  const body = {
    model: document.getElementById("m-model").value,
    volatility: parseFloat(document.getElementById("m-vol").value) / 100,
    trend: parseFloat(document.getElementById("m-trend").value) / 100,
  };
  try {
    const saved = await api(`/market/config/${market.symbol}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    market.configs[saved.symbol] = saved;
    showConfig();
    showToast(`${saved.symbol} set to ${saved.model}. Applies to new days (Advance or Regenerate).`);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function advanceMarket(days) {
  if (market.busy) return;
  market.busy = true;
  try {
    await api("/market/advance", { method: "POST", body: JSON.stringify({ days }) });
    await refreshMarketViews();
  } catch (err) {
    stopPlaying();
    showToast(err.message, true);
  } finally {
    market.busy = false;
  }
}

async function regenerateHistory() {
  const days = parseInt(document.getElementById("m-days").value, 10);
  if (!days || days < 2 || days > 1000) {
    showToast("History days must be between 2 and 1000", true);
    return;
  }
  try {
    stopPlaying();
    await api("/market/generate", { method: "POST", body: JSON.stringify({ days }) });
    showToast(`Generated ${days} days of new history for all stocks`);
    await refreshMarketViews();
  } catch (err) {
    showToast(err.message, true);
  }
}

function startPlaying() {
  const interval = parseInt(document.getElementById("m-speed").value, 10);
  market.timer = setInterval(() => advanceMarket(1), interval);
  document.getElementById("play-btn").textContent = "Pause";
}

function stopPlaying() {
  clearInterval(market.timer);
  market.timer = null;
  document.getElementById("play-btn").textContent = "Play";
}

document.getElementById("reset-btn").addEventListener("click", resetSimulation);
document.getElementById("m-apply").addEventListener("click", applyConfig);
document.getElementById("adv-1").addEventListener("click", () => advanceMarket(1));
document.getElementById("adv-5").addEventListener("click", () => advanceMarket(5));
document.getElementById("m-regen").addEventListener("click", regenerateHistory);
document.getElementById("play-btn").addEventListener("click", () => {
  if (market.timer) stopPlaying();
  else startPlaying();
});
document.getElementById("m-speed").addEventListener("change", () => {
  if (market.timer) {
    stopPlaying();
    startPlaying();
  }
});
document.getElementById("m-symbol").addEventListener("change", (e) => selectSymbol(e.target.value));
for (const id of ["ind-fast-on", "ind-fast", "ind-slow-on", "ind-slow", "ind-trades"]) {
  document.getElementById(id).addEventListener("change", loadChart);
}
document.getElementById("m-model").addEventListener("change", (e) => {
  document.getElementById("m-model-desc").textContent = MODEL_INFO[e.target.value];
  const trendEl = document.getElementById("m-trend");
  if (e.target.value === "trending" && parseFloat(trendEl.value) === 0) trendEl.value = 0.3;
});

checkHealth();
loadMarketConfigs().then(refreshAll);
