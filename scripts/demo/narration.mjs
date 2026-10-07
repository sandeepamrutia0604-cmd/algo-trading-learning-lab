// What the voice says during the tour, one line per caption (the keys are used in record.mjs).
// Plain ASCII and spelled-out numbers on purpose: the speech voices read "Rs 1,00,000" and "P&L" badly.
// Edit a line here and record again; the scene waits for its line to finish, so the length is free.

export const NARRATION = {
  intro:
    "This is the Algo Trading Learning Lab. It is a practice lab for algorithmic trading, and it uses paper money only. Nothing here is real money, and nothing here is advice.",
  home: "Home. You start with a paper portfolio of one lakh rupees, a practice checklist, and a guided course.",
  learn:
    "Learn. There are ten short lessons with quizzes, from what is a stock, all the way to going live. Each lesson ends with a Try it button that opens the app, ready for the experiment.",
  lesson:
    "The lessons use plain language and worked examples. This one covers risk: position sizing, stop losses, and take profits.",
  scanner:
    "The scanner asks one question: which stocks is a strategy signalling today? It only uses what has happened by the market date, so there is no peeking at the future.",
  scannerBuy: "There is a buy signal today. Let's take a look at it.",
  trade: "On the Trade page you get candlesticks, moving averages, a watchlist, and an order ticket.",
  position:
    "This open position already has its entry, stop loss and take profit drawn on the chart, with what each one would make or lose.",
  ticket:
    "For a new order, I set a stop loss and a take profit. The chart previews them, and the ticket shows the money at risk and the reward.",
  bought: "Bought. The levels now belong to the position.",
  advance: "Now let the market run, one day at a time. Each day's low and high are checked against my levels.",
  exit:
    "An exit fired by itself. If a stock opens beyond a level, the order fills at the open, and a day that touches both levels takes the stop.",
  dataQuality:
    "Data quality catches what quietly fools a backtest. Here it found a half price day that looks like an unadjusted stock split, and ten missing days.",
  strategies:
    "Strategies. There are six built-in types, or you can build your own rules. Each one marks its signals on the chart.",
  backtests: "A backtest replays history with a strategy, including trading costs and realistic next day fills.",
  metrics:
    "It reports much more than the return: Sharpe and Sortino ratios, the worst fall, how long it lasted, and how a simple buy and hold compares.",
  monteCarlo: "Monte Carlo reshuffles the trades thousands of times, to ask how much of the result was luck.",
  optimise: "The optimiser finds the best settings on a training period, then tests them on data it has never seen.",
  overfit:
    "A big drop from training to test is the signature of overfitting: settings fitted to noise, not to a real pattern.",
  performance: "Performance and Journal. Every paper trade, with drawdown, win rate, and a monthly breakdown.",
  outro:
    "Paper money, real lessons. The whole project is on GitHub, and it is all paper trading, not investment advice.",
};
