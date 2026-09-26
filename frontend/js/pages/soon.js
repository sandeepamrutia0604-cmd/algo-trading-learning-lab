import { $ } from "../util.js";

const INFO = {
  backtests: {
    title: "Backtests",
    phase: "Phases 6, 7 and 8",
    blurb:
      "Run a strategy over simulated history and see what would have happened. This page will use the Strategy Lab layout: rules on the left, results on the right.",
    items: [
      "KPI tiles: return, win rate, max drawdown, profit factor, Sharpe",
      "Equity curve against buy and hold, plus a drawdown chart",
      "Trade list where each row explains why the trade happened",
      "Risk settings: stop loss, position sizing, fees and slippage",
    ],
  },
  compare: {
    title: "Compare",
    phase: "Phase 10",
    blurb:
      "Put several strategies side by side on the same data. Results are shown as measurements from that backtest, not as advice.",
    items: [
      "Final capital, trades, win rate and drawdown per strategy",
      "Same dataset for every strategy so the comparison is fair",
      "Risk versus return, and why strategies behave differently in different markets",
    ],
  },
  learn: {
    title: "Learn",
    phase: "Learning Mode",
    blurb: "Short lessons with interactive exercises that use this simulator, in the order the concepts build on each other.",
    items: [
      "What is a stock, an order, a portfolio, an indicator, a strategy",
      "What is backtesting, risk management, overfitting and paper trading",
      "Each lesson: a short explanation, an example, an exercise and a quiz",
    ],
  },
};

export function renderSoon(route) {
  const info = INFO[route];
  $("soon-phase").textContent = `Planned: ${info.phase}`;
  $("soon-title").textContent = info.title;
  $("soon-blurb").textContent = info.blurb;
  $("soon-list").innerHTML = info.items.map((item) => `<li>${item}</li>`).join("");
}
