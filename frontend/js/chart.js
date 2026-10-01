import { api, money } from "./util.js";
import { themeColors } from "./theme.js";

export const SMA_COLORS = { fast: "#4c8dff", slow: "#f5a524" };

const DEFAULT_VISIBLE_DAYS = 90;

export async function loadChartData(symbol, smas) {
  const query = smas.map((m) => `sma=${m.period}`).join("&");
  const [prices, indicators] = await Promise.all([
    api(`/stocks/${symbol}/prices`),
    smas.length ? api(`/stocks/${symbol}/indicators?${query}`) : { sma: {} },
  ]);
  return { prices, indicators };
}

/** Turn the SMA indicator response into the generic overlay format drawPriceChart understands. */
export function smaOverlays(smas, indicators) {
  return smas.map((m) => ({
    name: `SMA ${m.period}`,
    panel: "price",
    color: m.color,
    dash: "solid",
    width: 1.8,
    fill_to_previous: false,
    y_range: null,
    points: indicators.sma[String(m.period)] || [],
  }));
}

function priceRange(rows, pad_frac = 0.08) {
  const low = Math.min(...rows.map((p) => p.low));
  const high = Math.max(...rows.map((p) => p.high));
  const pad = (high - low) * pad_frac || high * 0.01 || 1;
  return [low - pad, high + pad];
}

/** Rescale the price/volume axes to fit whatever date window is currently zoomed in on,
 * so candles stay readable instead of flattening out over a long history. */
function attachZoomAutoscale(el, prices) {
  if (el.removeAllListeners) el.removeAllListeners("plotly_relayout");
  let busy = false;
  el.on("plotly_relayout", (ev) => {
    if (busy) return;
    if (ev["xaxis.autorange"]) {
      const [low, high] = priceRange(prices);
      const maxVol = Math.max(...prices.map((p) => p.volume), 1);
      busy = true;
      Plotly.relayout(el, { "yaxis.range": [low, high], "yaxis2.range": [0, maxVol * 1.15] }).finally(() => (busy = false));
      return;
    }
    const x0 = ev["xaxis.range[0]"];
    const x1 = ev["xaxis.range[1]"];
    if (x0 == null || x1 == null) return;
    const from = String(x0).slice(0, 10);
    const to = String(x1).slice(0, 10);
    const visible = prices.filter((p) => p.date >= from && p.date <= to);
    if (!visible.length) return;
    const [low, high] = priceRange(visible);
    const maxVol = Math.max(...visible.map((p) => p.volume), 1);
    busy = true;
    Plotly.relayout(el, { "yaxis.range": [low, high], "yaxis2.range": [0, maxVol * 1.15] }).finally(() => (busy = false));
  });
}

function signalTrace(side, list, c) {
  const buy = side === "BUY";
  return {
    type: "scatter",
    mode: "markers",
    name: `${side} signal`,
    x: list.map((s) => s.date),
    y: list.map((s) => s.price * (buy ? 0.988 : 1.012)),
    text: list.map((s) => `${side} signal at ${money(s.price)}<br>${s.strategy_name}`),
    hoverinfo: "text",
    yaxis: "y",
    marker: {
      symbol: buy ? "star-triangle-up" : "star-triangle-down",
      size: 15,
      color: buy ? c.up : c.down,
      line: { color: "#fff", width: 1 },
    },
  };
}

/**
 * Candlesticks + volume, indicator overlays, your trades (triangles) and strategy signals (stars).
 * An overlay with panel "osc" is drawn in its own panel underneath (used for RSI).
 */
