import { api } from "./util.js";

export const store = {
  portfolio: null,
  stocks: [],
  positions: [],
  trades: [],
  strategies: [],
  strategyTypes: [],
  configs: {},
  marketDate: null,
  symbol: "ALPHA",
  side: "BUY",
};

// app.js fills these so pages can trigger a global refresh / navigation without importing app.js
export const hooks = {
  refresh: async () => {},
  navigate: () => {},
};

export async function loadCore() {
  const [portfolio, stocks, positions, trades, status, strategies] = await Promise.all([
    api("/portfolio"),
    api("/stocks"),
    api("/positions"),
    api("/trades"),
    api("/market/status"),
    api("/strategies"),
  ]);
  Object.assign(store, { portfolio, stocks, positions, trades, strategies, marketDate: status.date });
  if (!stocks.some((s) => s.symbol === store.symbol) && stocks.length) store.symbol = stocks[0].symbol;
}

export async function loadConfigs() {
  const configs = await api("/market/config");
  store.configs = Object.fromEntries(configs.map((c) => [c.symbol, c]));
}

export async function loadStrategyTypes() {
  store.strategyTypes = await api("/strategy-types");
}

export const stockBySymbol = (symbol) => store.stocks.find((s) => s.symbol === symbol);
export const positionBySymbol = (symbol) => store.positions.find((p) => p.symbol === symbol);
