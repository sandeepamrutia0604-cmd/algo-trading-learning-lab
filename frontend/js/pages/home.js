import { $, api, money, pnlClass, signedMoney, signedPercent, sparkline } from "../util.js";
import { hooks, store } from "../store.js";
import { drawEquityChart } from "../chart.js";

function renderHero() {
  const p = store.portfolio;
  $("h-value").textContent = money(p.portfolio_value);
  const ret = $("h-return");
  ret.innerHTML = `<small class="${pnlClass(p.total_pnl)}">${p.total_pnl > 0 ? "&#9650;" : p.total_pnl < 0 ? "&#9660;" : ""} ${signedPercent(p.return_pct)}</small>`;
  $("h-sub").textContent = `Started with ${money(p.starting_capital)} · Cash ${money(p.cash)} · Invested ${money(p.invested)}`;

  const chip = (label, value) =>
    `<span class="chip">${label} <b class="${pnlClass(value)}">${signedMoney(value)}</b></span>`;
  $("h-chips").innerHTML =
    chip("Realized", p.realized_pnl) + chip("Unrealized", p.unrealized_pnl) + chip("Today", p.day_pnl);
}

async function renderEquity() {
  const el = $("h-equity");
  if (typeof Plotly === "undefined") {
    el.textContent = "Chart library failed to load (check your internet connection).";
    return;
  }
  const curve = await api("/portfolio/equity-curve");
  if (curve.length < 2) {
    Plotly.purge(el);
    el.innerHTML = '<p class="empty">The equity curve appears once the market has some history.</p>';
    return;
  }
  const dates = curve.map((pt) => pt.date);
  const values = curve.map((pt) => pt.value);
  drawEquityChart(el, {
    dates,
    values,
    baseline: dates.map(() => store.portfolio.starting_capital),
    valueLabel: "Portfolio",
    baselineLabel: "Starting capital",
  });
}

function renderChecklist() {
  const trades = store.trades;
  const items = [
    ["Make your first BUY", trades.some((t) => t.side === "BUY")],
    ["Hold shares in two different stocks", store.positions.length >= 2],
    ["Sell a position to realize a profit or loss", trades.some((t) => t.side === "SELL")],
    ["Finish above your starting capital", store.portfolio.total_pnl > 0],
  ];
  const done = items.filter((i) => i[1]).length;
  $("h-progress").textContent = `${done}/${items.length}`;
  $("h-checklist").innerHTML = items
    .map(([label, ok]) => `<li class="${ok ? "done" : ""}"><i>${ok ? "&#10003;" : ""}</i><span>${label}</span></li>`)
    .join("");
}

function renderWatchlist() {
  $("h-watch").innerHTML = store.stocks
    .map((s) => {
      const change = s.previous_close ? ((s.current_price - s.previous_close) / s.previous_close) * 100 : 0;
      return `<div class="wrow">
        <div><b>${s.symbol}</b><small>${s.name}</small></div>
        ${sparkline(s.recent_closes, 74)}
        <div class="px">${money(s.current_price)}<small class="${pnlClass(change)}">${signedPercent(change)}</small></div>
        <button class="btn btn-buy" data-buy="${s.symbol}">Buy</button>
      </div>`;
    })
    .join("");
  $("h-watch").querySelectorAll("[data-buy]").forEach((btn) =>
    btn.addEventListener("click", () => {
      store.symbol = btn.dataset.buy;
      store.side = "BUY";
      hooks.navigate("trade");
    }),
  );
}

function renderRecent() {
  const trades = store.trades.slice(0, 5);
  if (!trades.length) {
    $("h-recent").innerHTML = '<p class="empty">No trades yet. Pick a stock from the watchlist to place your first paper trade.</p>';
    return;
  }
  $("h-recent").innerHTML = trades
    .map((t) => {
      const pnl =
        t.realized_pnl === null || t.realized_pnl === undefined
          ? `<span class="muted">open</span>`
          : `<b class="${pnlClass(t.realized_pnl)}">${signedMoney(t.realized_pnl)}</b>`;
      return `<div class="trade-item">
        <div><span class="side-${t.side.toLowerCase()}">${t.side}</span> ${t.quantity} ${t.symbol}
          <small>${t.market_date || "-"} · at ${money(t.price)}</small></div>
        <div>${pnl}</div>
      </div>`;
    })
    .join("");
}

export async function renderHome() {
  renderHero();
  renderChecklist();
  renderWatchlist();
  renderRecent();
  await renderEquity();
}
