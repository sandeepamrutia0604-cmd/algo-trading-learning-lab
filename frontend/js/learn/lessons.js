/* Learning Mode content. Each module is data, not markup: `blocks` are rendered by pages/learn.js.
 *
 * Block types:
 *   { h: "Heading" }                         { p: "Paragraph" }
 *   { list: ["item", ...] }                  { note: "Highlighted callout" }
 *   { example: { title, text } }             { terms: [["Term", "Definition"], ...] }
 *   { tryit: { label, hint, route, symbol } }   a button that opens the app ready for an experiment
 * Text may use **bold**. A module without `blocks` is listed as "coming soon".
 */

export const MODULES = [
  {
    id: 1,
    title: "What is a stock?",
    minutes: 5,
    summary: "Ownership in a company, why prices move, and how to read one day of price data.",
    blocks: [
      { h: "The idea" },
      {
        p: "A **stock** (also called a **share**) is a small slice of ownership in a company. When a company wants to raise money, it can divide its ownership into many equal pieces and sell them. Buy one and you own a tiny part of that business: you are a **shareholder**.",
      },
      {
        p: "Companies such as Reliance, TCS and Infosys are *listed* on stock exchanges like the NSE and BSE, which is where their shares are bought and sold between investors.",
      },

      { h: "Why does the price move?" },
      {
        p: "A share's price is not set by the company. It is set by buyers and sellers on the exchange. When more people want to buy than sell, the price rises; when more want to sell than buy, it falls. Company results, news, and what investors expect about the future all push that balance around.",
      },
      {
        note: "A higher share price does not mean a better company. A ₹2,000 share and a ₹100 share tell you nothing about which business is bigger, cheaper or healthier. Pay attention to how a price *changes*, not to how large the number looks.",
      },

      { h: "Reading one day of price data" },
      {
        p: "For every trading day the exchange records five numbers. This app draws them as one **candle** on the chart:",
      },
      {
        terms: [
          ["Open", "The price of the first trade of the day."],
          ["High", "The highest price reached during the day."],
          ["Low", "The lowest price reached during the day."],
          ["Close", "The price the day ended at. This is the number most charts and indicators are built on."],
          ["Volume", "How many shares changed hands during the day."],
        ],
      },
      {
        example: {
          title: "RELIANCE on 1 October 2026",
          text: "It opened at ₹1,180.10, climbed as high as ₹1,183.90, fell as low as ₹1,160.80 and closed at ₹1,167.70, with 1,67,71,221 shares (about 1.7 crore) traded. It closed below where it opened, so that day was a **down day**: sellers won.",
        },
      },

      { h: "Real stocks and practice stocks" },
      {
        p: "This lab has two kinds of stocks. Stocks imported from real data, such as **RELIANCE** and **TCS**, replay real NSE price history one day at a time as you advance the market. **ALPHA, BETA, GAMMA and DELTA** are made-up practice stocks whose prices the simulator generates. Either way, nothing here uses real money.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Share / stock", "A unit of ownership in a company."],
          ["Shareholder", "Someone who owns shares."],
          ["Exchange", "The marketplace where shares are bought and sold, such as the NSE or BSE."],
          ["Symbol (ticker)", "The short code for a stock, such as RELIANCE or TCS."],
          ["Candle", "One day's open, high, low and close drawn as a single bar."],
        ],
      },
      {
        note: "Prices can fall as well as rise, and people do lose money buying real stocks. That is exactly why this lab uses paper money. Everything here is for learning and is not investment advice.",
      },

      {
        tryit: {
          label: "Open RELIANCE on the Trade page",
          hint: "Practical experiment: look at the O / H / L / C numbers above the chart, then click different stocks in the watchlist. Notice how a real stock's chart differs from a made-up one like ALPHA.",
          route: "trade",
          symbol: "RELIANCE",
        },
      },
    ],
  },

  { id: 2, title: "What is an order?", minutes: 5, summary: "Buying and selling, market orders, and what happens when you place one." },
  { id: 3, title: "What is a portfolio?", minutes: 5, summary: "Cash, positions, and how profit and loss are measured." },
  { id: 4, title: "What is an indicator?", minutes: 6, summary: "Moving averages, RSI and other numbers calculated from price history." },
  { id: 5, title: "What is a trading strategy?", minutes: 6, summary: "Rules that turn indicators into BUY and SELL signals." },
  { id: 6, title: "What is backtesting?", minutes: 7, summary: "Replaying a strategy over history, and why trading costs matter." },
  { id: 7, title: "What is risk management?", minutes: 6, summary: "Position sizing, stop-losses and limits that protect your capital." },
  { id: 8, title: "What is overfitting?", minutes: 6, summary: "Why a strategy that looks perfect on past data can fail on new data." },
  { id: 9, title: "What is paper trading?", minutes: 5, summary: "Practising with market data and virtual money." },
  { id: 10, title: "What is live algorithmic trading?", minutes: 6, summary: "What changes when real money and real brokers are involved." },
];

export const isReady = (module) => Array.isArray(module.blocks) && module.blocks.length > 0;
