import { $, api, money, percent, pnlClass, signedMoney, signedPercent } from "../util.js";
import { drawEquityChart } from "../chart.js";
import { store } from "../store.js";
import { themeColors } from "../theme.js";

const fmtRatio = (v) => (v == null ? "—" : v.toFixed(2));
const fmtProfitFactor = (v, wins) => (v == null ? (wins > 0 ? "∞" : "—") : v.toFixed(2));

function renderMetrics(p) {
  const t = p.trade_stats;
  const tiles = [
    ["Total return", signedPercent(p.total_return_pct), pnlClass(p.total_return_pct)],
    ["Max drawdown", percent(p.max_drawdown_pct), p.max_drawdown_pct > 0 ? "down" : ""],
    ["Sharpe ratio", fmtRatio(p.sharpe_ratio), ""],
    ["Win rate", percent(t.win_rate_pct), ""],
    ["Avg win", money(t.avg_win), "up"],
    ["Avg loss", money(t.avg_loss), t.avg_loss < 0 ? "down" : ""],
    ["Profit factor", fmtProfitFactor(t.profit_factor, t.winning_trades), ""],
    ["Closed trades", t.total_trades, ""],
  ];
  $("pf-metrics").innerHTML = tiles.map(([label, value, cls]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
}

function drawDrawdown(el, curve) {
  const c = themeColors();
  const trace = {
    type: "scatter",
    mode: "lines",
    x: curve.map((p) => p.date),
    y: curve.map((p) => p.value),
    fill: "tozeroy",
    fillcolor: c.down + "22",
    line: { color: c.down, width: 1.6 },
    hovertemplate: "%{x}<br>%{y:.2f}%<extra></extra>",
  };
  const layout = {
    margin: { l: 8, r: 50, t: 6, b: 24 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: { gridcolor: "rgba(0,0,0,0)", rangebreaks: [{ bounds: ["sat", "mon"] }], linecolor: c.line },
    yaxis: { side: "right", gridcolor: c.line, ticksuffix: "%", zeroline: false },
  };
  Plotly.react(el, [trace], layout, { displayModeBar: false, responsive: true });
}

function drawMonthly(el, monthly) {
  const c = themeColors();
  const trace = {
    type: "bar",
    x: monthly.map((m) => m.month),
    y: monthly.map((m) => m.return_pct),
    marker: { color: monthly.map((m) => (m.return_pct >= 0 ? c.up : c.down)) },
    hovertemplate: "%{x}<br>%{y:.2f}%<extra></extra>",
  };
  const layout = {
    margin: { l: 8, r: 50, t: 6, b: 24 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    xaxis: { gridcolor: "rgba(0,0,0,0)", linecolor: c.line },
    yaxis: { side: "right", gridcolor: c.line, ticksuffix: "%", zeroline: true, zerolinecolor: c.line },
  };
  Plotly.react(el, [trace], layout, { displayModeBar: false, responsive: true });
}

function drawDistribution(el, pnls) {
  const c = themeColors();
  const trace = {
    type: "histogram",
    x: pnls,
    marker: { color: c.accent, opacity: 0.85 },
    hovertemplate: "₹%{x}<br>%{y} trade(s)<extra></extra>",
  };
  const layout = {
    margin: { l: 8, r: 50, t: 6, b: 24 },
    showlegend: false,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: c.muted, size: 11 },
    bargap: 0.08,
    xaxis: { gridcolor: "rgba(0,0,0,0)", linecolor: c.line, tickprefix: "₹", zeroline: true, zerolinecolor: c.line },
    yaxis: { side: "right", gridcolor: c.line, showticklabels: false, zeroline: false },
  };
  Plotly.react(el, [trace], layout, { displayModeBar: false, responsive: true });
}

function renderStrategyTable(rows) {
  document.querySelector("#pf-strategy-table tbody").innerHTML = rows
    .map(
      (r) => `<tr>
        <td>${r.name}</td>
        <td class="num">${r.total_trades}</td>
        <td class="num">${percent(r.win_rate_pct)}</td>
        <td class="num up">${money(r.avg_win)}</td>
        <td class="num ${r.avg_loss < 0 ? "down" : ""}">${money(r.avg_loss)}</td>
        <td class="num">${fmtProfitFactor(r.profit_factor, r.winning_trades)}</td>
        <td class="num ${pnlClass(r.total_pnl)}">${signedMoney(r.total_pnl)}</td>
      </tr>`,
    )
    .join("");
}

export async function renderPerformance() {
  const p = await api("/analytics/performance");
  const hasTrades = p.trade_stats.total_trades > 0;
  $("pf-empty").hidden = hasTrades;
  $("pf-content").hidden = !hasTrades;
  if (!hasTrades) return;

  renderMetrics(p);

  if (typeof Plotly === "undefined") return;
  drawEquityChart($("pf-equity"), {
    dates: p.equity_curve.map((c) => c.date),
    values: p.equity_curve.map((c) => c.value),
    baseline: p.equity_curve.map(() => store.portfolio.starting_capital),
    valueLabel: "Portfolio",
    baselineLabel: "Starting capital",
  });
  drawDrawdown($("pf-drawdown"), p.drawdown_curve);
  drawMonthly($("pf-monthly"), p.monthly_returns);
  drawDistribution($("pf-dist"), p.trade_pnls);
  renderStrategyTable(p.by_strategy);
}
