// The Compare page: two to four stocks (or a stock and an index you imported as a stock) drawn against each other,
// either all starting at 100 on one chart, or as two candlestick charts side by side that zoom together. The
// numbers (alignment, rebasing, return, risk, correlation) are in compare.js; this file only fetches and draws.
import { $, api, money, percent, signedPercent, toast } from "../util.js";
import { store } from "../store.js";
import { SERIES_COLORS, drawPriceChart, drawRebasedChart, linkXRanges } from "../chart.js";
import { PRESETS, alignSeries, applyPreset, rebase, relative, summarise } from "../compare.js";

const state = { view: "rebased", period: "all", picks: ["", "", "", ""], chosenByUser: [false, false, false, false], optionKey: "", cache: new Map(), draw: 0 };
const IDS = ["cmp-a", "cmp-b", "cmp-c", "cmp-d"];
const INDEX_NAMES = /^(NSE500|NIFTY500|NIFTY50|NIFTY)$/i;

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const dash = (value, format) => (value === null || value === undefined ? "-" : format(value));
const daysBefore = (iso, days) => new Date(new Date(`${iso}T00:00:00Z`).getTime() - days * 86400000).toISOString().slice(0, 10);

/* ---------------- choosing the stocks ---------------- */

function buildOptions() {
  const key = JSON.stringify(store.stocks.map((s) => s.symbol));
  if (key === state.optionKey) return;
  state.optionKey = key;
  const symbols = store.stocks.map((s) => s.symbol);
  const options = (blank) => (blank ? `<option value="">(none)</option>` : "") + store.stocks.map((s) => `<option value="${s.symbol}">${s.symbol}: ${escapeHtml(s.name)}</option>`).join("");

  const [a0, b0, c0, d0] = state.picks;
  const a = symbols.includes(a0) ? a0 : symbols.includes(store.symbol) ? store.symbol : symbols[0] || "";
  const index = symbols.find((s) => INDEX_NAMES.test(s) && s !== a);
  // Until you pick the second stock yourself, an imported index (NSE500...) is preferred, so importing one switches to it.
  const keepB = symbols.includes(b0) && b0 !== a && (state.chosenByUser[1] || !index);
  const b = keepB ? b0 : index || symbols.find((s) => s !== a) || "";
  state.picks = [a, b, symbols.includes(c0) ? c0 : "", symbols.includes(d0) ? d0 : ""];
  IDS.forEach((id, i) => {
    $(id).innerHTML = options(i >= 2);
    $(id).value = state.picks[i];
  });
}

const chosen = () => [...new Set(state.picks.filter(Boolean))];

/* ---------------- loading prices ---------------- */

async function loadPrices(symbol) {
  const key = `${symbol}|${store.marketDate}`;
  if (!state.cache.has(key)) state.cache.set(key, api(`/stocks/${symbol}/prices`).catch((err) => (state.cache.delete(key), Promise.reject(err))));
  return state.cache.get(key);
}

/* ---------------- drawing ---------------- */

function message(text) {
  $("cmp-empty").textContent = text;
  $("cmp-empty").hidden = !text;
}

function showView() {
  $("cmp-rebased").hidden = state.view !== "rebased";
  $("cmp-candles").hidden = state.view !== "candles";
  document.querySelectorAll("#cmp-view button").forEach((b) => b.classList.toggle("on", b.dataset.view === state.view));
  document.querySelectorAll("#cmp-periods button").forEach((b) => b.classList.toggle("on", b.dataset.period === state.period));
}

function drawRebased(windowed) {
  const { dates, series } = windowed;
  const lines = series.map((s, i) => ({ label: s.symbol, values: rebase(s.closes), color: SERIES_COLORS[i % SERIES_COLORS.length] }));
  drawRebasedChart($("cmp-chart"), { dates, series: lines });
  const [first, second] = series;
  $("cmp-rel-wrap").hidden = !second;
  if (second) {
    $("cmp-rel-title").textContent = `${first.symbol} against ${second.symbol}: above 100 means ${first.symbol} is ahead`;
    drawRebasedChart($("cmp-rel"), { dates, series: [{ label: `${first.symbol} ÷ ${second.symbol}`, values: relative(first.closes, second.closes), color: SERIES_COLORS[0] }], single: true });
  }
}

function drawCandles(priceLists, symbols) {
  // Both charts cover the same window: from the later of the two first days (or the period asked for) to the earlier
  // of the two last days. If the stocks don't overlap at all, each simply shows its own history.
  const firsts = priceLists.map((p) => p[0]?.date).filter(Boolean).sort();
  const ends = priceLists.map((p) => p[p.length - 1]?.date).filter(Boolean).sort();
  const end = ends[0];
  const periodStart = PRESETS[state.period] == null ? null : daysBefore(end, PRESETS[state.period]);
  const overlap = firsts[firsts.length - 1] <= end;
  const start = [overlap ? firsts[firsts.length - 1] : null, periodStart].filter(Boolean).sort().pop() || null;
  const panes = [["cmp-chart-a", "cmp-head-a"], ["cmp-chart-b", "cmp-head-b"]];
  panes.forEach(([chartId, headId], i) => {
    const all = priceLists[i];
    const prices = overlap ? all.filter((p) => (!start || p.date >= start) && p.date <= end) : all;
    const first = prices[0];
    const last = prices[prices.length - 1];
    const change = first && last ? (last.close / first.close - 1) * 100 : 0;
    $(headId).innerHTML = `<span class="sym">${escapeHtml(symbols[i])}</span> <span class="ohlc">${last ? money(last.close) : "-"} <span class="${change >= 0 ? "up" : "down"}">${signedPercent(change)}</span> over ${plural(prices.length, "day")} shown</span>`;
    if (prices.length) drawPriceChart($(chartId), { symbol: symbols[i], prices, visibleDays: Infinity });
  });
  linkXRanges($("cmp-chart-a"), $("cmp-chart-b"));
}

