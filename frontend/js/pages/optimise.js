import { $, api, percent, pnlClass, signedPercent, toast } from "../util.js";
import { store } from "../store.js";
import { currentTheme, themeColors } from "../theme.js";

const MAX_COMBINATIONS = 400; // keep in step with services/optimizer_service.py
const MAX_AXIS_VALUES = 40;
const NICE_STEPS = [1, 2, 5, 10, 20, 25, 50, 100];
const METRIC_LABEL = { return: "total return", risk_adjusted: "return per unit of drawdown" };

const state = { result: null, runId: 0, drawn: "", running: false, history: {} };

const typeOf = (key) => store.strategyTypes.find((t) => t.key === key);
const specOf = (name) => typeOf($("op-type").value)?.params.find((p) => p.name === name);
const roundTo = (n, digits) => Math.round(n * 10 ** digits) / 10 ** digits;
const num = (id) => parseFloat($(id).value);

/* ---------------- the builder ---------------- */

/** A sensible sweep for one setting: about half to double its default, in about eight steps. */
function defaultRange(spec) {
  let low = Math.max(spec.min, spec.default * 0.5);
  let high = Math.min(spec.max, spec.default * 2);
  if (!(low < high)) [low, high] = [spec.min, spec.max];
  const units = Math.max(1, (high - low) / spec.step);
  const nice = NICE_STEPS.find((n) => n >= units / 8) || NICE_STEPS[NICE_STEPS.length - 1];
  const step = roundTo(nice * spec.step, 6);
  low = Math.max(spec.min, roundTo(Math.ceil(low / step - 1e-9) * step, 6));
  high = Math.min(spec.max, roundTo(Math.floor(high / step + 1e-9) * step, 6));
  return { low, high: high > low ? high : spec.max, step };
}

function setRange(axis, spec) {
  const { low, high, step } = defaultRange(spec);
  $(`op-${axis}-low`).value = low;
  $(`op-${axis}-high`).value = high;
  $(`op-${axis}-step`).value = step;
  for (const part of ["low", "high"]) {
    $(`op-${axis}-${part}`).min = spec.min;
    $(`op-${axis}-${part}`).max = spec.max;
  }
}

function fillAxisSelects({ resetRanges }) {
  const type = typeOf($("op-type").value);
  if (!type) return;
  const x = $("op-x");
  const wantedX = type.params.some((p) => p.name === x.value) ? x.value : type.params[0].name;
  x.innerHTML = type.params.map((p) => `<option value="${p.name}">${p.label}</option>`).join("");
  x.value = wantedX;

  const y = $("op-y");
  const previousY = y.value;
  y.innerHTML =
    `<option value="">(none: vary one setting only)</option>` +
    type.params
      .filter((p) => p.name !== wantedX)
      .map((p) => `<option value="${p.name}">${p.label}</option>`)
      .join("");
  y.value = resetRanges ? (type.params.find((p) => p.name !== wantedX)?.name ?? "") : previousY;

  if (resetRanges) {
    setRange("x", specOf(wantedX));
    if (y.value) setRange("y", specOf(y.value));
  }
  syncYRange();
}

function syncYRange() {
  $("op-y-range").hidden = !$("op-y").value;
  updateCombos();
}

function valueCount(prefix, spec) {
  const low = num(`${prefix}-low`);
  const high = num(`${prefix}-high`);
  const step = num(`${prefix}-step`);
  if (!spec || !(step > 0) || !(low <= high)) return NaN;
  return spec.kind === "int" ? Math.floor((high - Math.round(low)) / Math.max(1, Math.round(step))) + 1 : Math.round((high - low) / step + 1e-9) + 1;
}

function updateCombos() {
  const nx = valueCount("op-x", specOf($("op-x").value));
  const ny = $("op-y").value ? valueCount("op-y", specOf($("op-y").value)) : 1;
  const hint = $("op-combos");
  const total = nx * ny;
  hint.classList.toggle("over", !(total <= MAX_COMBINATIONS) || nx > MAX_AXIS_VALUES || ny > MAX_AXIS_VALUES);
  if (!Number.isFinite(total)) hint.textContent = "Check the ranges: From must not be above To, and Step must be above zero.";
  else if (total > MAX_COMBINATIONS) hint.textContent = `${$("op-y").value ? `${nx} × ${ny} = ` : ""}${total} combinations is too many (most allowed: ${MAX_COMBINATIONS}). Use bigger steps or narrower ranges.`;
  else if (nx > MAX_AXIS_VALUES || ny > MAX_AXIS_VALUES) hint.textContent = `One setting would try more than ${MAX_AXIS_VALUES} values. Use a bigger step.`;
  else hint.textContent = `${$("op-y").value ? `${nx} × ${ny} = ` : ""}${total} combination${total === 1 ? "" : "s"} will be tested, each on both periods.`;
  const fixed = typeOf($("op-type").value)?.params.filter((p) => p.name !== $("op-x").value && p.name !== $("op-y").value);
  $("op-hint").dataset.fixed = fixed?.length ? fixed.map((p) => `${p.label} ${p.default}`).join(", ") : "";
}

