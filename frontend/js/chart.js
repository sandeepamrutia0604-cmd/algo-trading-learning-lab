import { api, money } from "./util.js";
import { themeColors } from "./theme.js";
import { reachableLevelPrices } from "./levels.js";

export const SMA_COLORS = { fast: "#4c8dff", slow: "#f5a524" };
/** The colours of the lines when several things share one chart (compared backtests, compared stocks). */
export const SERIES_COLORS = ["#4c8dff", "#f5a524", "#a78bfa", "#26a69a", "#ef5350", "#8a94a3"];

const DEFAULT_VISIBLE_DAYS = 90;

/** `full` returns the whole stored history instead of only what the market clock has reached
 *  -- for backtests, which replay all of it. */
export async function loadChartData(symbol, smas, { full = false } = {}) {
  const query = smas.map((m) => `sma=${m.period}`).join("&");
  const [prices, indicators] = await Promise.all([
    api(`/stocks/${symbol}/prices${full ? "?full=true" : ""}`),
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

/** The price axis range for `rows`, with room for any `extra` prices (the lines of a position's levels). */
function priceRange(rows, pad_frac = 0.08, extra = []) {
  const low = Math.min(...rows.map((p) => p.low), ...extra);
  const high = Math.max(...rows.map((p) => p.high), ...extra);
  const pad = (high - low) * pad_frac || high * 0.01 || 1;
  return [low - pad, high + pad];
}

/** Rescale the price/volume axes to fit whatever date window is currently zoomed in on,
 * so candles stay readable instead of flattening out over a long history. */
function attachZoomAutoscale(el, prices, extra = []) {
  if (el.removeAllListeners) el.removeAllListeners("plotly_relayout");
  let busy = false;
  el.on("plotly_relayout", (ev) => {
    if (busy) return;
    if (ev["xaxis.autorange"]) {
      const [low, high] = priceRange(prices, 0.08, extra);
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
    const [low, high] = priceRange(visible, 0.08, extra);
    const maxVol = Math.max(...visible.map((p) => p.volume), 1);
    busy = true;
    Plotly.relayout(el, { "yaxis.range": [low, high], "yaxis2.range": [0, maxVol * 1.15] }).finally(() => (busy = false));
  });
}

const compactVolume = (v) => (v >= 1e7 ? `${(v / 1e7).toFixed(2)} Cr` : v >= 1e5 ? `${(v / 1e5).toFixed(2)} L` : Math.round(v).toLocaleString("en-IN"));

/**
 * A horizontal crosshair line with a value tag on the right-hand axis, following the mouse in
 * the price, volume and indicator panels. (The vertical line is Plotly's own x spike, which
 * knows how to skip weekends; Plotly has no equivalent for a free-moving horizontal line.)
 * Reads the live axis ranges on every move, so it stays right after zooming.
 */
function attachCrosshair(el) {
  if (el._crosshair) {
    // Plotly may have rebuilt the container's contents; put the overlay back if so.
    if (!el._crosshair.line.isConnected) el.append(el._crosshair.line, el._crosshair.tag);
    return;
  }
  const line = document.createElement("div");
  const tag = document.createElement("div");
  line.className = "crosshair-h";
  tag.className = "crosshair-tag";
  el.append(line, tag);
  el._crosshair = { line, tag };

  const hide = () => {
    line.style.display = "none";
    tag.style.display = "none";
  };
  el.addEventListener("mouseleave", hide);
  el.addEventListener("mousemove", (ev) => {
    const layout = el._fullLayout;
    if (!layout || !layout.xaxis) return hide();
    const box = el.getBoundingClientRect();
    const x = ev.clientX - box.left;
    const y = ev.clientY - box.top;
    const xa = layout.xaxis;
    if (x < xa._offset || x > xa._offset + xa._length) return hide();

    for (const name of ["yaxis", "yaxis2", "yaxis3"]) {
      const ya = layout[name];
      if (!ya || !ya.range || y < ya._offset || y > ya._offset + ya._length) continue;
      const share = (ya._offset + ya._length - y) / ya._length;
      const value = ya.range[0] + share * (ya.range[1] - ya.range[0]);
      line.style.cssText = `display:block;left:${xa._offset}px;width:${xa._length}px;top:${y}px`;
      tag.style.cssText = `display:block;left:${xa._offset + xa._length + 2}px;top:${y}px`;
      tag.textContent = name === "yaxis" ? money(value) : name === "yaxis2" ? compactVolume(value) : value.toFixed(1);
      return;
    }
    hide();
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
 * Horizontal lines for a position's entry, stop-loss and take-profit (see levels.js), with the
 * space between the entry and each exit tinted: red for what you stand to lose, green for what you
 * stand to make. A `preview` level (from an order not yet placed) is drawn dotted.
 * Each level is { kind: "entry"|"stop"|"target"|"alert", price, label, preview }. An alert is a dotted
 * line in the warning colour, with no tint.
 */
function levelDecorations(levels, c) {
  const colour = { entry: c.accent, stop: c.down, target: c.up, alert: c.warn };
  const shapes = [];
  const annotations = [];
  const entry = levels.find((l) => l.kind === "entry");
  for (const l of levels) {
    if (entry && l.kind !== "entry" && l.kind !== "alert") {
      shapes.push({
        type: "rect", xref: "paper", x0: 0, x1: 1, yref: "y", y0: entry.price, y1: l.price,
        fillcolor: colour[l.kind], opacity: l.preview ? 0.05 : 0.09, line: { width: 0 }, layer: "below",
      });
    }
  }
  for (const l of levels) {
    shapes.push({
      type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: l.price, y1: l.price,
      line: { color: colour[l.kind], width: 1.4, dash: l.preview || l.kind === "alert" ? "dot" : "dash" },
    });
    annotations.push({
      xref: "paper", x: 0.005, xanchor: "left", yref: "y", y: l.price, yanchor: l.kind === "stop" ? "top" : "bottom",
      text: l.label, showarrow: false, align: "left", borderpad: 2,
      font: { size: 11, color: colour[l.kind] }, bgcolor: c.panel, opacity: 0.92,
    });
  }
  return { shapes, annotations };
}

/**
 * Candlesticks + volume, indicator overlays, your trades (triangles) and strategy signals (stars).
 * An overlay with panel "osc" is drawn in its own panel underneath (used for RSI).
 * `levels` adds entry / stop-loss / take-profit lines (see levelDecorations).
 * `visibleDays` is how many of the latest days show at first (the rest is a scroll or zoom away); pass
 * Infinity to show every candle given.
 */
export function drawPriceChart(el, { symbol, prices, overlays = [], trades = [], signals = [], levels = [], visibleDays = DEFAULT_VISIBLE_DAYS }) {
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
  const visible = prices.length > visibleDays ? prices.slice(-visibleDays) : prices;
  const xRange = prices.length > visibleDays ? [visible[0].date, last] : null;
  const levelPrices = reachableLevelPrices(levels, last_close(prices));
  const [priceLow, priceHigh] = priceRange(visible, 0.08, levelPrices);
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
      showspikes: true,
      spikemode: "across",
      spikesnap: "cursor",
      spikecolor: c.muted,
      spikethickness: 1,
      spikedash: "dot",
      ...(xRange ? { range: xRange } : {}),
    },
    yaxis: { domain: domains.price, side: "right", gridcolor: c.line, tickprefix: "₹", zeroline: false, range: [priceLow, priceHigh], fixedrange: true },
    yaxis2: { domain: domains.volume, side: "right", showgrid: false, showticklabels: false, zeroline: false, range: [0, maxVol * 1.15], fixedrange: true },
    hovermode: "x",
    ...levelDecorations(levels.filter((l) => levelPrices.includes(l.price)), c),
  };
  if (hasOsc) {
    layout.yaxis3 = { domain: domains.osc, side: "right", gridcolor: c.line, zeroline: false, fixedrange: true, ...(oscRange ? { range: oscRange } : {}) };
  }
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true, scrollZoom: true });
  attachZoomAutoscale(el, prices, levelPrices);
  attachCrosshair(el);
}

const last_close = (prices) => (prices.length ? prices[prices.length - 1].close : 1);

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

/**
 * Several stocks on one chart, each rebased so it starts at 100 (see compare.js), so what is compared is how
 * much each moved, not what a share costs. A dashed line marks 100; the hover shows each line's value and the
 * change from the start. With `single`, one line is drawn with a tinted fill down to 100 (used for "A against B").
 * series: [{ label, values, color }], all on the same `dates`.
 */
export function drawRebasedChart(el, { dates, series, single = false }) {
  const c = themeColors();
  const traces = series.map((s) => ({
    type: "scatter",
    mode: "lines",
    name: s.label,
    x: dates,
    y: s.values,
    customdata: s.values.map((v) => v - 100),
    line: { color: s.color, width: 2 },
    hovertemplate: `${s.label}: %{y:.1f} (%{customdata:+.1f}%)<extra></extra>`,
  }));
  if (single) {
    traces.unshift({ type: "scatter", mode: "lines", x: dates, y: dates.map(() => 100), line: { width: 0 }, hoverinfo: "skip", showlegend: false });
    traces[1].fill = "tonexty";
    traces[1].fillcolor = series[0].color + "22";
  }
  const all = series.flatMap((s) => s.values).filter(Number.isFinite);
  const low = Math.min(...all, 100);
  const high = Math.max(...all, 100);
  const pad = Math.max((high - low) * 0.12, 1);
  const layout = {
    margin: { l: 8, r: 46, t: 6, b: single ? 24 : 40 },
    showlegend: !single,
    legend: { orientation: "h", font: { size: 11, color: c.muted }, y: -0.12 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    hovermode: "x unified",
    xaxis: { gridcolor: "rgba(0,0,0,0)", rangebreaks: [{ bounds: ["sat", "mon"] }], linecolor: c.line, showspikes: true, spikemode: "across", spikecolor: c.muted, spikethickness: 1, spikedash: "dot" },
    yaxis: { side: "right", gridcolor: c.line, tickformat: ".0f", zeroline: false, range: [low - pad, high + pad] },
    shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: 100, y1: 100, line: { color: c.muted, width: 1, dash: "dash" } }],
  };
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true });
}

