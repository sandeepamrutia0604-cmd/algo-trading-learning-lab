import { $, toast } from "./util.js";
import { hooks, loadConfigs, loadCore } from "./store.js";
import { initTheme } from "./theme.js";
import { checkHealth, initTopbar, renderTopbar } from "./topbar.js";
import { renderHome } from "./pages/home.js";
import { initTrade, renderTrade } from "./pages/trade.js";
import { renderSoon } from "./pages/soon.js";
import { initStrategies, renderStrategies } from "./pages/strategies.js";
import { renderJournal } from "./pages/journal.js";

const ROUTES = ["home", "trade", "strategies", "backtests", "compare", "journal", "learn"];
const PAGE_OF = { home: "home", trade: "trade", strategies: "strategies", journal: "journal" };

function currentRoute() {
  const route = location.hash.replace(/^#\//, "");
  return ROUTES.includes(route) ? route : "home";
}

async function renderActive() {
  const route = currentRoute();
  if (route === "home") await renderHome();
  else if (route === "trade") await renderTrade();
  else if (route === "strategies") await renderStrategies();
  else if (route === "journal") await renderJournal();
}

function showRoute() {
  const route = currentRoute();
  const page = PAGE_OF[route] || "soon";
  for (const name of ["home", "trade", "strategies", "journal", "soon"]) $(`page-${name}`).hidden = name !== page;
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
  window.addEventListener("hashchange", showRoute);
  checkHealth();
  try {
    await loadConfigs();
  } catch (err) {
    toast(err.message, true);
  }
  await showRoute();
}

boot();