export function drawPriceChart(el, { symbol, prices, overlays = [], trades = [], signals = [] }) {
  const c = themeColors();
  const dates = prices.map((p) => p.date);
  const first = dates[0];
  const last = dates[dates.length - 1];
  const inRange = (d) => d && d >= first && d <= last;
  const oscillators = overlays.filter((o) => o.panel === "osc");
  const hasOsc = oscillators.length > 0;

  const traces = [
    {
      type: "candlestick",
      name: symbol,
      x: dates,
      open: prices.map((p) => p.open),
      high: prices.map((p) => p.high),
      low: prices.map((p) => p.low),
      close: prices.map((p) => p.close),
      increasing: { line: { color: c.up }, fillcolor: c.up },
      decreasing: { line: { color: c.down }, fillcolor: c.down },
      yaxis: "y",
    },
    {
      type: "bar",
      x: dates,
      y: prices.map((p) => p.volume),
      marker: { color: prices.map((p) => (p.close >= p.open ? c.up : c.down)), opacity: 0.5 },
      yaxis: "y2",
      hoverinfo: "skip",
    },
  ];

  for (const o of overlays) {
    const osc = o.panel === "osc";
    traces.push({
      type: "scatter",
      mode: "lines",
      name: o.name,
      x: o.points.map((pt) => pt.date),
      y: o.points.map((pt) => pt.value),
      line: { color: o.color, width: o.width, dash: o.dash === "solid" ? "solid" : o.dash },
      yaxis: osc ? "y3" : "y",
      ...(o.fill_to_previous ? { fill: "tonexty", fillcolor: "rgba(138,148,163,0.13)" } : {}),
      hovertemplate: `${o.name}: ${osc ? "" : "₹"}%{y:.${osc ? 1 : 2}f}<extra></extra>`,
    });
  }

  const mine = trades.filter((t) => t.symbol === symbol && inRange(t.market_date));
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
      text: list.map((t) => `${side} ${t.quantity} @ ${money(t.price)}<br>${t.source}`),
      hoverinfo: "text",
      yaxis: "y",
      marker: { symbol: buy ? "triangle-up" : "triangle-down", size: 12, color: buy ? c.up : c.down, line: { color: "#fff", width: 1.5 } },
    });
  }

  const visibleSignals = signals.filter((s) => s.symbol === symbol && inRange(s.date));
  for (const side of ["BUY", "SELL"]) {
    const list = visibleSignals.filter((s) => s.signal === side);
    if (list.length) traces.push(signalTrace(side, list, c));
  }

  const domains = hasOsc
    ? { price: [0.42, 1], volume: [0.29, 0.38], osc: [0, 0.23] }
    : { price: [0.22, 1], volume: [0, 0.17] };
  const oscRange = oscillators.find((o) => o.y_range)?.y_range;

  // Default to the most recent window so candles stay readable on a long history;
  // scroll-to-zoom (and attachZoomAutoscale below) take it from there.
  const visible = prices.length > DEFAULT_VISIBLE_DAYS ? prices.slice(-DEFAULT_VISIBLE_DAYS) : prices;
  const xRange = prices.length > DEFAULT_VISIBLE_DAYS ? [visible[0].date, last] : null;
  const [priceLow, priceHigh] = priceRange(visible);
  const maxVol = Math.max(...visible.map((p) => p.volume), 1);

  const layout = {
    margin: { l: 6, r: 56, t: 6, b: 28 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: {
      anchor: hasOsc ? "y3" : "y2",
      rangeslider: { visible: false },
      rangebreaks: [{ bounds: ["sat", "mon"] }],
      gridcolor: c.line,
      linecolor: c.line,
      ...(xRange ? { range: xRange } : {}),
    },
    yaxis: { domain: domains.price, side: "right", gridcolor: c.line, tickprefix: "₹", zeroline: false, range: [priceLow, priceHigh], fixedrange: true },
    yaxis2: { domain: domains.volume, side: "right", showgrid: false, showticklabels: false, zeroline: false, range: [0, maxVol * 1.15], fixedrange: true },
    hovermode: "x",
  };
  if (hasOsc) {
    layout.yaxis3 = { domain: domains.osc, side: "right", gridcolor: c.line, zeroline: false, fixedrange: true, ...(oscRange ? { range: oscRange } : {}) };
  }
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true, scrollZoom: true });
  attachZoomAutoscale(el, prices);
}

/** A value-over-time line against a reference line (flat starting capital or a buy-and-hold curve). */
export function drawEquityChart(el, { dates, values, baseline, valueLabel = "Value", baselineLabel = "Baseline" }) {
  const c = themeColors();
  const traces = [
    {
      type: "scatter",
      mode: "lines",
      name: baselineLabel,
      x: dates,
      y: baseline,
      line: { color: c.muted, width: 1.2, dash: "dot" },
      hovertemplate: `${baselineLabel}: ₹%{y:,.2f}<extra></extra>`,
    },
    {
      type: "scatter",
      mode: "lines",
      name: valueLabel,
      x: dates,
      y: values,
      fill: "tonexty",
      fillcolor: c.accent + "22",
      line: { color: c.accent, width: 2 },
      hovertemplate: `${valueLabel}: ₹%{y:,.2f}<extra></extra>`,
    },
  ];
  const all = [...values, ...baseline];
  const low = Math.min(...all);
  const high = Math.max(...all);
  const pad = Math.max((high - low) * 0.15, Math.abs(high) * 0.005 || 1);
  const layout = {
    margin: { l: 8, r: 58, t: 6, b: 24 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: { gridcolor: "rgba(0,0,0,0)", rangebreaks: [{ bounds: ["sat", "mon"] }], linecolor: c.line },
    yaxis: { side: "right", gridcolor: c.line, tickprefix: "₹", tickformat: ",.0f", zeroline: false, range: [low - pad, high + pad] },
  };
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true });
}

/** Several named value-over-time lines on one chart, each with its own date axis (for
 * comparing backtests that may cover different stocks or history lengths). */
export function drawMultiLineChart(el, series) {
  const c = themeColors();
  const traces = series.map((s) => ({
    type: "scatter",
    mode: "lines",
    name: s.label,
    x: s.dates,
    y: s.values,
    line: { color: s.color, width: 2 },
    hovertemplate: `${s.label}: ₹%{y:,.2f}<extra></extra>`,
  }));
  const all = series.flatMap((s) => s.values);
  const low = Math.min(...all);
  const high = Math.max(...all);
  const pad = Math.max((high - low) * 0.12, Math.abs(high) * 0.005 || 1);
  const layout = {
    margin: { l: 8, r: 58, t: 6, b: 40 },
    showlegend: true,
    legend: { orientation: "h", font: { size: 10, color: c.muted }, y: -0.22 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: { gridcolor: "rgba(0,0,0,0)", rangebreaks: [{ bounds: ["sat", "mon"] }], linecolor: c.line },
    yaxis: { side: "right", gridcolor: c.line, tickprefix: "₹", tickformat: ",.0f", zeroline: false, range: [low - pad, high + pad] },
  };
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true });
}
