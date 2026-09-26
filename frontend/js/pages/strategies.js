import { $, api, money, toast } from "../util.js";
import { hooks, store } from "../store.js";
import { SMA_COLORS, drawPriceChart, loadChartData } from "../chart.js";
import { signalOutcome, whyCard } from "../why.js";

const state = { selectedId: null, editingId: null, openWhy: new Set() };

/* ---------------- builder ---------------- */

const editingStrategy = () => store.strategies.find((s) => s.id === state.editingId) || null;

function renderBuilder() {
  const select = $("sb-symbol");
  if (select.options.length !== store.stocks.length) {
    select.innerHTML = store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}</option>`).join("");
    select.value = store.symbol;
  }
  const editing = editingStrategy();
  $("sb-title").textContent = editing ? "Edit strategy" : "Strategy builder";
  $("sb-create").textContent = editing ? "Save changes" : "Create strategy";
  $("sb-cancel").hidden = !editing;
  $("sb-symbol").disabled = Boolean(editing);
}

function readBuilder() {
  return {
    symbol: $("sb-symbol").value,
    fast: parseInt($("sb-fast").value, 10),
    slow: parseInt($("sb-slow").value, 10),
    quantity: parseInt($("sb-qty").value, 10),
    auto_trade: $("sb-auto").checked,
  };
}

function resetBuilder() {
  state.editingId = null;
  $("sb-fast").value = 20;
  $("sb-slow").value = 50;
  $("sb-qty").value = 10;
  $("sb-auto").checked = false;
  $("sb-symbol").value = store.symbol;
  renderBuilder();
}

async function saveBuilder() {
  const body = readBuilder();
  if (!(body.fast >= 2) || !(body.slow > body.fast) || !(body.quantity >= 1)) {
    toast("Fast must be at least 2 and smaller than slow, and quantity at least 1", true);
    return;
  }
  try {
    if (state.editingId) {
      const { symbol, ...changes } = body;
      await api(`/strategies/${state.editingId}`, { method: "PATCH", body: JSON.stringify(changes) });
      toast("Strategy updated. Run it on history to refresh its signals.");
      resetBuilder();
    } else {
      const created = await api("/strategies", { method: "POST", body: JSON.stringify(body) });
      state.selectedId = created.id;
      toast(`Created "${created.name}". Click "Run on history" to see its signals.`);
    }
    await hooks.refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

function startEdit(id) {
  const s = store.strategies.find((x) => x.id === id);
  if (!s) return;
  state.editingId = id;
  $("sb-symbol").value = s.symbol;
  $("sb-fast").value = s.fast;
  $("sb-slow").value = s.slow;
  $("sb-qty").value = s.quantity;
  $("sb-auto").checked = s.auto_trade;
  renderBuilder();
  $("sb-fast").focus();
}

/* ---------------- list ---------------- */

function renderList() {
  const list = $("strat-list");
  $("strat-empty").hidden = store.strategies.length > 0;
  list.innerHTML = store.strategies
    .map(
      (s) => `<div class="strat-card ${s.id === state.selectedId ? "sel" : ""}" data-id="${s.id}">
        <div class="strat-head"><b>${s.name}</b><span class="chip">${s.symbol}</span></div>
        <div class="muted small">Fast ${s.fast} &middot; Slow ${s.slow} &middot; ${s.quantity} shares per trade &middot; holding ${s.held}</div>
        <div class="muted small">Signals: ${s.signal_count} (${s.buy_count} BUY &middot; ${s.sell_count} SELL)</div>
        <div class="strat-actions">
          <label class="switch"><input type="checkbox" data-auto="${s.id}" ${s.auto_trade ? "checked" : ""} /> Auto-trade</label>
          <span class="spacer"></span>
          <button class="btn" data-run="${s.id}">Run on history</button>
          <button class="btn" data-edit="${s.id}">Edit</button>
          <button class="btn btn-sell" data-del="${s.id}">Delete</button>
        </div>
      </div>`,
    )
    .join("");

  list.querySelectorAll(".strat-card").forEach((card) =>
    card.addEventListener("click", (e) => {
      if (e.target.closest("button, label, input")) return;
      state.selectedId = Number(card.dataset.id);
      renderStrategies();
    }),
  );
  list.querySelectorAll("[data-auto]").forEach((box) =>
    box.addEventListener("change", async () => {
      try {
        await api(`/strategies/${box.dataset.auto}`, { method: "PATCH", body: JSON.stringify({ auto_trade: box.checked }) });
        toast(box.checked ? "Auto-trade on: this strategy now trades as the market advances." : "Auto-trade off.");
        await hooks.refresh();
      } catch (err) {
        box.checked = !box.checked;
        toast(err.message, true);
      }
    }),
  );
  list.querySelectorAll("[data-run]").forEach((btn) => btn.addEventListener("click", () => runOnHistory(Number(btn.dataset.run))));
  list.querySelectorAll("[data-edit]").forEach((btn) => btn.addEventListener("click", () => startEdit(Number(btn.dataset.edit))));
  list.querySelectorAll("[data-del]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const s = store.strategies.find((x) => x.id === Number(btn.dataset.del));
      if (!s || !confirm(`Delete "${s.name}"? Its signals are removed; its past trades stay as manual trades.`)) return;
      try {
        await api(`/strategies/${s.id}`, { method: "DELETE" });
        if (state.selectedId === s.id) state.selectedId = null;
        if (state.editingId === s.id) resetBuilder();
        await hooks.refresh();
      } catch (err) {
        toast(err.message, true);
      }
    }),
  );
}

async function runOnHistory(id) {
  try {
    const signals = await api(`/strategies/${id}/run`, { method: "POST" });
    state.selectedId = id;
    toast(signals.length ? `Found ${signals.length} crossover signal${signals.length === 1 ? "" : "s"} in the price history` : "No crossovers in the current history. Try shorter periods or more days.");
    await hooks.refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------- detail: chart + signals ---------------- */

async function renderDetail() {
  const strategy = store.strategies.find((s) => s.id === state.selectedId);
  $("strat-detail").hidden = !strategy;
  if (!strategy) return;

  $("sd-title").textContent = strategy.name;
  $("sd-rule").textContent = strategy.description || "";

  const smas = [
    { period: strategy.fast, color: SMA_COLORS.fast },
    { period: strategy.slow, color: SMA_COLORS.slow },
  ];
  const [{ prices, indicators }, signals] = await Promise.all([
    loadChartData(strategy.symbol, smas),
    api(`/signals?strategy_id=${strategy.id}`),
  ]);
  if (state.selectedId !== strategy.id) return;

  if (typeof Plotly === "undefined") {
    $("strat-chart").textContent = "Chart library failed to load (check your internet connection).";
  } else {
    drawPriceChart($("strat-chart"), { symbol: strategy.symbol, prices, indicators, smas, trades: store.trades, signals });
  }

  $("sd-legend").innerHTML =
    `<span><i style="background:${SMA_COLORS.fast}"></i>SMA ${strategy.fast}</span>` +
    `<span><i style="background:${SMA_COLORS.slow}"></i>SMA ${strategy.slow}</span>` +
    `<span class="up">&#9650; BUY signal</span><span class="down">&#9660; SELL signal</span>`;

  renderSignals(signals);
}

