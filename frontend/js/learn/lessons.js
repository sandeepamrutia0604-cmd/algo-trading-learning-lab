/* Learning Mode content. Each module is data, not markup: `blocks` are rendered by pages/learn.js.
 *
 * Block types:
 *   { h: "Heading" }                         { p: "Paragraph" }
 *   { list: ["item", ...] }                  { note: "Highlighted callout" }
 *   { example: { title, text } }             { terms: [["Term", "Definition"], ...] }
 *   { tryit: { label, hint, route, symbol } }   a button that opens the app ready for an experiment
 * Text may use **bold** and *italic*. A module without `blocks` is listed as "coming soon".
 *
 * `quiz` (optional) is a list of { q, options: [...], answer: <index of the right option>, why }.
 * Learners can retry a question until they get it right; `why` is shown once they do.
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
    quiz: [
      {
        q: "What does owning a share of a company mean?",
        options: [
          "You have lent money to the company, and it must pay you back.",
          "You own a small part of the company.",
          "You are guaranteed a fixed return every year.",
          "You can run the company's day-to-day operations.",
        ],
        answer: 1,
        why: "A share is ownership, not a loan. There is no promised return, and owning a few shares gives you no say in daily operations.",
      },
      {
        q: "What sets the price of a share on the exchange?",
        options: [
          "The company's management, each morning.",
          "The exchange, once a week.",
          "Buyers and sellers: more buyers than sellers pushes the price up.",
          "The government.",
        ],
        answer: 2,
        why: "The price is whatever buyers and sellers are willing to trade at. When demand to buy outweighs supply to sell, the price rises, and when it is the other way round, it falls.",
      },
      {
        q: "Share X costs ₹2,000 and share Y costs ₹100. What can you conclude?",
        options: [
          "Nothing about which company is bigger, better or cheaper. The price per share alone doesn't say.",
          "X is the better company.",
          "Y is the cheaper business.",
          "X will rise faster than Y.",
        ],
        answer: 0,
        why: "A company can split its ownership into any number of shares, so the price per share says little by itself. Look at how a price changes over time, not at how big the number is.",
      },
      {
        q: "A stock opens the day at ₹1,180 and closes at ₹1,167. How would you describe that day?",
        options: [
          "An up day, because the price is above ₹1,000.",
          "A day with 1,167 shares traded.",
          "A day when the low was ₹1,180.",
          "A down day: it closed below where it opened.",
        ],
        answer: 3,
        why: "Comparing the close with the open tells you the direction of the day. Closing lower than it opened makes it a down day. Volume is a separate number, and the low can't be above the close.",
      },
      {
        q: "What does a day's volume tell you?",
        options: [
          "How volatile the price was.",
          "How many shares changed hands that day.",
          "What the price was at the start of the day.",
          "How much money the company made.",
        ],
        answer: 1,
        why: "Volume is the number of shares traded during the day. It says how active trading was, not how much the price moved or what the company earned.",
      },
    ],
  },

  {
    id: 2,
    title: "What is an order?",
    minutes: 5,
    summary: "Buying and selling, market orders, and what happens when you place one.",
    blocks: [
      { h: "The idea" },
      {
        p: "An **order** is an instruction to buy or sell a stock. You can't just take a share from the exchange: you tell it what you want, and it matches you with someone on the other side of the trade. Every order has a **side** (BUY or SELL), a **symbol** (which stock) and a **quantity** (how many shares).",
      },
      {
        p: "Buying opens or adds to a **position**: shares you now own. Selling reduces or closes it. Once a trade goes through, it is called **executed** or **filled**.",
      },

      { h: "Market orders" },
      {
        p: "The simplest kind is a **market order**: buy or sell right now at whatever the going price is. This lab uses market orders only. When you press Buy or Sell on the Trade page, the order fills immediately at the stock's current price.",
      },
      {
        p: "Real brokers also offer **limit orders** (trade only at a price you name or better) and **stop orders** (trade when the price reaches a trigger). They aren't part of this lab yet, but you will meet the idea of a stop in the risk management module.",
      },

      { h: "What an order costs" },
      {
        p: "Buying 10 shares at ₹3,000 each costs ₹30,000 plus any charges, and that money leaves your cash straight away. Selling brings cash back in. In a real market the price you get is not always exactly the price you saw, and brokers and the government take a cut. This lab can simulate three effects, which you switch on in the Trading costs tab on the Trade page:",
      },
      {
        terms: [
          ["Slippage", "You pay slightly more than the quoted price when buying, and receive slightly less when selling, because the market moves while your order is being filled."],
          ["Brokerage", "The broker's fee for carrying out the trade. It is usually a small percentage with a cap."],
          ["Taxes and charges", "Government and exchange levies, charged as a small percentage of the trade value."],
        ],
      },
      {
        example: {
          title: "Buying 10 shares of a stock quoted at ₹3,000",
          text: "With costs off, you pay ₹30,000. With the app's default costs switched on, slippage lifts your fill to about ₹3,001.50 per share (₹30,015 in all), and charges add roughly ₹39 on top, so you pay about ₹30,054. That is a cost of about 0.18% just to get in, and you pay something similar again to get out.",
        },
      },
      {
        note: "Costs look tiny on one trade, but a strategy that trades often pays them again and again. That is why the backtesting module spends time on them.",
      },

      { h: "When an order is refused" },
      {
        p: "The lab checks every order before it fills, as a real broker would:",
      },
      {
        list: [
          "**Not enough cash**: the total cost, charges included, is more than your available cash.",
          "**Not enough shares**: you can only sell shares you actually hold. Selling something you don't own (short selling) isn't allowed here.",
          "**Invalid quantity**: the number of shares must be a whole number above zero.",
          "**A risk limit**: if you have turned on risk management, an order that breaks one of your limits is refused too.",
        ],
      },

      { h: "Key terms" },
      {
        terms: [
          ["Order", "An instruction to buy or sell a stock."],
          ["Side", "BUY or SELL."],
          ["Quantity", "How many shares the order is for."],
          ["Market order", "An order that fills immediately at the current price."],
          ["Fill / execution", "The moment an order is carried out. The fill price is what you actually got."],
        ],
      },

      {
        tryit: {
          label: "Place a practice order on TCS",
          hint: "Practical experiment: choose BUY, enter a quantity of 1 and press Buy. Then look at the Trade history table: find the price, the fees and the market date of your fill. Then try to sell more shares than you own and read the message you get back.",
          route: "trade",
          symbol: "TCS",
        },
      },
    ],
    quiz: [
      {
        q: "What does a market order do?",
        options: [
          "Waits until the price reaches a level you choose.",
          "Buys or sells straight away at the current price.",
          "Only works when the market is closed.",
          "Guarantees you a profit.",
        ],
        answer: 1,
        why: "A market order trades immediately at the going price. Waiting for a chosen price is what a limit order does, and no order type guarantees a profit.",
      },
      {
        q: "You have ₹20,000 in cash. You try to buy 10 shares at ₹3,000. What happens?",
        options: [
          "It fills, and your cash goes negative.",
          "It fills for as many shares as you can afford.",
          "It is refused: the cost is more than your available cash.",
          "It waits until you have enough cash.",
        ],
        answer: 2,
        why: "The order costs ₹30,000 or more, which is more than the cash you have, so the lab refuses it. It never fills part of an order or lets cash go below zero.",
      },
      {
        q: "What is slippage?",
        options: [
          "A fee the government charges on every trade.",
          "A drop in the share price after you buy.",
          "The gap between the price you expected and the price you actually got.",
          "The time it takes the exchange to open.",
        ],
        answer: 2,
        why: "Slippage is the difference between the quoted price and your fill price, usually to your disadvantage: a little more when buying and a little less when selling. It is separate from brokerage and taxes.",
      },
      {
        q: "You own 5 shares of INFY. Can you place an order to sell 8?",
        options: [
          "Yes. The extra 3 are sold short.",
          "No. You can only sell shares you actually hold.",
          "Yes, if you have enough cash.",
          "Only on Mondays.",
        ],
        answer: 1,
        why: "This lab, like a basic share account, lets you sell only what you own. Selling shares you don't hold is called short selling, and it isn't supported here.",
      },
    ],
  },

  {
    id: 3,
    title: "What is a portfolio?",
    minutes: 5,
    summary: "Cash, positions, and how profit and loss are measured.",
    blocks: [
      { h: "The idea" },
      {
        p: "Your **portfolio** is everything you hold: the cash you haven't spent, plus the shares you own. In this lab you start with a virtual amount of cash (₹1,00,000 unless you changed it) and the portfolio value tracks how well you are doing with it.",
      },
      {
        terms: [
          ["Cash", "Money not tied up in shares. It is what you can spend on new orders."],
          ["Position", "Shares you own in one stock, for example 10 shares of TCS."],
          ["Average price", "What you paid per share on average, including any charges. If you buy at different prices, it blends them."],
          ["Market value", "What your shares are worth now: quantity times the current price."],
          ["Portfolio value", "Cash plus the market value of all your positions."],
        ],
      },

      { h: "Profit and loss (P&L)" },
      {
        p: "Profit and loss comes in two kinds, and the difference matters:",
      },
      {
        list: [
          "**Unrealized P&L** is the gain or loss on shares you **still hold**. It is on paper only and changes with every price move. It becomes real only when you sell.",
          "**Realized P&L** is the gain or loss locked in by shares you have **sold**. It no longer changes.",
        ],
      },
      {
        p: "**Total P&L** is the two added together, and **return %** is total P&L as a percentage of the capital you started with. **Day P&L** is how much your holdings moved since the previous day's close.",
      },
      {
        example: {
          title: "Starting with ₹1,00,000 (costs ignored to keep it simple)",
          text: "**1.** You buy 10 shares at ₹3,000. Cash falls to ₹70,000 and you hold ₹30,000 of shares. Portfolio value: ₹1,00,000, unchanged, since you only swapped cash for shares. **2.** The price rises to ₹3,100. Your shares are worth ₹31,000, so unrealized P&L is +₹1,000 and portfolio value is ₹1,01,000. **3.** You sell 4 shares at ₹3,100. That brings in ₹12,400 and locks in a realized profit of ₹400 (₹100 per share). Cash is now ₹82,400. **4.** You still hold 6 shares worth ₹18,600, with an unrealized profit of ₹600. Total P&L is ₹400 + ₹600 = ₹1,000 and portfolio value is still ₹1,01,000. Selling didn't change your total; it just turned part of it from paper into real.",
        },
      },
      {
        note: "Buying never changes your portfolio value by itself. Only price moves, and charges, do. With costs switched on, a new position starts slightly negative because you have paid charges to get in.",
      },

      { h: "Why this matters for algorithms" },
      {
        p: "Every strategy you build later is judged by what it does to these numbers: total return, how deep the portfolio value falls from its highest point (called **drawdown**), and how many trades won. The Performance page draws your portfolio value over time as an **equity curve**. Learning to read the portfolio is learning to read the scoreboard.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Portfolio", "Your cash plus all the shares you hold."],
          ["Unrealized P&L", "Profit or loss on shares you still own."],
          ["Realized P&L", "Profit or loss locked in by selling."],
          ["Return %", "Total P&L divided by your starting capital."],
          ["Equity curve", "A chart of portfolio value over time."],
        ],
      },

      {
        tryit: {
          label: "Check your portfolio on the Trade page",
          hint: "Practical experiment: look at the Cash, Invested and Portfolio value boxes at the top, then buy a few shares. Notice that cash drops by exactly what you spent while portfolio value barely moves. Then press Play for a few days and watch the Unrealized P&L column change.",
          route: "trade",
          symbol: "TCS",
        },
      },
    ],
    quiz: [
      {
        q: "You have ₹1,00,000 in cash and buy ₹30,000 of shares (ignoring charges). What is your portfolio value straight afterwards?",
        options: [
          "₹70,000",
          "₹1,00,000",
          "₹1,30,000",
          "₹30,000",
        ],
        answer: 1,
        why: "You only swapped cash for shares: ₹70,000 of cash plus ₹30,000 of shares is still ₹1,00,000. Portfolio value changes when prices move, not when you buy.",
      },
      {
        q: "You hold shares that have risen in price, but you haven't sold them. The gain is called:",
        options: [
          "Realized P&L",
          "Slippage",
          "Unrealized P&L",
          "Brokerage",
        ],
        answer: 2,
        why: "A gain on shares you still hold is unrealized: it exists only on paper and can still shrink. It becomes realized when you sell.",
      },
      {
        q: "You buy 10 shares at ₹3,000, then 10 more at ₹3,200. What is your average price?",
        options: [
          "₹3,000",
          "₹3,200",
          "₹3,100",
          "₹6,200",
        ],
        answer: 2,
        why: "You paid ₹30,000 plus ₹32,000 for 20 shares, which is ₹62,000, so the average is ₹3,100 per share.",
      },
      {
        q: "Your realized P&L is ₹400 and your unrealized P&L is ₹600. What is your total P&L?",
        options: [
          "₹200",
          "₹400",
          "₹600",
          "₹1,000",
        ],
        answer: 3,
        why: "Total P&L is realized plus unrealized: ₹400 + ₹600 = ₹1,000.",
      },
    ],
  },
  { id: 4, title: "What is an indicator?", minutes: 6, summary: "Moving averages, RSI and other numbers calculated from price history." },
  { id: 5, title: "What is a trading strategy?", minutes: 6, summary: "Rules that turn indicators into BUY and SELL signals." },
  { id: 6, title: "What is backtesting?", minutes: 7, summary: "Replaying a strategy over history, and why trading costs matter." },
  { id: 7, title: "What is risk management?", minutes: 6, summary: "Position sizing, stop-losses and limits that protect your capital." },
  { id: 8, title: "What is overfitting?", minutes: 6, summary: "Why a strategy that looks perfect on past data can fail on new data." },
  { id: 9, title: "What is paper trading?", minutes: 5, summary: "Practising with market data and virtual money." },
  { id: 10, title: "What is live algorithmic trading?", minutes: 6, summary: "What changes when real money and real brokers are involved." },
];

export const isReady = (module) => Array.isArray(module.blocks) && module.blocks.length > 0;
