import { $ } from "../util.js";

const INFO = {
  strategies: {
    title: "Strategies",
    phase: "Phases 4, 5 and 9",
    blurb:
      "Automated rules that generate BUY / SELL / HOLD signals. The first one is a moving-average crossover, then more indicators, then a no-code rule builder.",
    items: [
      "Moving-average crossover with adjustable fast/slow periods (Phase 4)",
      "RSI, Bollinger Bands, breakout and mean reversion (Phase 5)",
      "Signals drawn on the chart with a plain-language reason for each (Phase 4)",
      "Rule builder: IF SMA 20 crosses above SMA 50 AND RSI < 70 THEN BUY (Phase 9)",
    ],
  },
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
  journal: {
    title: "Journal",
    phase: "Phase 4 (the Why system)",
    blurb: "Every trade and signal with the reasons behind it, so you learn from decisions rather than just outcomes.",
    items: [
      "WHY DID I BUY? card: indicator values, rule that fired, stop loss, quantity",
      "Your own notes and a rating for each decision",
      "Review past trades against what the market did next",
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
