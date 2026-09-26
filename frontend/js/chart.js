import { api, money } from "./util.js";
import { themeColors } from "./theme.js";

export const SMA_COLORS = { fast: "#4c8dff", slow: "#f5a524" };

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

  const layout = {
    margin: { l: 6, r: 56, t: 6, b: 28 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: { anchor: hasOsc ? "y3" : "y2", rangeslider: { visible: false }, rangebreaks: [{ bounds: ["sat", "mon"] }], gridcolor: c.line, linecolor: c.line },
    yaxis: { domain: domains.price, side: "right", gridcolor: c.line, tickprefix: "₹", zeroline: false },
    yaxis2: { domain: domains.volume, side: "right", showgrid: false, showticklabels: false, zeroline: false },
    hovermode: "x",
  };
  if (hasOsc) {
    layout.yaxis3 = { domain: domains.osc, side: "right", gridcolor: c.line, zeroline: false, ...(oscRange ? { range: oscRange } : {}) };
  }
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true });
}
