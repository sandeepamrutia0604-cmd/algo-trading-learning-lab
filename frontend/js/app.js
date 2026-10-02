import { $, toast } from "./util.js";
import { hooks, loadConfigs, loadCore, loadCostSettings, loadRiskSettings, loadStrategyTypes } from "./store.js";
import { initTheme } from "./theme.js";
import { checkHealth, initTopbar, renderTopbar } from "./topbar.js";
import { renderHome } from "./pages/home.js";
import { initTrade, renderTrade } from "./pages/trade.js";
import { renderSoon } from "./pages/soon.js";
import { initStrategies, renderStrategies } from "./pages/strategies.js";
import { initBacktests, renderBacktests } from "./pages/backtests.js";
import { renderPerformance } from "./pages/performance.js";
import { renderJournal } from "./pages/journal.js";

const ROUTES = ["home", "trade", "strategies", "backtests", "performance", "journal", "learn"];
const PAGE_OF = {
  home: "home",
  trade: "trade",
  strategies: "strategies",
  backtests: "backtests",
  performance: "performance",
  journal: "journal",
};

function currentRoute() {
  const route = location.hash.replace(/^#\//, "");
  return ROUTES.includes(route) ? route : "home";
}

async function renderActive() {
  const route = currentRoute();
  if (route === "home") await renderHome();
  else if (route === "trade") await renderTrade();
  else if (route === "strategies") await renderStrategies();
  else if (route === "backtests") await renderBacktests();
  else if (route === "performance") await renderPerformance();
  else if (route === "journal") await renderJournal();
}

function showRoute() {
  const route = currentRoute();
  const page = PAGE_OF[route] || "soon";
  for (const name of ["home", "trade", "strategies", "backtests", "performance", "journal", "soon"]) $(`page-${name}`).hidden = name !== page;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.route === route));
  if (page === "soon") renderSoon(route);
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
  window.addEventListener("hashchange", showRoute);
  checkHealth();
  try {
    await Promise.all([loadConfigs(), loadStrategyTypes(), loadRiskSettings(), loadCostSettings()]);
  } catch (err) {
    toast(err.message, true);
  }
  await showRoute();
}

boot();
