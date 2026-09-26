const money = (n) =>
  "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

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
    statusEl.textContent = `${data.status.toUpperCase()} — ${data.app}`;
    statusEl.className = "ok";
  } catch (err) {
    statusEl.textContent = `Unable to reach backend (${err.message})`;
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
  totalEl.textContent = `${money(w.total_pnl)} (${w.return_pct.toFixed(2)}%)`;
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
      <td>${s.symbol}</td>
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
}

async function loadPositions() {
  const positions = await api("/positions");
  const tbody = document.querySelector("#positions-table tbody");
  tbody.innerHTML = "";
  document.getElementById("positions-empty").hidden = positions.length > 0;

  for (const p of positions) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.symbol}</td>
      <td>${p.quantity}</td>
      <td>${money(p.average_price)}</td>
      <td>${money(p.current_price)}</td>
      <td>${money(p.market_value)}</td>
      <td class="pnl ${pnlClass(p.unrealized_pnl)}">${money(p.unrealized_pnl)}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function loadTrades() {
  const trades = await api("/trades");
  const tbody = document.querySelector("#trades-table tbody");
  tbody.innerHTML = "";
  document.getElementById("trades-empty").hidden = trades.length > 0;

  for (const t of trades) {
    const tr = document.createElement("tr");
    const time = new Date(t.timestamp).toLocaleString("en-IN");
    tr.innerHTML = `
      <td>${time}</td>
      <td>${t.symbol}</td>
      <td>${t.side}</td>
      <td>${t.quantity}</td>
      <td>${money(t.price)}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshAll() {
  await Promise.all([loadWallet(), loadStocks(), loadPositions(), loadTrades()]);
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
    await api("/reset", { method: "POST" });
    showToast("Simulation reset");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

document.getElementById("reset-btn").addEventListener("click", resetSimulation);

checkHealth();
refreshAll();
