/* Monte Carlo panel on the Backtests page: re-play the open backtest's closed trades many times
 * (backend/app/engine/monte_carlo.py) and show how much of the result was luck. */

import { $, api, percent, signedPercent, toast } from "../util.js";
import { currentTheme, themeColors } from "../theme.js";

const state = { result: null, analysis: null, runId: 0, drawn: "", running: false };

/** Called whenever the Backtests page shows a result: a different result clears the old analysis. */
export function showMonteCarlo(result) {
  if (state.result !== result) {
    state.result = result;
    state.analysis = null;
    state.drawn = "";
  }
  render();
}

const wordFor = (worseThan) => (worseThan < 25 ? "a calmer ordering than most" : worseThan > 75 ? "a rougher ordering than most" : "a fairly typical ordering");

function verdict(a) {
  const f = a.final_return.percentiles;
  const d = a.max_drawdown.percentiles;
  const n = a.trade_count;
  const drawdown = `The maximum drawdown was typically ${percent(d["50"])} and exceeded ${percent(d["95"])} in about 1 run in 20. This backtest's ${percent(a.original.max_drawdown_pct)} was worse than ${a.original_drawdown_worse_than_pct.toFixed(0)}% of the simulations: ${wordFor(a.original_drawdown_worse_than_pct)}.`;
  if (a.method === "shuffle") {
    const cls = d["95"] <= 20 ? "good" : d["95"] > 40 ? "bad" : "mixed";
    return { cls, html: `<b>Same ${n} trades, ${a.simulations.toLocaleString("en-IN")} different orders.</b> The total is ${signedPercent(a.original.return_pct)} every time, because compounding doesn't care about order. What does change is the ride: the drawdown ranged from ${percent(a.max_drawdown.min)} to ${percent(a.max_drawdown.max)} (the middle 90% of runs: ${percent(d["5"])} to ${percent(d["95"])}). ${drawdown}` };
  }
  const range = `${signedPercent(f["5"])} to ${signedPercent(f["95"])}`;
  const loss = a.probability_of_loss_pct;
  const cls = f["5"] > 0 ? "good" : f["50"] <= 0 ? "bad" : "mixed";
  const lead =
    cls === "good"
      ? `Even the unluckiest 5% of resamples made money.`
      : cls === "bad"
        ? `The typical resample lost money, so a profit here would owe a lot to luck.`
        : `${loss.toFixed(0)}% of resamples lost money, so the sign of this result is not safe.`;
  return { cls, html: `<b>Resampling the same ${n} trades ${a.simulations.toLocaleString("en-IN")} times, the total return ranged from ${range} (the middle 90% of runs), with a median of ${signedPercent(f["50"])}.</b> ${lead} This backtest's ${signedPercent(a.original.return_pct)} is one draw from that spread. ${drawdown}` };
}

function metrics(a) {
  const f = a.final_return.percentiles;
  const d = a.max_drawdown.percentiles;
  const exceed20 = a.drawdown_exceeds_pct.find((row) => row.threshold === 20);
  const tiles = [["This backtest (closed trades)", signedPercent(a.original.return_pct), a.original.return_pct > 0 ? "up" : a.original.return_pct < 0 ? "down" : ""]];
  if (a.method === "bootstrap") {
    tiles.push(
      ["Median simulated return", signedPercent(f["50"]), f["50"] > 0 ? "up" : f["50"] < 0 ? "down" : ""],
      ["Middle 90% of returns", `${signedPercent(f["5"])} to ${signedPercent(f["95"])}`, ""],
      ["Chance of a loss", `${a.probability_of_loss_pct.toFixed(0)}%`, a.probability_of_loss_pct > 50 ? "down" : ""],
    );
  } else {
    tiles.push(["Total in every shuffle", signedPercent(a.original.return_pct), ""]);
  }
  tiles.push(
    ["Median max drawdown", percent(d["50"]), "down"],
    ["Bad-luck drawdown (1 in 20)", percent(d["95"]), "down"],
    ["Yours was worse than", `${a.original_drawdown_worse_than_pct.toFixed(0)}% of runs`, ""],
    ["Drawdown of 20% or more", `${exceed20 ? exceed20.pct.toFixed(0) : 0}% of runs`, exceed20 && exceed20.pct > 25 ? "down" : ""],
  );
  return tiles.map(([label, value, cls]) => `<div class="metric"><span>${label}</span><b class="${cls}">${value}</b></div>`).join("");
}