async function historyDates(symbol) {
  if (!state.history[symbol]) {
    const prices = await api(`/stocks/${symbol}/prices?full=true`);
    state.history[symbol] = prices.map((p) => p.date);
  }
  return state.history[symbol];
}

async function applySplit(kind) {
  const dates = await historyDates($("op-symbol").value).catch(() => []);
  if (!dates.length) return;
  const set = (id, value) => ($(id).value = value || "");
  for (const id of ["op-train-from", "op-train-to", "op-test-from", "op-test-to"]) {
    $(id).min = dates[0];
    $(id).max = dates[dates.length - 1];
  }
  if (kind === "none") {
    set("op-train-from", "");
    set("op-train-to", "");
    set("op-test-from", "");
    set("op-test-to", "");
    return;
  }
  const cut = Math.floor((dates.length * Number(kind)) / 100);
  set("op-train-from", dates[0]);
  set("op-train-to", dates[cut - 1]);
  set("op-test-from", dates[cut]);
  set("op-test-to", dates[dates.length - 1]);
}

function renderBuilder() {
  const types = store.strategyTypes;
  const typeSelect = $("op-type");
  if (typeSelect.options.length !== types.length) {
    typeSelect.innerHTML = types.map((t) => `<option value="${t.key}">${t.label}</option>`).join("");
    fillAxisSelects({ resetRanges: true });
  }
  const symbolSelect = $("op-symbol");
  if (symbolSelect.options.length !== store.stocks.length) {
    symbolSelect.innerHTML = store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}</option>`).join("");
    symbolSelect.value = store.stocks.some((s) => s.symbol === "RELIANCE") ? "RELIANCE" : store.symbol;
    applySplit("70");
  }
}

/* ---------------- running ---------------- */

function buildRequest() {
  const type = typeOf($("op-type").value);
  const axis = (prefix, name) => ({ param: name, low: num(`${prefix}-low`), high: num(`${prefix}-high`), step: num(`${prefix}-step`) });
  const request = {
    symbol: $("op-symbol").value,
    type: type.key,
    x: axis("op-x", $("op-x").value),
    metric: $("op-metric").value,
    quantity: parseInt($("op-qty").value, 10),
    initial_capital: parseFloat($("op-capital").value),
  };
  if ($("op-y").value) request.y = axis("op-y", $("op-y").value);
  for (const [field, id] of [["train_start", "op-train-from"], ["train_end", "op-train-to"], ["test_start", "op-test-from"], ["test_end", "op-test-to"]]) {
    if ($(id).value) request[field] = $(id).value;
  }
  return request;
}

async function runOptimisation() {
  if (state.running) return;
  const request = buildRequest();
  if (!(request.quantity >= 1)) return toast("Shares per BUY must be at least 1", true);
  if (!(request.initial_capital > 0)) return toast("Initial capital must be greater than zero", true);
  for (const axis of [request.x, request.y].filter(Boolean)) {
    if (![axis.low, axis.high, axis.step].every(Number.isFinite)) return toast("Fill in From, To and Step for each setting", true);
  }
  if (request.test_end && !request.test_start) return toast("A test period needs a From date", true);

  state.running = true;
  $("op-run").disabled = true;
  $("op-run").textContent = "Running...";
  try {
    const result = await api("/backtests/optimise", { method: "POST", body: JSON.stringify(request) });
    state.result = result;
    state.runId += 1;
    renderResults();
  } catch (err) {
    toast(err.message, true);
  } finally {
    state.running = false;
    $("op-run").disabled = false;
    $("op-run").textContent = "Run optimisation";
  }
}

/* ---------------- results ---------------- */

const settingsText = (r, xv, yv) => `${r.x.label} ${xv}` + (r.y ? ` · ${r.y.label} ${yv}` : "");
const scoreText = (r, score) => (r.metric === "risk_adjusted" ? score.toFixed(2) : signedPercent(score));

function verdict(r) {
  const b = r.best;
  const trained = `${settingsText(r, b.params[r.x.name], r.y ? b.params[r.y.name] : null)}`;
  if (!r.test) {
    return { cls: "mixed", html: `Trained on ${r.train.start} to ${r.train.end} only. The best settings were <b>${trained}</b>. Add a test period to find out whether they hold up on data they have never seen.` };
  }
  const share = b.test_rank / b.test_valid;
  const rank = `${b.test_rank} of ${b.test_valid}`;
  const thin = b.test_valid < 8 ? " With so few combinations the ranking says little, so try a wider sweep." : "";
  const hold = r.test.buy_hold_pct;
  const trail = b.test.return_pct < hold ? ` It also trailed simply buying and holding the stock (${signedPercent(hold)}).` : ` For comparison, buying and holding made ${signedPercent(hold)}.`;
  if (b.test.return_pct > 0 && share <= 0.25) {
    return { cls: "good", html: `<b>Held up.</b> The training winner (${trained}) made ${signedPercent(b.train.return_pct)} in training and ${signedPercent(b.test.return_pct)} on the unseen test period, ranking ${rank} there (top ${Math.max(1, Math.round(share * 100))}%).${trail} One test is not proof, but a broad pattern like this is what a real edge looks like.${thin}` };
  }
  if (b.test.return_pct <= 0 || share >= 0.6) {
    return { cls: "bad", html: `<b>Did not hold up.</b> The training winner (${trained}) made ${signedPercent(b.train.return_pct)} in training but ${signedPercent(b.test.return_pct)} on data it had never seen, ranking ${rank} there.${trail} This is the classic sign of overfitting: the best-looking settings were mostly fitted to the past.${thin}` };
  }
  return { cls: "mixed", html: `<b>Mixed.</b> The training winner (${trained}) made ${signedPercent(b.train.return_pct)} in training and ${signedPercent(b.test.return_pct)} on the test period, ranking ${rank} there.${trail} It carried over partly, which is better than nothing but not convincing on its own.${thin}` };
}

function renderMetrics(r) {
  const b = r.best;
  const tiles = [["Training winner", settingsText(r, b.params[r.x.name], r.y ? b.params[r.y.name] : null), ""], ["Return in training", signedPercent(b.train.return_pct), pnlClass(b.train.return_pct)]];
  if (r.test) {
    tiles.push(
      ["Return on test", signedPercent(b.test.return_pct), pnlClass(b.test.return_pct)],
      ["Rank on test", `${b.test_rank} of ${b.test_valid}`, ""],
      ["Typical setting on test", scoreText(r, b.test_median_score), r.metric === "return" ? pnlClass(b.test_median_score) : ""],
      ["Buy & hold: train / test", `${signedPercent(r.train.buy_hold_pct)} / ${signedPercent(r.test.buy_hold_pct)}`, ""],
    );
  } else {
    tiles.push(["Buy & hold in training", signedPercent(r.train.buy_hold_pct), pnlClass(r.train.buy_hold_pct)]);
  }
  tiles.push(["Max drawdown (winner, training)", percent(b.train.max_drawdown_pct), b.train.max_drawdown_pct > 0 ? "down" : ""]);
  $("op-metrics").innerHTML = tiles.map(([label, value, cls]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
}

function heatmap(el, r, period, title) {
  const c = themeColors();
  const xs = r.x.values.map(String);
  const ys = r.y ? r.y.values.map(String) : [""];
  const z = period.cells.map((row) => row.map((cell) => (cell ? cell.score : null)));
  const text = period.cells.map((row, ri) =>
    row.map((cell, ci) => {
      const where = `${r.x.label}: ${xs[ci]}` + (r.y ? `<br>${r.y.label}: ${ys[ri]}` : "");
      return cell
        ? `${where}<br>Return: ${signedPercent(cell.return_pct)}<br>Max drawdown: ${percent(cell.max_drawdown_pct)}<br>Trades: ${cell.trades}<br>Score: ${r.metric === "risk_adjusted" ? cell.score.toFixed(2) : signedPercent(cell.score)}`
        : `${where}<br>Not a valid combination`;
    }),
  );
  const best = r.best.params;
  const bx = xs.indexOf(String(best[r.x.name]));
  const by = r.y ? ys.indexOf(String(best[r.y.name])) : 0;
  const small = xs.length * ys.length <= 144;
  const traces = [
    {
      type: "heatmap", x: xs, y: ys, z, text, hoverinfo: "text", hoverongaps: false, showscale: false, xgap: 1, ygap: 1,
      zmid: 0, colorscale: [[0, c.down], [0.5, c.line], [1, c.up]],
      ...(small ? { texttemplate: "%{z:.1f}", textfont: { size: 10, color: c.text } } : {}),
    },
    { type: "scatter", mode: "markers", x: [xs[bx]], y: [ys[by]], hoverinfo: "skip", marker: { symbol: "star", size: 15, color: "#ffffff", line: { color: "#000000", width: 1 } } },
  ];
  el.classList.toggle("thin", !r.y);
  el.previousElementSibling.textContent = title;
  Plotly.react(
    el,
    traces,
    {
      margin: { l: r.y ? 56 : 12, r: 8, t: 6, b: 46 },
      showlegend: false,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: c.muted, size: 11 },
      xaxis: { type: "category", title: { text: r.x.label }, automargin: true, showgrid: false, zeroline: false },
      yaxis: r.y ? { type: "category", title: { text: r.y.label }, automargin: true, showgrid: false, zeroline: false } : { visible: false },
    },
    { displayModeBar: false, responsive: true },
  );
}

function renderTopTable(r) {
  const panel = $("op-top-panel");
  panel.hidden = !r.test;
  if (!r.test) return;
  const rows = [];
  r.train.cells.forEach((row, ri) => row.forEach((cell, ci) => cell && rows.push({ ri, ci, train: cell, test: r.test.cells[ri][ci] })));
  const testScores = rows.map((row) => row.test.score);
  rows.sort((a, b) => b.train.score - a.train.score);
  document.querySelector("#op-top-table tbody").innerHTML = rows
    .slice(0, 8)
    .map((row) => {
      const rank = 1 + testScores.filter((s) => s > row.test.score).length;
      return `<tr>
        <td>${settingsText(r, r.x.values[row.ci], r.y ? r.y.values[row.ri] : null)}</td>
        <td class="num ${pnlClass(row.train.return_pct)}">${signedPercent(row.train.return_pct)}</td>
        <td class="num ${pnlClass(row.test.return_pct)}">${signedPercent(row.test.return_pct)}</td>
        <td class="num">${rank} of ${testScores.length}</td>
      </tr>`;
    })
    .join("");
}

function renderResults() {
  const r = state.result;
  $("op-empty").hidden = Boolean(r);
  $("op-results").hidden = !r;
  if (!r) return;

  $("op-title").textContent = `${r.type_label} on ${r.symbol}: ${r.x.label}${r.y ? ` × ${r.y.label}` : ""}`;
  const fixed = $("op-hint").dataset.fixed;
  $("op-sub").textContent =
    `${r.valid} of ${r.combinations} combinations valid · scored by ${METRIC_LABEL[r.metric]}` +
    (fixed ? ` · other settings held at their defaults (${fixed})` : "") +
    (r.uses_risk ? " · with your Risk management settings" : "") +
    (r.uses_costs ? " · with trading costs" : "");
  const v = verdict(r);
  $("op-verdict").className = `op-verdict ${v.cls}`;
  $("op-verdict").innerHTML = v.html;
  renderMetrics(r);
  renderTopTable(r);

  if (typeof Plotly === "undefined") return;
  const key = `${state.runId}|${currentTheme()}`;
  if (state.drawn === key) return;
  state.drawn = key;
  heatmap($("op-heat-train"), r, r.train, `Training: ${r.train.start} to ${r.train.end} (buy & hold ${signedPercent(r.train.buy_hold_pct)})`);
  $("op-test-wrap").hidden = !r.test;
  if (r.test) heatmap($("op-heat-test"), r, r.test, `Unseen test: ${r.test.start} to ${r.test.end} (buy & hold ${signedPercent(r.test.buy_hold_pct)})`);
}

/* ---------------- public API ---------------- */

export function renderOptimise() {
  renderBuilder();
  renderResults();
}

export function initOptimise() {
  $("op-type").addEventListener("change", () => fillAxisSelects({ resetRanges: true }));
  $("op-x").addEventListener("change", () => {
    fillAxisSelects({ resetRanges: false });
    setRange("x", specOf($("op-x").value));
    if ($("op-y").value) setRange("y", specOf($("op-y").value));
    updateCombos();
  });
  $("op-y").addEventListener("change", () => {
    if ($("op-y").value) setRange("y", specOf($("op-y").value));
    syncYRange();
  });
  for (const id of ["op-x-low", "op-x-high", "op-x-step", "op-y-low", "op-y-high", "op-y-step"]) $(id).addEventListener("input", updateCombos);
  $("op-symbol").addEventListener("change", () => applySplit("70"));
  $("op-presets").querySelectorAll("[data-split]").forEach((btn) => btn.addEventListener("click", () => applySplit(btn.dataset.split)));
  $("op-run").addEventListener("click", runOptimisation);
}