function renderFigures(summary, symbols) {
  if (summary.days < 3) {
    $("cmp-figures").innerHTML = "";
    return;
  }
  const rows = summary.rows
    .map((r) => `<tr><td><b>${escapeHtml(r.symbol)}</b></td>
      <td class="num ${r.return_pct >= 0 ? "up" : "down"}">${dash(r.return_pct, signedPercent)}</td>
      <td class="num">${dash(r.volatility_pct, percent)}</td>
      <td class="num ${r.max_drawdown_pct > 0 ? "down" : ""}">${dash(r.max_drawdown_pct, percent)}</td></tr>`)
    .join("");
  const pairs = summary.pairs
    .map((p) => `<tr><td><b>${escapeHtml(p.symbol)}</b></td>
      <td class="num">${dash(p.correlation, (v) => v.toFixed(2))}</td>
      <td class="num">${dash(p.beta, (v) => v.toFixed(2))}</td>
      <td class="num ${p.return_diff_pct >= 0 ? "up" : "down"}">${dash(p.return_diff_pct, signedPercent)}</td></tr>`)
    .join("");
  $("cmp-figures").innerHTML = `
    <h3>Over ${plural(summary.days, "shared trading day")}, ${summary.from} to ${summary.to}</h3>
    <table class="cmp-table"><thead><tr><th>Stock</th><th class="num">Return</th><th class="num">Volatility (a year)</th><th class="num">Max drawdown</th></tr></thead><tbody>${rows}</tbody></table>
    ${pairs ? `<h3>How ${escapeHtml(symbols[0])} moved against each of the others</h3>
    <table class="cmp-table"><thead><tr><th>Against</th><th class="num">Correlation</th><th class="num">Beta</th><th class="num">${escapeHtml(symbols[0])}'s return minus theirs</th></tr></thead><tbody>${pairs}</tbody></table>` : ""}`;
}

export async function renderCompare() {
  buildOptions();
  showView();
  const symbols = chosen();
  const token = ++state.draw;
  if (symbols.length < 2) {
    message(store.stocks.length < 2 ? "Add another stock first (Trade, then Import data or New practice stock) to compare." : "Pick two different stocks to compare.");
    $("cmp-note").textContent = "";
    $("cmp-figures").innerHTML = "";
    $("cmp-rebased").hidden = $("cmp-candles").hidden = true;
    return;
  }

  let lists;
  try {
    lists = await Promise.all(symbols.map(loadPrices));
  } catch (err) {
    return toast(err.message, true);
  }
  if (token !== state.draw) return; // the picks changed while loading

  const series = symbols.map((symbol, i) => ({ symbol, dates: lists[i].map((p) => p.date), closes: lists[i].map((p) => p.close) }));
  const aligned = alignSeries(series);
  const windowed = applyPreset(aligned, state.period);
  const own = series.map((s) => `${s.symbol} ${s.dates.length.toLocaleString("en-IN")}`).join(", ");
  $("cmp-note").textContent = `Prices up to the market date (${store.marketDate}), so nothing from the future shows. Stored trading days: ${own}. ${plural(aligned.dates.length, "day")} are shared by all of them; the start-at-100 view and the figures use only those.`;

  const tooFew = windowed.dates.length < 2;
  if (state.view === "rebased") {
    message(tooFew ? `${symbols.join(" and ")} share ${aligned.dates.length ? "too few" : "no"} trading days${state.period === "all" ? "" : " in this period"}, so they can't be lined up. Try a longer period or different stocks (an index imported from a file has to overlap in time with the stock).` : "");
    $("cmp-rebased").hidden = tooFew;
    if (!tooFew) drawRebased(windowed);
  } else {
    message("");
    drawCandles(lists.slice(0, 2), symbols.slice(0, 2));
  }
  renderFigures(summarise(windowed), symbols);
}

export function initCompare() {
  IDS.forEach((id, i) =>
    $(id).addEventListener("change", () => {
      state.picks[i] = $(id).value;
      state.chosenByUser[i] = true;
      renderCompare();
    }),
  );
  $("cmp-view").addEventListener("click", (e) => {
    const button = e.target.closest("button[data-view]");
    if (!button) return;
    state.view = button.dataset.view;
    renderCompare();
  });
  $("cmp-periods").addEventListener("click", (e) => {
    const button = e.target.closest("button[data-period]");
    if (!button) return;
    state.period = button.dataset.period;
    renderCompare();
  });
}