function drawFan(a) {
  const c = themeColors();
  const x = a.fan.trade_numbers;
  const b = a.fan.bands;
  const shade = (hex, alpha) => `${hex}${alpha}`;
  const band = (low, high, fill) => [
    { type: "scatter", mode: "lines", x, y: b[low], line: { width: 0 }, hoverinfo: "skip", showlegend: false },
    { type: "scatter", mode: "lines", x, y: b[high], line: { width: 0 }, fill: "tonexty", fillcolor: fill, hoverinfo: "skip", showlegend: false },
  ];
  const traces = [
    ...band("5", "95", shade(c.accent, "22")),
    ...band("25", "75", shade(c.accent, "40")),
    { type: "scatter", mode: "lines", name: "Median", x, y: b["50"], line: { color: c.muted, width: 1.5, dash: "dot" }, hovertemplate: "Median: ₹%{y:,.0f}<extra></extra>" },
    { type: "scatter", mode: "lines", name: "Your trades", x, y: a.fan.original, line: { color: c.accent, width: 2.4 }, hovertemplate: "Your actual trades: ₹%{y:,.0f}<extra></extra>" },
  ];
  Plotly.react(
    $("mc-fan"),
    traces,
    {
      margin: { l: 8, r: 62, t: 6, b: 34 },
      showlegend: false,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: c.muted, size: 11 },
      hovermode: "x",
      xaxis: { title: { text: "Trade number" }, gridcolor: c.line, zeroline: false, dtick: x.length <= 30 ? 1 : undefined },
      yaxis: { side: "right", gridcolor: c.line, tickprefix: "₹", tickformat: ",.0f", zeroline: false },
    },
    { displayModeBar: false, responsive: true },
  );
}

function drawHistogram(el, distribution, original, label, positiveIsGood) {
  const c = themeColors();
  const { edges, counts } = distribution.histogram;
  const centres = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const widths = counts.map((_, i) => edges[i + 1] - edges[i]);
  const colours = centres.map((centre) => (positiveIsGood ? (centre >= 0 ? c.up : c.down) : c.warn));
  Plotly.react(
    el,
    [{ type: "bar", x: centres, y: counts, width: widths, marker: { color: colours, opacity: 0.8 }, hovertemplate: `${label}: %{x:.1f}%<br>%{y} simulations<extra></extra>` }],
    {
      margin: { l: 40, r: 8, t: 22, b: 34 },
      showlegend: false,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: c.muted, size: 11 },
      bargap: 0.05,
      xaxis: { title: { text: `${label} (%)` }, gridcolor: c.line, zeroline: positiveIsGood, zerolinecolor: c.muted },
      yaxis: { title: { text: "simulations" }, gridcolor: c.line },
      shapes: [{ type: "line", xref: "x", yref: "paper", x0: original, x1: original, y0: 0, y1: 1, line: { color: c.accent, width: 2.4 } }],
      annotations: [{ x: original, y: 1, xref: "x", yref: "paper", text: "this backtest", showarrow: false, yanchor: "bottom", font: { color: c.accent, size: 10 } }],
    },
    { displayModeBar: false, responsive: true },
  );
}

function render() {
  const a = state.analysis;
  $("mc-results").hidden = !a;
  if (!a) return;
  const v = verdict(a);
  $("mc-verdict").className = `op-verdict ${v.cls}`;
  $("mc-verdict").innerHTML = v.html;
  $("mc-metrics").innerHTML = metrics(a);
  $("mc-note").textContent =
    `Based on ${a.trade_count} closed trades from ${a.period_start} to ${a.period_end}` +
    (a.open_trade_excluded ? " (a position still open at the end is left out)" : "") +
    (a.uses_risk ? ", with your Risk management settings" : "") +
    (a.uses_costs ? ", with trading costs" : "") +
    `. ${a.method === "shuffle" ? "Each simulation re-orders the same trades." : "Each simulation draws the same number of trades at random, with replacement, from this run's trades."} ` +
    `Drawdown is measured between closed trades, so it is a little smaller than the daily drawdown the backtest reports (${percent(a.backtest_max_drawdown_pct)}). ` +
    `Both methods assume the trades to come look like the ones so far and that one trade doesn't influence the next, which markets don't strictly honour; read the spread as a sense of scale, not a forecast.`;
  $("mc-return-wrap").hidden = a.method === "shuffle";

  if (typeof Plotly === "undefined") return;
  const key = `${state.runId}|${currentTheme()}`;
  if (state.drawn === key) return;
  state.drawn = key;
  drawFan(a);
  if (a.method === "bootstrap") drawHistogram($("mc-hist-return"), a.final_return, a.original.return_pct, "Final return", true);
  drawHistogram($("mc-hist-dd"), a.max_drawdown, a.original.max_drawdown_pct, "Max drawdown", false);
}

export function initMonteCarlo(getRequest) {
  $("mc-run").addEventListener("click", async () => {
    const request = getRequest();
    if (!request || state.running) return;
    state.running = true;
    $("mc-run").disabled = true;
    $("mc-run").textContent = "Running...";
    try {
      const analysis = await api("/backtests/monte-carlo", {
        method: "POST",
        body: JSON.stringify({ request, simulations: parseInt($("mc-sims").value, 10), method: $("mc-method").value }),
      });
      state.analysis = analysis;
      state.runId += 1;
      render();
    } catch (err) {
      toast(err.message, true);
    } finally {
      state.running = false;
      $("mc-run").disabled = false;
      $("mc-run").textContent = "Run Monte Carlo";
    }
  });
}

