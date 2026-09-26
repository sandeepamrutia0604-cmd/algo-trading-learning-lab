import { api } from "./util.js";

export const store = {
  portfolio: null,
  stocks: [],
  positions: [],
  trades: [],
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
  const [portfolio, stocks, positions, trades, status] = await Promise.all([
    api("/portfolio"),
    api("/stocks"),
    api("/positions"),
    api("/trades"),
    api("/market/status"),
  ]);
  Object.assign(store, { portfolio, stocks, positions, trades, marketDate: status.date });
  if (!stocks.some((s) => s.symbol === store.symbol) && stocks.length) store.symbol = stocks[0].symbol;
}

export async function loadConfigs() {
  const configs = await api("/market/config");
  store.configs = Object.fromEntries(configs.map((c) => [c.symbol, c]));
}

export const stockBySymbol = (symbol) => store.stocks.find((s) => s.symbol === symbol);
export const positionBySymbol = (symbol) => store.positions.find((p) => p.symbol === symbol);