function renderSignals(signals) {
  $("signals-empty").hidden = signals.length > 0;
  const tbody = document.querySelector("#signals-table tbody");
  tbody.innerHTML = signals
    .map((s) => {
      const open = state.openWhy.has(s.id);
      return `<tr>
        <td>${s.date}</td>
        <td class="side-${s.signal.toLowerCase()}">${s.signal}</td>
        <td class="num">${money(s.price)}</td>
        <td class="num">${money(s.details.fast_ma)}</td>
        <td class="num">${money(s.details.slow_ma)}</td>
        <td>${signalOutcome(s)}</td>
        <td class="num"><button class="btn" data-why="${s.id}">${open ? "Hide" : "Why?"}</button></td>
      </tr>${open ? `<tr class="why-row"><td colspan="7">${whyCard(s)}</td></tr>` : ""}`;
    })
    .join("");

  tbody.querySelectorAll("[data-why]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.why);
      if (state.openWhy.has(id)) state.openWhy.delete(id);
      else state.openWhy.add(id);
      renderSignals(signals);
    }),
  );
}

/* ---------------- public API ---------------- */

export async function renderStrategies() {
  if (!store.strategies.some((s) => s.id === state.selectedId)) state.selectedId = store.strategies[0]?.id ?? null;
  renderBuilder();
  renderList();
  await renderDetail();
}

export function initStrategies() {
  $("sb-create").addEventListener("click", saveBuilder);
  $("sb-cancel").addEventListener("click", resetBuilder);
}
