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
  {
    id: 4,
    title: "What is an indicator?",
    minutes: 6,
    summary: "Moving averages, RSI and other numbers calculated from price history.",
    blocks: [
      { h: "The idea" },
      {
        p: "A price chart is a noisy line. An **indicator** is a number, calculated from past prices (and sometimes volume), that summarises something about that line: which way it is trending, how stretched it is, or how jumpy it has been. Indicators don't see the future. They are just a different, simpler way of looking at what has already happened.",
      },
      {
        p: "Algorithms like indicators because they turn a vague feeling (\"it looks like it's going up\") into an exact number a program can test.",
      },

      { h: "Moving average (SMA)" },
      {
        p: "A **simple moving average** is the average of the last N closing prices. Each new day, the oldest price drops out of the window and the newest one comes in, so the average *moves* along with the price while smoothing out the day-to-day jumps. A 20-day SMA reacts quickly, and a 50-day SMA is slower and smoother.",
      },
      {
        example: {
          title: "A 5-day SMA, worked by hand",
          text: "The last five closes are 100, 102, 101, 103 and 104. Their total is 510, so the 5-day SMA is 510 ÷ 5 = **102**. Tomorrow the stock closes at 106. The 100 drops out and the 106 comes in: 102, 101, 103, 104, 106 total 516, so the SMA becomes **103.2**. The price jumped 2 but the average moved only 1.2. That smoothing is the point.",
        },
      },
      {
        p: "When the price (or a fast SMA) is above a slow SMA, the recent trend is up. When it is below, the trend is down. The moment a fast average crosses the slow one is called a **crossover**, and it is one of the oldest trading signals there is.",
      },

      { h: "RSI: how stretched is the price?" },
      {
        p: "The **Relative Strength Index** compares the size of recent up days with recent down days (over 14 days by default) and boils it down to a score from **0 to 100**. A common reading is that below 30 means the stock has fallen fast and may be **oversold**, and above 70 means it has risen fast and may be **overbought**. \"May be\" is doing a lot of work: in a strong trend RSI can stay above 70 for weeks.",
      },

      { h: "Bollinger Bands: how far is too far?" },
      {
        p: "Bollinger Bands draw a moving average in the middle, with an upper and lower band a few **standard deviations** above and below it. Standard deviation is just a measure of how much prices usually stray from their average. When the price pokes through the lower band, it is unusually low compared with its own recent past, and through the upper band, unusually high. The bands widen when the stock gets jumpy and tighten when it calms down.",
      },

      { h: "Volatility" },
      {
        p: "**Volatility** measures how much a price jumps around from day to day. A calm stock that moves 0.5% a day is low volatility. One that regularly moves 3% is high volatility. It says nothing about direction, only about how bumpy the ride is, and it matters a lot for risk, which comes later in this course.",
      },
      {
        note: "Indicators **lag**: they are built from the past, so they confirm a move after it has started. No indicator predicts the future, and a signal that worked on one stock or one year can fail on the next. Treat indicators as tools for describing the market, not as crystal balls.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Indicator", "A number calculated from past prices that summarises something about them."],
          ["SMA", "Simple moving average: the average of the last N closing prices."],
          ["Crossover", "When a fast average crosses above or below a slow one."],
          ["RSI", "A 0 to 100 score of how fast the price has recently risen or fallen."],
          ["Bollinger Bands", "A moving average with bands a few standard deviations either side."],
          ["Volatility", "How much the price jumps around from day to day."],
        ],
      },

      {
        tryit: {
          label: "Play with moving averages on RELIANCE",
          hint: "Practical experiment: on the chart toolbar the two SMA boxes (blue and orange) show the 20-day and 50-day averages. Change the 20 to 5 and watch the blue line hug the price. Change it to 100 and watch it go smooth and late. Notice where the fast line crosses the slow one.",
          route: "trade",
          symbol: "RELIANCE",
        },
      },
    ],
    quiz: [
      {
        q: "What is a simple moving average (SMA)?",
        options: [
          "The highest price of the last N days.",
          "The price at which a stock opened.",
          "The average of the last N closing prices.",
          "A forecast of tomorrow's price.",
        ],
        answer: 2,
        why: "An SMA averages the last N closes and moves forward one day at a time. It is built entirely from past prices, so it describes the market and doesn't forecast it.",
      },
      {
        q: "Compared with a 50-day SMA, a 20-day SMA is:",
        options: [
          "Faster to react to price changes, but noisier.",
          "Slower, but smoother.",
          "Exactly the same.",
          "Only useful for volatile stocks.",
        ],
        answer: 0,
        why: "A shorter window gives each recent day more weight, so the line follows the price closely. A longer window is smoother but slower to turn.",
      },
      {
        q: "A stock's RSI reads 82. What is the usual interpretation?",
        options: [
          "It is certain to fall tomorrow.",
          "It has been very quiet.",
          "It is a guaranteed buy.",
          "It has risen fast and may be overbought, though in a strong trend it can stay high.",
        ],
        answer: 3,
        why: "Above 70 is commonly read as overbought: the price has risen quickly. That is a warning light, not a prediction, because trending stocks can stay overbought for a long time.",
      },
      {
        q: "Why do indicators \"lag\"?",
        options: [
          "The exchange sends the data late.",
          "They are calculated from past prices, so they confirm a move after it has begun.",
          "They only update once a week.",
          "Because they ignore the closing price.",
        ],
        answer: 1,
        why: "Every indicator is a calculation on prices that have already happened, so it can only describe or confirm. That is why none of them can reliably predict what comes next.",
      },
    ],
  },

  {
    id: 5,
    title: "What is a trading strategy?",
    minutes: 6,
    summary: "Rules that turn indicators into BUY and SELL signals.",
    blocks: [
      { h: "The idea" },
      {
        p: "A **trading strategy** is a set of rules, written down exactly enough that a computer could follow them, that says when to buy and when to sell. Instead of deciding each trade on a hunch, you decide the rules in advance and let them make the calls. That is what makes it *algorithmic* trading.",
      },
      {
        p: "A strategy needs two things: an **entry rule** (when to BUY) and an **exit rule** (when to SELL). Both must be unambiguous. \"Buy when it looks strong\" is not a rule. \"Buy when the 20-day SMA crosses above the 50-day SMA\" is.",
      },

      { h: "Signals" },
      {
        p: "Each day the strategy checks its rules against the latest prices. When a rule is met, it produces a **signal**: BUY or SELL, on that day, at that price. A signal is just a message that says \"the rules say act now\". Whether anything is actually traded is a separate step. In this lab, signals are marked on the chart, and if you turn on **auto-trade** the strategy also places a paper trade at that day's close. A strategy holds one position at a time.",
      },
      {
        example: {
          title: "The classic: moving average crossover",
          text: "**Entry:** BUY when the 20-day SMA crosses above the 50-day SMA, meaning recent prices have climbed above the longer-term average. **Exit:** SELL when the 20-day SMA crosses back below the 50-day SMA. Two numbers and two rules, and a computer can follow it without any judgement.",
        },
      },

      { h: "Two big families" },
      {
        terms: [
          ["Trend following", "Bets that a move will continue: buy strength, sell weakness. MA Crossover and Breakout work this way. They do well in steady trends and badly in choppy, sideways markets."],
          ["Mean reversion", "Bets that a stretched price will snap back to normal: buy when it's unusually low, sell when it returns to average. RSI, Bollinger Bands and Mean Reversion work this way. They do well in sideways markets and badly in steady downtrends."],
        ],
      },
      {
        p: "Neither family is better. Each one fits a different kind of market, which is why every strategy in this lab lists where it **works best** and where it **struggles**.",
      },
      {
        p: "The classic trend follower's enemy is the **whipsaw**: the price wobbles around the average, the fast line crosses up, then straight back down, and each false signal costs a little money. A crossover strategy can lose small amounts over and over in a sideways market, then win big in a trend.",
      },

      { h: "Strategies in this lab" },
      {
        list: [
          "**MA Crossover**: buy when a fast average crosses above a slow one.",
          "**RSI**: buy when RSI falls below the oversold line, sell when it rises above the overbought line.",
          "**Bollinger Bands**: buy below the lower band, sell above the upper band.",
          "**Mean Reversion**: buy when the price is unusually far below its average, sell when it returns.",
          "**Breakout**: buy a new N-day high, sell a new M-day low.",
          "**Combined**: a crossover that also needs RSI, price and volatility checks to agree.",
          "**Custom rules**: build your own entry and exit rules from the indicators.",
        ],
      },
      {
        note: "A strategy that looks good when you scroll through a chart is not proven. It might just match the stretch of history you happened to look at. The next module, backtesting, is how you test it properly, and the one after that is how you protect yourself when it is wrong.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Strategy", "A set of exact rules for when to buy and sell."],
          ["Entry / exit rule", "The condition that triggers a BUY, and the one that triggers a SELL."],
          ["Signal", "A BUY or SELL message produced when a rule is met."],
          ["Auto-trade", "Letting a strategy place paper trades on its own as the market advances."],
          ["Whipsaw", "A false signal that reverses straight away and costs a little money."],
        ],
      },

      {
        tryit: {
          label: "Create a strategy on RELIANCE",
          hint: "Practical experiment: choose MA Crossover, keep the default 20 and 50 and press Create strategy, then press Run on history on its card. Look at where the BUY and SELL signals fall in the Signals table. Which ones came too late? Which were whipsaws?",
          route: "strategies",
          symbol: "RELIANCE",
        },
      },
    ],
    quiz: [
      {
        q: "Which of these is a proper entry rule for an algorithm?",
        options: [
          "Buy when the stock looks strong.",
          "Buy when the 20-day SMA crosses above the 50-day SMA.",
          "Buy whenever you feel confident.",
          "Buy low and sell high.",
        ],
        answer: 1,
        why: "A rule must be exact enough for a computer to check. The SMA crossover can be tested on any day with no judgement, while the others depend on opinion.",
      },
      {
        q: "A strategy produces a BUY signal. What does that mean in this lab?",
        options: [
          "Shares have already been bought.",
          "It guarantees a profit.",
          "The rules say to buy now. A paper trade is placed only if auto-trade is on.",
          "The market date moves forward.",
        ],
        answer: 2,
        why: "A signal is only a message that the rules were met. It is marked on the chart. A trade follows only when auto-trade is switched on for that strategy.",
      },
      {
        q: "Which kind of market is the worst for a moving average crossover strategy?",
        options: [
          "A steady, strong uptrend.",
          "A steady, strong downtrend.",
          "A rapidly rising market.",
          "A sideways, choppy market full of false crossovers.",
        ],
        answer: 3,
        why: "In a sideways market the fast average keeps crossing the slow one back and forth. Each false crossover (a whipsaw) loses a little money, and there is never a big trend to pay for them.",
      },
      {
        q: "RSI and Bollinger Band strategies buy when a price is unusually low. What are they betting on?",
        options: [
          "That the price will keep falling.",
          "That the company will pay a dividend.",
          "That the price will move back towards its average.",
          "That volume will rise.",
        ],
        answer: 2,
        why: "These are mean reversion strategies. They bet that a stretched price will return to normal. They struggle in strong downtrends, where cheap prices keep getting cheaper.",
      },
    ],
  },
  {
    id: 6,
    title: "What is backtesting?",
    minutes: 7,
    summary: "Replaying a strategy over history, and why trading costs matter.",
    blocks: [
      { h: "The idea" },
      {
        p: "Before you trust a strategy with money, even paper money, you want to know how it would have done. **Backtesting** answers that by replaying the strategy over past price history, day by day, exactly as if it had been running then: it sees only the prices up to that day, makes its BUY and SELL decisions, and a pretend account keeps score.",
      },
      {
        p: "Done properly, it's a fast and free experiment. You can test five years of trading in a few seconds instead of waiting five years.",
      },

      { h: "What a backtest tells you" },
      {
        p: "On the Backtests page you choose a strategy and a stock, set the starting capital and press Run. You get:",
      },
      {
        terms: [
          ["Final capital / Total return", "What the account ended with, and the percentage gain or loss."],
          ["Total trades, Winning, Losing", "How many completed trades there were, and how many made or lost money."],
          ["Win rate", "The percentage of trades that made money. A low win rate can still be profitable if the wins are much bigger than the losses."],
          ["Max drawdown", "The biggest fall from a peak in your account value to a later low. It measures the worst pain you would have sat through."],
          ["Equity curve", "A chart of the account value over time, drawn next to a **buy & hold** line."],
        ],
      },

      { h: "Always compare with buy and hold" },
      {
        p: "The simplest strategy of all is to buy the stock on day one and do nothing. A trading strategy has to beat that to be worth the trouble. The equity chart draws the **buy & hold** line for exactly this reason.",
      },
      {
        example: {
          title: "Made money, but still lost",
          text: "A crossover strategy turns ₹1,00,000 into ₹1,04,000 over three years: +4%. That sounds fine until you see that simply holding the stock would have grown the same money to ₹1,30,000. The strategy made money and still did far worse than doing nothing, and it took effort and risk to get there.",
        },
      },

      { h: "Why costs matter" },
      {
        p: "Every trade costs something: slippage, brokerage and taxes (you met them in Module 2). With the app's default costs switched on, a round trip, getting in and out again, costs roughly **0.35%** of the money traded. That looks small until a strategy trades often.",
      },
      {
        example: {
          title: "Death by a thousand cuts",
          text: "Suppose a strategy puts all its money into each trade and makes 40 round trips in a year. At about 0.35% each, it pays roughly **14%** of the account in costs, so it has to earn more than 14% before it makes a single rupee. Switch on **Trading costs** on the Trade page, then run the same backtest again, and watch a frequent trader's result shrink.",
        },
      },
      {
        note: "A backtest without costs is flattering. Always run it with costs on before you believe the result.",
      },

      { h: "What a backtest can't tell you" },
      {
        list: [
          "**The future.** History shows what *would have* happened, and markets change.",
          "**Everything about the strategy's odds.** One stock over one stretch of years is a small sample. A strategy can look brilliant simply because it suited that period.",
          "**Whether you've fooled yourself.** If you keep adjusting the settings until the backtest looks good, you may only be fitting the past. That trap is called overfitting, and it is the subject of Module 8.",
        ],
      },

      { h: "Key terms" },
      {
        terms: [
          ["Backtest", "Replaying a strategy over past data to see how it would have done."],
          ["Buy & hold", "Buying once and holding. The benchmark a strategy must beat."],
          ["Max drawdown", "The largest peak-to-low fall in account value."],
          ["Win rate", "The share of trades that made money."],
          ["Equity curve", "Account value over time."],
        ],
      },
      {
        example: {
          title: "Reading a drawdown",
          text: "An account grows from ₹1,00,000 to a peak of ₹1,20,000, then slides to ₹90,000 before recovering. The fall from the peak is ₹30,000, which is 30,000 ÷ 1,20,000 = **25%**. That is the max drawdown, even if the account later ends higher.",
        },
      },

      {
        tryit: {
          label: "Run a backtest on RELIANCE",
          hint: "Practical experiment: keep MA Crossover with the default 20 and 50 and press Run backtest. Compare the strategy's equity line with the Buy & hold line, and check the max drawdown. Then try a different strategy type on the same stock and see which one suited this period.",
          route: "backtests",
          symbol: "RELIANCE",
        },
      },
    ],
    quiz: [
      {
        q: "What does a backtest do?",
        options: [
          "Predicts tomorrow's price.",
          "Places real orders with your broker.",
          "Waits for a signal in the live market.",
          "Replays a strategy over past prices to see how it would have performed.",
        ],
        answer: 3,
        why: "A backtest runs the strategy's rules over historical data, day by day, with a pretend account. It reports what would have happened and doesn't predict what will.",
      },
      {
        q: "Why is the buy & hold line drawn beside a strategy's equity curve?",
        options: [
          "It's the benchmark: a strategy should beat simply buying and doing nothing.",
          "It shows the broker's fees.",
          "It marks the days the market was closed.",
          "It predicts the next signal.",
        ],
        answer: 0,
        why: "Buy & hold is the effortless alternative. A strategy that earns less than that, however profitable it looks on its own, wasn't worth running.",
      },
      {
        q: "An account rises to ₹1,20,000, falls to ₹90,000, then recovers. What is the max drawdown?",
        options: [
          "10%",
          "30%",
          "25%",
          "75%",
        ],
        answer: 2,
        why: "The fall from the peak is ₹30,000, and ₹30,000 out of the ₹1,20,000 peak is 25%. Drawdown is measured against the peak, not the starting capital.",
      },
      {
        q: "Why do trading costs hurt a strategy that trades very often more than one that trades rarely?",
        options: [
          "Costs only apply to losing trades.",
          "Each round trip pays costs, so many trades add up to a large share of the account.",
          "Brokers charge more for fast strategies.",
          "They don't. Costs are the same either way.",
        ],
        answer: 1,
        why: "Every trade pays slippage, brokerage and taxes. A strategy that trades 40 times a year pays that bill 40 times, and it has to earn more than the total just to break even.",
      },
    ],
  },

  {
    id: 7,
    title: "What is risk management?",
    minutes: 6,
    summary: "Position sizing, stop-losses and limits that protect your capital.",
    blocks: [
      { h: "The idea" },
      {
        p: "No strategy wins every time. **Risk management** is the set of rules that decides how much you can lose when it is wrong, so that a bad run hurts but doesn't end the game. Traders often say: *first survive, then profit*.",
      },
      {
        p: "The reason is arithmetic. Losses are harder to recover than they look:",
      },
      {
        terms: [
          ["Lose 10%", "You need to gain about 11% to get back to even."],
          ["Lose 20%", "You need to gain 25%."],
          ["Lose 50%", "You need to gain **100%**: the account has to double."],
        ],
      },
      {
        p: "The deeper the hole, the harder the climb. Keeping losses small is worth more than chasing big wins.",
      },

      { h: "Position sizing: how many shares?" },
      {
        p: "The most important risk decision is how much to put into one trade. A popular method is to decide how much of your account you're willing to lose if the trade goes wrong (say **2%**), and how far the price can fall before you give up on the trade (a **stop-loss**, say **5%** below your entry). The share count follows from those two choices:",
      },
      {
        example: {
          title: "The sizing formula",
          text: "shares = (account × risk %) ÷ (price × stop-loss %). With a ₹10,00,000 account, 2% risk, a stock at ₹500 and a 5% stop: you risk ₹20,000, and each share risks ₹25 (5% of ₹500), so you can buy **800 shares**. If the stop-loss triggers, you lose 800 × ₹25 = ₹20,000, which is exactly 2% of the account.",
        },
      },

      { h: "Stop-loss" },
      {
        p: "A **stop-loss** is a predefined exit: if the price falls a set percentage below your entry, you sell and accept the loss rather than hoping. In this lab, with risk management on, an auto-trade strategy's position is closed on the first day its closing price falls to or below the stop. It is a promise to yourself, enforced by the program, which is exactly why algorithms are good at it: they don't hesitate.",
      },
      {
        note: "A stop-loss limits losses but does not guarantee them. In this lab it checks closing prices, and in real markets a stock can gap down overnight and open far below your stop, so you can exit at a worse price than planned.",
      },

      { h: "Limits that spread the risk" },
      {
        p: "Two more limits stop one mistake from sinking the whole account:",
      },
      {
        list: [
          "**Max allocation per stock** (20% by default): no single stock can be more than that share of your portfolio. In the example above, 800 shares would be ₹4,00,000, which is 40% of the account, so the lab shrinks the order to **400 shares** (₹2,00,000, the 20% cap). The worst loss at the stop is then ₹10,000, or 1%.",
          "**Max open positions** (5 by default): you can hold only that many stocks at once, so you can't spread yourself too thin or take on too many bets at the same time.",
        ],
      },
      {
        p: "Spreading money across several stocks is called **diversification**. If one company has a bad year, the others cushion the blow.",
      },

      { h: "Using it in this lab" },
      {
        p: "Open the **Risk management** tab on the Trade page, tick *Enable risk management* and press Save. From then on, position sizing, the stop-loss and both limits apply to auto-trading, every manual BUY is checked against the limits, and backtests use the same rules. So you can compare a strategy with and without risk management, side by side.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Risk per trade", "The share of your account you accept losing on one trade."],
          ["Position sizing", "Deciding how many shares to buy, based on risk."],
          ["Stop-loss", "A predefined exit price that cuts a losing trade."],
          ["Allocation", "The share of your portfolio in one stock."],
          ["Diversification", "Spreading money over several stocks so one doesn't dominate."],
        ],
      },

      {
        tryit: {
          label: "Try the risk limits on TCS",
          hint: "Practical experiment: open the Risk management tab, enable it and save, and read the worked example under the settings. Then try to buy more TCS than 20% of your portfolio is worth, and read why the order is refused.",
          route: "trade",
          symbol: "TCS",
        },
      },
    ],
    quiz: [
      {
        q: "After losing 50% of an account, how much must you gain to get back to where you started?",
        options: [
          "50%",
          "100%",
          "25%",
          "75%",
        ],
        answer: 1,
        why: "If ₹1,00,000 falls to ₹50,000, you need ₹50,000 more, which is 100% of what you have left. Big losses are very hard to recover from.",
      },
      {
        q: "Account ₹1,00,000, risk 2% per trade, stop-loss 5%, share price ₹100. Before any allocation cap, how many shares does the sizing formula give?",
        options: [
          "200",
          "100",
          "400",
          "2,000",
        ],
        answer: 2,
        why: "You risk ₹2,000 (2% of ₹1,00,000). Each share risks ₹5 (5% of ₹100). ₹2,000 ÷ ₹5 = 400 shares, which is ₹40,000, so an allocation cap might then shrink it.",
      },
      {
        q: "What is the purpose of a stop-loss?",
        options: [
          "To cut a losing trade at a set point instead of hoping it recovers.",
          "To guarantee you never lose money.",
          "To buy more when the price falls.",
          "To lower your brokerage.",
        ],
        answer: 0,
        why: "A stop-loss is a predefined exit that limits how much one trade can lose. It doesn't guarantee the exit price, since a stock can gap down past it, but it stops a small loss growing into a large one.",
      },
      {
        q: "Why limit the maximum allocation per stock (20% by default)?",
        options: [
          "To reduce the number of trades.",
          "To save on charges.",
          "To make strategies trade faster.",
          "So that one bad stock can't sink the whole portfolio.",
        ],
        answer: 3,
        why: "If most of your money is in one company and it falls sharply, your whole account suffers. A cap on each stock's share, together with a limit on open positions, spreads the risk.",
      },
    ],
  },
  {
    id: 8,
    title: "What is overfitting?",
    minutes: 6,
    summary: "Why a strategy that looks perfect on past data can fail on new data.",
    blocks: [
      { h: "The idea" },
      {
        p: "Imagine a student who memorises last year's exam paper, answers and all. They'd score full marks on that paper, and fail a new one. They learned the *specific* questions, not the subject.",
      },
      {
        p: "**Overfitting** is the same mistake in trading. If you keep adjusting a strategy until it looks perfect on a stretch of history, you may be tuning it to that history's quirks and coincidences, which are **noise**, instead of to a pattern that will repeat. The backtest looks wonderful, and then the strategy meets prices it hasn't seen and falls apart.",
      },

      { h: "How it happens" },
      {
        p: "Every strategy has settings: the fast and slow averages in a crossover, the RSI levels, the stop-loss. Prices contain a lot of random wiggle, and if you try enough combinations, some will match the wiggles of the past by sheer luck.",
      },
      {
        example: {
          title: "Searching until something works",
          text: "You test 200 combinations of fast and slow moving averages on one stock. The best pair, 17 and 43, returns +40% over three years. It looks like you found something. But with 200 tries, a lucky winner was almost guaranteed even if every combination was worthless. Run 17/43 on the following year, or on a different stock, and it returns −3%. You didn't discover a pattern. You discovered which random combination fitted the past best.",
        },
      },
      {
        note: "The more settings you tune and the more variations you try, the more likely a great-looking result is luck. Trying many ideas isn't wrong, but you must test the winner on data it was *not* chosen from.",
      },

      { h: "Warning signs" },
      {
        list: [
          "**A suspiciously smooth, steep equity curve.** Real strategies have rough patches. A curve that only goes up usually means the settings were bent to fit.",
          "**Fragile settings.** If 20/50 works but 19/50 and 21/50 lose money, the result depends on an exact coincidence and probably isn't real. A genuine edge usually survives small changes to the settings.",
          "**Too many rules.** Every extra condition and filter is another knob to fit the past with.",
          "**It only works on one stock or one period.** A pattern that appears nowhere else is more likely luck.",
        ],
      },

      { h: "How to protect yourself" },
      {
        terms: [
          ["Out-of-sample test", "Build the strategy on one stretch of history, then test it, once, on a later stretch it has never seen. If it only works on the first, it was overfitted."],
          ["Test on other stocks", "Run the same settings on stocks you didn't use to choose them. A real edge tends to show up at least a little elsewhere."],
          ["Keep it simple", "Fewer settings and rules leave less room to fit noise."],
          ["Check robustness", "Nudge the settings up and down. A good strategy degrades gently. An overfitted one collapses."],
          ["Include costs", "Switch on trading costs. Many overfitted strategies trade constantly and only look good before charges."],
        ],
      },
      {
        note: "On the Backtests page you can do this directly: set the From and To dates, or press First half and Second half. Tune your settings on the first half, then run them once on the second half. Days before your From date still warm the indicators up, so the test period isn't wasted waiting for a slow average to form.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Overfitting", "Tuning a strategy so closely to past data that it fits noise instead of a real pattern."],
          ["Noise", "Random price movement that carries no repeatable pattern."],
          ["In-sample", "The data you used to build and tune the strategy."],
          ["Out-of-sample", "Fresh data the strategy has never seen. The honest test."],
          ["Robust", "Still works reasonably when settings or data change a little."],
        ],
      },

      {
        tryit: {
          label: "Hunt for the best settings, then test them elsewhere",
          hint: "Practical experiment: on RELIANCE, run MA Crossover with a few different fast and slow values (for example 10/30, 20/50, 5/20) and note which looks best. First do this on the First half of the history, then run your best pair on the Second half, which it has never seen. Does it still win? Then try it on TCS and INFY, and nudge the best pair by a day or two to see whether the result holds.",
          route: "backtests",
          symbol: "RELIANCE",
        },
      },
    ],
    quiz: [
      {
        q: "What is overfitting?",
        options: [
          "Tuning a strategy so closely to past data that it fits noise and fails on new data.",
          "Buying too many shares of one stock.",
          "Trading too rarely.",
          "A backtest that runs out of history.",
        ],
        answer: 0,
        why: "Overfitting means the strategy has learned the quirks and coincidences of the past rather than a repeatable pattern, so it looks great in the backtest and disappoints on fresh data.",
      },
      {
        q: "You try 200 settings and the best returns +40%. Why should you be cautious?",
        options: [
          "Because +40% is illegal.",
          "Because the best of 200 tries is likely to look good by luck, even if all of them are worthless.",
          "Because more settings always means a better strategy.",
          "Because costs are not included in tests.",
        ],
        answer: 1,
        why: "With enough attempts, some will fit the past by chance. The winner has to be tested on data it was not chosen from before you believe it.",
      },
      {
        q: "A strategy works with a 20/50 crossover but loses money with 19/50 and 21/50. What does this suggest?",
        options: [
          "That 20/50 is a perfect setting.",
          "That the exchange data is wrong.",
          "That you should trade it with more money.",
          "That the result is fragile and may be a coincidence, so be sceptical.",
        ],
        answer: 3,
        why: "A real edge usually survives small changes to its settings. If a one-day nudge turns it from profit to loss, the good result probably came from an exact coincidence in the data.",
      },
      {
        q: "What is an out-of-sample test?",
        options: [
          "Testing with fewer shares.",
          "Testing without any indicators.",
          "Testing on data the strategy has never seen, such as a later period or other stocks.",
          "Testing only on the days the market went up.",
        ],
        answer: 2,
        why: "Out-of-sample means fresh data that played no part in choosing the settings. It is the honest test of whether the strategy found a pattern or just memorised the past.",
      },
    ],
  },

  {
    id: 9,
    title: "What is paper trading?",
    minutes: 5,
    summary: "Practising with market data and virtual money.",
    blocks: [
      { h: "The idea" },
      {
        p: "**Paper trading** means trading with *virtual* money: you place orders, hold positions and track profit and loss exactly as you would with a real account, but nothing real is at stake. The name comes from the days when people wrote practice trades down on paper.",
      },
      {
        p: "Everything in this lab is paper trading. It is the step between \"I have an idea\" (a backtest) and \"I'll risk real money\".",
      },

      { h: "Why do it?" },
      {
        list: [
          "**Learn the mechanics** of orders, positions, costs and P&L without paying for mistakes.",
          "**Test a strategy going forward**, not just on history. Backtests can be overfitted, but a strategy that keeps working on days it hasn't seen is a much better sign.",
          "**Find the bugs.** Rules that looked fine on paper sometimes behave oddly: they trade too often, or size positions strangely. Better to find out for free.",
          "**Build a track record** and some confidence, based on evidence.",
        ],
      },

      { h: "How this lab does it" },
      {
        p: "You start with virtual cash (₹1,00,000 unless you changed it). Stocks imported from real data replay their real NSE history **one day at a time** as you press +1 day, +5 days or Play, so you see each day without knowing what comes next. Strategies with **auto-trade** switched on check every new day and place paper trades at that day's close. The Home page keeps a **practice checklist** that ticks itself off as you trade, and the Journal records every signal.",
      },
      {
        note: "Be clear about what this is: the lab replays *past* real prices, not a live feed of today's market. It is paper trading on replayed history. Connecting to live prices is something a future version could add.",
      },

      { h: "What paper trading can't teach you" },
      {
        terms: [
          ["Emotions", "Watching real money fall feels very different. Fear and greed make people break their own rules. A paper account can't recreate that."],
          ["Real fills", "In real markets orders can fill partly, fill late, or fill at worse prices when few people are trading. The lab approximates this with slippage, but it is only an approximation."],
          ["Liquidity", "Small practice orders never move the price. Large real orders can."],
          ["Discipline over time", "It is easy to follow rules when nothing is at stake."],
        ],
      },
      {
        p: "So paper trading proves a strategy's logic works, not that *you* will stick to it with real money. That gap is why the next step, if you ever take it, should start very small.",
      },

      { h: "Doing it well" },
      {
        list: [
          "**Write the plan first**: which strategy, which stock, how much risk per trade.",
          "**Turn on trading costs and risk management**, so your practice looks like the real thing.",
          "**Give it enough time.** A lucky week proves nothing. Look at many trades across different market conditions, not just a handful.",
          "**Keep notes.** Use the Journal to see why each trade happened and to review the mistakes.",
          "**Judge by the whole picture**: return, drawdown and win rate, compared with buy & hold, as in Module 6.",
        ],
      },

      { h: "Key terms" },
      {
        terms: [
          ["Paper trading", "Practising with virtual money instead of real money."],
          ["Virtual cash", "The pretend balance your paper account starts with."],
          ["Forward test", "Trading a strategy on new days it hasn't seen, as opposed to backtesting old ones."],
          ["Track record", "The recorded results of your trades over time."],
        ],
      },

      {
        tryit: {
          label: "Work through the practice checklist",
          hint: "Practical experiment: on the Home page, the Practice checklist lists four goals, such as making your first BUY and holding two different stocks. Pick a real stock like INFY, buy some, press Play for a few weeks of market days, and watch the checklist and your portfolio update.",
          route: "home",
        },
      },
    ],
    quiz: [
      {
        q: "What is paper trading?",
        options: [
          "Trading only on printed charts.",
          "Practising trading with virtual money, so mistakes cost nothing.",
          "Trading with a small amount of real money.",
          "Filing your trades for tax.",
        ],
        answer: 1,
        why: "Paper trading uses virtual money, so you can practise orders, positions and strategies without any real financial risk.",
      },
      {
        q: "Which of these can paper trading NOT teach you well?",
        options: [
          "How to place a buy order.",
          "How P&L is calculated.",
          "How you'll react when real money is falling.",
          "How a strategy's rules behave day by day.",
        ],
        answer: 2,
        why: "Fear and greed only show up when real money is at stake. Paper trading is excellent for mechanics and logic, but it can't reproduce the emotional pressure.",
      },
      {
        q: "In this lab, where do real-stock prices come from when you press Play?",
        options: [
          "A live feed of today's market.",
          "Random numbers.",
          "The broker's order book.",
          "Real historical NSE prices, replayed one day at a time.",
        ],
        answer: 3,
        why: "Imported stocks replay their real past prices day by day on the market clock. It's realistic data, but it isn't live. Only the simulated practice stocks use generated prices.",
      },
      {
        q: "A strategy makes money in your paper account for one week. What's the right conclusion?",
        options: [
          "It's too early to tell. You need many trades across different conditions.",
          "It's proven, so go live now.",
          "It will win every week from now on.",
          "Paper trading results never matter.",
        ],
        answer: 0,
        why: "A single week is a tiny sample, and luck easily explains it. Judge a strategy over many trades and different market conditions, including how deep the losses went.",
      },
    ],
  },
  {
    id: 10,
    title: "What is live algorithmic trading?",
    minutes: 6,
    summary: "What changes when real money and real brokers are involved.",
    blocks: [
      { h: "The idea" },
      {
        p: "**Live algorithmic trading** means a program places real orders, with real money, through a real broker, on its own. It is the step *after* everything in this course: you have an idea (Module 5), you backtested it with costs (Module 6), you managed its risk (Module 7), you checked you hadn't overfitted (Module 8), and you paper traded it (Module 9).",
      },
      {
        note: "This lab never places real orders. It only ever paper trades. The Upstox and Angel One connections here are **read-only market data** sources. This module explains what going live involves so you understand it, and none of it is a recommendation to trade with real money or investment advice.",
      },

      { h: "What changes when it's real" },
      {
        terms: [
          ["Real money, real emotions", "Losses hurt, and the temptation to switch the program off after a bad week, or to override it, is strong. A strategy only works if you actually let it run."],
          ["Real fills", "Orders can fill partly, fill late, or fill at worse prices than you saw, especially in thinly traded stocks or fast markets. The gap between the price you wanted and the price you got is slippage, and it is rarely kind."],
          ["Real costs", "Brokerage, taxes and other charges come out of your actual balance, every trade."],
          ["Live data", "A live feed is different from a clean historical file: it can arrive late, have gaps, or contain a bad tick. Historical prices may also be adjusted for splits and bonuses, while live ones are not."],
        ],
      },

      { h: "What can go wrong with the software" },
      {
        p: "Once a program can place orders, ordinary bugs become expensive. Things professional traders plan for:",
      },
      {
        list: [
          "**Connection failures**: the internet drops, or the broker's API is down, in the middle of a trade. Is the order placed? Do you know?",
          "**Duplicate or runaway orders**: a bug or a retry sends the same order twice, or hundreds of times.",
          "**Wrong size**: a unit mistake (shares versus rupees) buys far more than intended.",
          "**Expired access**: broker tokens and logins expire. A strategy that can't log in can't exit a position either.",
          "**Surprises**: halted stocks, circuit limits, a market holiday, a corporate action such as a split.",
        ],
      },
      {
        p: "That is why live systems have **safety limits** written into the code: a maximum order size, a maximum number of orders per day, a daily loss limit, and a **kill switch**, a way to stop everything instantly. The risk rules from Module 7 become a safety net for the software as well as for the strategy.",
      },

      { h: "Credentials and security" },
      {
        p: "A broker API key or token can move real money, so treat it like a bank password. Keep it only in a private local file or a secrets manager. Never paste it into chat, code, screenshots or a public repository, and use read-only keys wherever you can. This lab follows that rule: credentials live in a local .env file that is never committed.",
      },

      { h: "Rules and regulation" },
      {
        p: "Automated trading through a broker is regulated, and the rules differ by country and change over time. In India, for example, the market regulator and brokers have requirements around API access, such as registered or approved strategies and fixed IP addresses for order APIs. Check your broker's and the regulator's **current** rules, and understand how your trading profits are taxed, before you go anywhere near live trading.",
      },

      { h: "If you ever go live: a sensible checklist" },
      {
        list: [
          "The strategy was backtested **with costs** and tested out-of-sample.",
          "It was paper traded long enough, across different market conditions.",
          "Risk management is on, and the safety limits and a kill switch exist.",
          "You can see and monitor what the program is doing, and get alerts when something goes wrong.",
          "You start with a very small amount you can truly afford to lose, and scale up slowly, if at all.",
          "Your credentials are safe, and you know the rules and the tax treatment.",
        ],
      },
      {
        note: "Most strategies that look good on paper do not become profitable live. That is normal, and it is why this course spends nine modules on testing and risk before this one. Learning to be sceptical of your own results is the most valuable skill here.",
      },

      { h: "Key terms" },
      {
        terms: [
          ["Live trading", "Trading with real money through a real broker."],
          ["Broker API", "A programming interface a broker offers so a program can fetch data and place orders."],
          ["Kill switch", "A way to stop all trading instantly."],
          ["Safety limits", "Hard caps in the software on order size, order count and daily loss."],
          ["Latency", "The delay between a decision and the order reaching the market."],
        ],
      },

      {
        tryit: {
          label: "Review your results like a pre-live check",
          hint: "Practical experiment: open the Performance page and look at your max drawdown, win rate and the per-strategy table. If these were real rupees, would you be comfortable sitting through that drawdown? That question is the first one to answer before any real money is involved.",
          route: "performance",
        },
      },
    ],
    quiz: [
      {
        q: "Which of these is a difference between paper trading and live trading?",
        options: [
          "Strategies use different rules.",
          "Live trading doesn't use indicators.",
          "Paper trading is always more expensive.",
          "Live orders can fill at worse prices, partly, or late, and real money is at stake.",
        ],
        answer: 3,
        why: "The strategy logic can be identical, but live trading adds real fills, real costs and real emotions. That is exactly what paper trading can't fully recreate.",
      },
      {
        q: "What is a kill switch?",
        options: [
          "A button that doubles your position.",
          "A way to stop all automated trading immediately.",
          "A type of stop-loss order.",
          "A broker fee.",
        ],
        answer: 1,
        why: "A kill switch halts the program at once. Live systems need one because a bug or a bad market can otherwise keep sending orders faster than a person can react.",
      },
      {
        q: "Where should a broker API key or token be kept?",
        options: [
          "In a private local file or secrets manager, never in chat, public code or screenshots.",
          "In the strategy's source code, so it is easy to find.",
          "In a public GitHub repository, so it is backed up.",
          "In a message to a friend, in case you lose it.",
        ],
        answer: 0,
        why: "A key can move real money, so it is as sensitive as a bank password. Keep it private, use read-only keys where possible, and never commit or share it.",
      },
      {
        q: "Your strategy paper-traded well for a few weeks. What's the sensible approach to going live?",
        options: [
          "Put in all your savings to make the most of it.",
          "Skip safety limits, because it already works.",
          "Start very small with money you can afford to lose, keep risk limits and monitoring on, and scale up slowly if at all.",
          "Turn off risk management so it can earn more.",
        ],
        answer: 2,
        why: "A few good weeks are weak evidence, and live trading adds new risks. Starting small, with limits and monitoring in place, keeps a surprise from becoming a disaster.",
      },
    ],
  },
];

export const isReady = (module) => Array.isArray(module.blocks) && module.blocks.length > 0;
