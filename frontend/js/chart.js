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

/** Candlesticks + volume, SMA lines, your trades (triangles) and strategy signals (stars). */
export function drawPriceChart(el, { symbol, prices, indicators, smas, trades = [], signals = [] }) {
  const c = themeColors();
  const dates = prices.map((p) => p.date);
  const first = dates[0];
  const last = dates[dates.length - 1];
  const inRange = (d) => d && d >= first && d <= last;

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

  for (const m of smas) {
    const points = indicators.sma[String(m.period)] || [];
    traces.push({
      type: "scatter",
      mode: "lines",
      name: `SMA ${m.period}`,
      x: points.map((pt) => pt.date),
      y: points.map((pt) => pt.value),
      line: { color: m.color, width: 1.8 },
      yaxis: "y",
      hovertemplate: `SMA ${m.period}: ₹%{y:.2f}<extra></extra>`,
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

  const layout = {
    margin: { l: 6, r: 56, t: 6, b: 28 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: { anchor: "y2", rangeslider: { visible: false }, rangebreaks: [{ bounds: ["sat", "mon"] }], gridcolor: c.line, linecolor: c.line },
    yaxis: { domain: [0.22, 1], side: "right", gridcolor: c.line, tickprefix: "₹", zeroline: false },
    yaxis2: { domain: [0, 0.17], side: "right", showgrid: false, showticklabels: false, zeroline: false },
    hovermode: "x",
  };
  Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true });
}
