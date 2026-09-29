import { $, api, money, toast } from "../util.js";
import { hooks, store } from "../store.js";
import { drawPriceChart, loadChartData } from "../chart.js";
import { signalHeadline, signalOutcome, whyCard } from "../why.js";
import * as rb from "../rulebuilder.js";

const state = { selectedId: null, editingId: null, openWhy: new Set() };

const typeOf = (key) => store.strategyTypes.find((t) => t.key === key);
const editingStrategy = () => store.strategies.find((s) => s.id === state.editingId) || null;
const isCustom = () => $("sb-type").value === "custom";

/* ---------------- builder ---------------- */

function readParams() {
  const values = {};
  $("sb-params").querySelectorAll("input[data-param]").forEach((input) => {
    values[input.dataset.param] = input.dataset.kind === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
  });
  return values;
}

function renderRule() {
  const type = typeOf($("sb-type").value);
  if (!type) return;
  const values = readParams();
  const fill = (text) => text.replace(/\{(\w+)\}/g, (_, key) => (Number.isNaN(values[key]) || values[key] === undefined ? "?" : values[key]));
  $("sb-rule").innerHTML = `<div><b class="up">BUY</b> when ${fill(type.entry_text)}</div><div><b class="down">SELL</b> when ${fill(type.exit_text)}</div>`;
}

function renderTypeFields(values) {
  const type = typeOf($("sb-type").value);
  if (!type) return;
  $("sb-desc").innerHTML = `<p>${type.summary}</p>
    <p><b class="up">Works best:</b> ${type.works_best}</p>
    <p><b class="down">Struggles:</b> ${type.struggles}</p>`;
  $("sb-params").innerHTML = type.params
    .map(
      (p) => `<label class="field">${p.label}
        <input type="number" data-param="${p.name}" data-kind="${p.kind}" min="${p.min}" max="${p.max}" step="${p.step}" value="${values?.[p.name] ?? p.default}" />
      </label>`,
    )
    .join("");
  $("sb-params").querySelectorAll("input").forEach((input) => input.addEventListener("input", renderRule));
  renderRule();
}

function updateCustomPreview() {
  const rules = { entry: rb.readSide($("sb-entry-rows"), $("sb-entry-logic").value), exit: rb.readSide($("sb-exit-rows"), $("sb-exit-logic").value) };
  $("sb-custom-preview").textContent = rb.ruleSummaryText(rules);
}

function renderCustomRules(rules) {
  $("sb-entry-logic").value = rules.entry.logic;
  $("sb-exit-logic").value = rules.exit.logic;
  rb.renderSide($("sb-entry-rows"), rules.entry);
  rb.renderSide($("sb-exit-rows"), rules.exit);
  updateCustomPreview();
}

function switchBuilderMode() {
  const custom = isCustom();
  $("sb-desc").hidden = custom;
  $("sb-params").hidden = custom;
  $("sb-rule").hidden = custom;
  $("sb-custom").hidden = !custom;
}

function applyBuilderDefaults() {
  switchBuilderMode();
  if (isCustom()) renderCustomRules(rb.DEFAULT_RULES);
  else renderTypeFields();
}

