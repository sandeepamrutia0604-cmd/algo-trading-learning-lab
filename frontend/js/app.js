import { $, toast } from "./util.js";
import { hooks, loadConfigs, loadCore, loadCostSettings, loadRiskSettings, loadStrategyTypes } from "./store.js";
import { initTheme } from "./theme.js";
import { initLive } from "./live.js";
import { checkHealth, initTopbar, renderTopbar } from "./topbar.js";
import { renderHome } from "./pages/home.js";
import { initTrade, renderTrade } from "./pages/trade.js";
import { initLearn, renderLearn } from "./pages/learn.js";
import { initStrategies, renderStrategies } from "./pages/strategies.js";
import { initBacktests, renderBacktests } from "./pages/backtests.js";
import { initScanner, renderScanner } from "./pages/scanner.js";
import { initOptimise, renderOptimise } from "./pages/optimise.js";
import { renderPerformance } from "./pages/performance.js";
import { renderJournal } from "./pages/journal.js";

const ROUTES = ["home", "trade", "strategies", "scanner", "backtests", "optimise", "performance", "journal", "learn"];
const PAGE_OF = {
  home: "home",
  trade: "trade",
  strategies: "strategies",
  scanner: "scanner",
  backtests: "backtests",
  optimise: "optimise",
  performance: "performance",
  journal: "journal",
  learn: "learn",
};

function currentRoute() {
  const route = location.hash.replace(/^#\//, "").split("/")[0];
  return ROUTES.includes(route) ? route : "home";
}

async function renderActive() {
  const route = currentRoute();
  if (route === "home") await renderHome();
  else if (route === "trade") await renderTrade();
  else if (route === "strategies") await renderStrategies();
  else if (route === "scanner") await renderScanner();
  else if (route === "backtests") await renderBacktests();
  else if (route === "optimise") await renderOptimise();
  else if (route === "performance") await renderPerformance();
  else if (route === "journal") await renderJournal();
  else if (route === "learn") renderLearn();
}

function showRoute() {
  const route = currentRoute();
  const page = PAGE_OF[route];
  for (const name of ["home", "trade", "strategies", "scanner", "backtests", "optimise", "performance", "journal", "learn"]) $(`page-${name}`).hidden = name !== page;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.route === route));
  return refresh();
}

async function refresh() {
  try {
    await loadCore();
    renderTopbar();
    await renderActive();
  } catch (err) {
    toast(err.message, true);
  }
}

/** Another tab changed something: re-read what that kind of change can affect, then redraw. */
async function onLiveChange(kinds) {
  const reloads = [];
  if (kinds.has("stocks") || kinds.has("market") || kinds.has("backup") || kinds.has("reconnected")) reloads.push(loadConfigs());
  if (kinds.has("settings") || kinds.has("backup") || kinds.has("reconnected")) reloads.push(loadRiskSettings(), loadCostSettings());
  await Promise.all(reloads).catch(() => {});
  await refresh();
}

hooks.refresh = refresh;
hooks.reloadConfigs = loadConfigs;
hooks.navigate = (route) => {
  if (location.hash === `#/${route}`) refresh();
  else location.hash = `#/${route}`;
};

async function boot() {
  initTheme(() => refresh());
  initTopbar();
  initTrade();
  initStrategies();
  initBacktests();
  initScanner();
  initOptimise();
  initLearn();
  window.addEventListener("hashchange", showRoute);
  checkHealth();
  try {
    await Promise.all([loadConfigs(), loadStrategyTypes(), loadRiskSettings(), loadCostSettings()]);
  } catch (err) {
    toast(err.message, true);
  }
  await showRoute();
  initLive(onLiveChange);
}

boot();