/**
 * Make two charts that share a date axis zoom and pan together. Call it after both are drawn (drawPriceChart
 * replaces a chart's listeners each time it draws). A change is only copied when the other chart isn't already
 * showing that range, so the two never ping-pong.
 */
export function linkXRanges(elA, elB) {
  const parse = (value) => Date.parse(String(value).replace(" ", "T") + (String(value).length <= 10 ? "T00:00:00Z" : "Z"));
  const same = (range, other) => other && Math.abs(parse(range[0]) - parse(other[0])) < 1000 && Math.abs(parse(range[1]) - parse(other[1])) < 1000;
  const follow = (from, to) =>
    from.on("plotly_relayout", (ev) => {
      const target = to._fullLayout && to._fullLayout.xaxis;
      if (!target) return;
      if (ev["xaxis.autorange"]) {
        if (target.autorange !== true) Plotly.relayout(to, { "xaxis.autorange": true });
        return;
      }
      // A drag or scroll reports "xaxis.range[0]" and "[1]"; a program setting the whole range reports "xaxis.range".
      const [lo, hi] = ev["xaxis.range"] || [ev["xaxis.range[0]"], ev["xaxis.range[1]"]];
      if (lo == null || hi == null || same([lo, hi], target.range)) return;
      // Written the way a drag reports it, so the other chart's own price-axis refit (attachZoomAutoscale) runs too.
      Plotly.relayout(to, { "xaxis.range[0]": lo, "xaxis.range[1]": hi });
    });
  follow(elA, elB);
  follow(elB, elA);
}