function renderBuilder() {
  const typeSelect = $("sb-type");
  if (typeSelect.options.length !== store.strategyTypes.length + 1) {
    typeSelect.innerHTML =
      store.strategyTypes.map((t) => `<option value="${t.key}">${t.label}</option>`).join("") +
      `<option value="custom">Custom (build your own rules)</option>`;
    applyBuilderDefaults();
  }
  const symbolSelect = $("sb-symbol");
  if (symbolSelect.options.length !== store.stocks.length) {
    symbolSelect.innerHTML = store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}</option>`).join("");
    symbolSelect.value = store.symbol;
  }
  const editing = editingStrategy();
  $("sb-title").textContent = editing ? "Edit strategy" : "Strategy builder";
  $("sb-create").textContent = editing ? "Save changes" : "Create strategy";
  $("sb-cancel").hidden = !editing;
  $("sb-all").hidden = Boolean(editing);
  $("sb-symbol").disabled = Boolean(editing);
  $("sb-type").disabled = Boolean(editing);
}

function resetBuilder() {
  state.editingId = null;
  $("sb-qty").value = 10;
  $("sb-auto").checked = false;
  $("sb-symbol").value = store.symbol;
  applyBuilderDefaults();
  renderBuilder();
}

async function saveBuilder() {
  const quantity = parseInt($("sb-qty").value, 10);
  if (!(quantity >= 1)) {
    toast("Shares per trade must be at least 1", true);
    return;
  }
  const custom = isCustom();
  const body = custom
    ? {
        symbol: $("sb-symbol").value,
        type: "custom",
        rules: { entry: rb.readSide($("sb-entry-rows"), $("sb-entry-logic").value), exit: rb.readSide($("sb-exit-rows"), $("sb-exit-logic").value) },
        quantity,
        auto_trade: $("sb-auto").checked,
      }
    : { symbol: $("sb-symbol").value, type: $("sb-type").value, params: readParams(), quantity, auto_trade: $("sb-auto").checked };
  try {
    if (state.editingId) {
      const patch = custom ? { rules: body.rules, quantity, auto_trade: body.auto_trade } : { params: body.params, quantity, auto_trade: body.auto_trade };
      await api(`/strategies/${state.editingId}`, { method: "PATCH", body: JSON.stringify(patch) });
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

async function createOneOfEach() {
  const symbol = $("sb-symbol").value;
  const quantity = Math.max(parseInt($("sb-qty").value, 10) || 10, 1);
  try {
    let firstId = null;
    let totalSignals = 0;
    for (const type of store.strategyTypes) {
      const created = await api("/strategies", { method: "POST", body: JSON.stringify({ symbol, type: type.key, quantity }) });
      firstId ??= created.id;
      totalSignals += (await api(`/strategies/${created.id}/run`, { method: "POST" })).length;
    }
    state.selectedId = firstId;
    toast(`Created ${store.strategyTypes.length} strategies on ${symbol} and found ${totalSignals} signals in total. Compare their charts.`);
    await hooks.refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

function startEdit(id) {
  const s = store.strategies.find((x) => x.id === id);
  if (!s) return;
  state.editingId = id;
  $("sb-type").value = s.type;
  switchBuilderMode();
  if (s.type === "custom") renderCustomRules(s.rules);
  else renderTypeFields(s.params);
  $("sb-symbol").value = s.symbol;
  $("sb-qty").value = s.quantity;
  $("sb-auto").checked = s.auto_trade;
  renderBuilder();
  $("sb-params").querySelector("input")?.focus();
}

/* ---------------- list ---------------- */

function renderList() {
  const list = $("strat-list");
  $("strat-empty").hidden = store.strategies.length > 0;
  list.innerHTML = store.strategies
    .map(
      (s) => `<div class="strat-card ${s.id === state.selectedId ? "sel" : ""}" data-id="${s.id}">
        <div class="strat-head"><b>${s.name}</b><span class="chip">${s.type_label}</span></div>
        <div class="muted small">${s.param_summary} &middot; ${s.quantity} shares per trade &middot; holding ${s.held}</div>
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
    toast(
      signals.length
        ? `Found ${signals.length} signal${signals.length === 1 ? "" : "s"} in the price history`
        : "No signals in the current history. Try different settings or generate more days.",
    );
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

  const [{ prices }, overlays, signals] = await Promise.all([
    loadChartData(strategy.symbol, []),
    api(`/strategies/${strategy.id}/series`),
    api(`/signals?strategy_id=${strategy.id}`),
  ]);
  if (state.selectedId !== strategy.id) return;

  if (typeof Plotly === "undefined") {
    $("strat-chart").textContent = "Chart library failed to load (check your internet connection).";
  } else {
    drawPriceChart($("strat-chart"), { symbol: strategy.symbol, prices, overlays, trades: store.trades, signals });
  }

  $("sd-legend").innerHTML =
    overlays.map((o) => `<span><i style="background:${o.color}"></i>${o.name}</span>`).join("") +
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
        <td class="muted">${signalHeadline(s)}</td>
        <td>${signalOutcome(s)}</td>
        <td class="num"><button class="btn" data-why="${s.id}">${open ? "Hide" : "Why?"}</button></td>
      </tr>${open ? `<tr class="why-row"><td colspan="6">${whyCard(s)}</td></tr>` : ""}`;
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
  $("sb-all").addEventListener("click", createOneOfEach);
  $("sb-type").addEventListener("change", applyBuilderDefaults);

  $("sb-entry-add").addEventListener("click", () => {
    rb.addRow($("sb-entry-rows"));
    updateCustomPreview();
  });
  $("sb-exit-add").addEventListener("click", () => {
    rb.addRow($("sb-exit-rows"));
    updateCustomPreview();
  });
  rb.initSide($("sb-entry-rows"), updateCustomPreview);
  rb.initSide($("sb-exit-rows"), updateCustomPreview);
  $("sb-entry-logic").addEventListener("change", updateCustomPreview);
  $("sb-exit-logic").addEventListener("change", updateCustomPreview);
}
