import { $, api, money, pnlClass, signedMoney, signedPercent, toast } from "./util.js";
import { hooks, store } from "./store.js";

const state = { timer: null, busy: false };

export function renderTopbar() {
  const p = store.portfolio;
  if (!p) return;
  $("t-value").textContent = money(p.portfolio_value);
  $("t-cash").textContent = money(p.cash);
  $("t-invested").textContent = money(p.invested);

  const day = $("t-day");
  const dayPct = p.portfolio_value ? (p.day_pnl / (p.portfolio_value - p.day_pnl)) * 100 : 0;
  day.textContent = `${signedMoney(p.day_pnl)} (${signedPercent(dayPct)})`;
  day.className = pnlClass(p.day_pnl);

  const total = $("t-total");
  total.textContent = `${signedMoney(p.total_pnl)} (${signedPercent(p.return_pct)})`;
  total.className = pnlClass(p.total_pnl);

  $("t-date").textContent = store.marketDate
    ? new Date(store.marketDate + "T00:00:00").toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "-";
}

export async function checkHealth() {
  const el = $("status");
  try {
    const data = await api("/health");
    el.textContent = `Backend ${data.status.toUpperCase()}`;
    el.className = "status-pill ok";
  } catch (err) {
    el.textContent = "Backend unreachable";
    el.className = "status-pill error";
  }
}

async function advance(days) {
  if (state.busy) return;
  state.busy = true;
  try {
    const result = await api("/market/advance", { method: "POST", body: JSON.stringify({ days }) });
    await hooks.refresh();
    if (result.reached_end) stopPlaying();
    if (result.events && result.events.length) toast(result.events.slice(-3).join("  |  "));
  } catch (err) {
    stopPlaying();
    toast(err.message, true);
  } finally {
    state.busy = false;
  }
}

function startPlaying() {
  const interval = parseInt($("m-speed").value, 10);
  state.timer = setInterval(() => advance(1), interval);
  $("play-btn").innerHTML = "&#10074;&#10074; Pause";
}

export function stopPlaying() {
  clearInterval(state.timer);
  state.timer = null;
  $("play-btn").innerHTML = "&#9654; Play";
}

async function resetSimulation() {
  if (!confirm("Reset the simulation? This clears all trades and positions and restores the default market.")) return;
  try {
    stopPlaying();
    await api("/reset", { method: "POST" });
    toast("Simulation reset");
    await hooks.reloadConfigs();
    await hooks.refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

export function initTopbar() {
  $("adv-1").addEventListener("click", () => advance(1));
  $("adv-5").addEventListener("click", () => advance(5));
  $("play-btn").addEventListener("click", () => (state.timer ? stopPlaying() : startPlaying()));
  $("m-speed").addEventListener("change", () => {
    if (state.timer) {
      stopPlaying();
      startPlaying();
    }
  });
  $("reset-btn").addEventListener("click", resetSimulation);
}
