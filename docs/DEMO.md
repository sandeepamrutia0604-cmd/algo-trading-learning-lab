# Showing the Algo Trading Learning Lab

How to demo the app to friends and colleagues, live or on video. Nothing here uses real money, a broker
login or your real data: the demo runs on a database built from the app's own **simulated** stocks.

## 1. Set up the demo (two minutes)

Build the demo database once (it never touches your real one), then start the app on it:

```bash
python scripts/demo_setup.py       # writes data/demo.db (use .venv\Scripts\python.exe if needed)
scripts\start_demo.bat             # opens http://127.0.0.1:8001 on the demo database
```

What the demo contains: about three years of simulated history for ALPHA, BETA, GAMMA and DELTA, a practice
stock (ZETA), a sample file-imported stock with deliberate data problems (BADDATA), three saved strategies, a few
finished paper trades, one open position protected by a stop-loss and take-profit, and trading costs switched on.
The market date is chosen so the Scanner has a BUY signal waiting.

To start over, close the app and run `demo_setup.py` again. Your real data lives in `data/algo_trading.db` and is
never read or changed by any of this.

## 2. The pitch in one breath

> "It's a practice lab for algorithmic trading, using pretend money. You write or pick a rule for when to buy and
> sell, test it on history, and the app tries hard to show you whether the result was skill or luck, because most
> beginners' backtests are luck."

Three ideas to keep coming back to: **paper money only**, **explain everything in plain language**, and **make
overfitting visible**.

## 3. Live demo script (about 7 minutes)

| Time | Page | Do | Say |
|---|---|---|---|
| 0:00 | Home | Point at the portfolio, checklist and course card. | "Paper portfolio of ₹1,00,000. Nothing here is real money." |
| 0:30 | Learn | Open Module 7 (risk) and scroll a little. | "Ten short lessons with quizzes. Each ends with a Try it button that opens the app ready for the experiment." |
| 1:15 | Scanner | Choose **Breakout**. Point at the green BUY row. | "Which stocks is this strategy signalling today? It only uses what has happened by the market date, so no peeking at the future." Click **Open** on the BUY. |
| 2:00 | Trade | Show BETA's lines on the chart, then pick the scanner's stock. Type a quantity, tick Stop-loss (1%) and Take-profit (2%). | "The chart previews where the stop and target sit, and the ticket shows the money at risk and the reward." Press **Buy**. |
| 3:15 | Top bar | Press **+1 day** until the exit fires. | "The market moves one day at a time and each day's low and high are checked against your levels. A gap fills at the open, and a day that touches both takes the stop." Show the Trades tab. |
| 4:15 | Trade → Data quality | Click **BADDATA**. | "Bad prices rarely look bad. This half-price day looks like an unadjusted stock split; a backtest would trade around it as if it were real." |
| 4:45 | Backtests | BETA, MA Crossover, 200 shares, **Run**. Scroll to the metrics. | "More than the return: Sharpe, drawdown, how long it was under water, and how it compares with just buying and holding." |
| 5:30 | Backtests → Monte Carlo | **Run Monte Carlo**. | "It reshuffles the trades thousands of times to ask how much of the result was luck." |
| 6:00 | Optimise | ALPHA, **Run optimisation**. Read the red verdict aloud. | "It finds the best settings on a training period, then tests them on data they have never seen. ALPHA is a random walk, so there is nothing real to find, and the verdict says so. That drop is overfitting." |
| 6:45 | Performance | Glance at it. | "Every paper trade, drawdown and win rate land here." |

**Why the Optimise step matters most.** It is the point of the whole app. Slow down there.

## 4. Questions you will be asked

- **"Is this real money?"** No. Paper trading only; there is no broker connection that can place an order.
- **"Does it predict stocks?"** No. It teaches how to test an idea and how to avoid fooling yourself. The demo stocks
  are simulated, so no strategy has a real edge in them, which is exactly why the overfitting demo works.
- **"Why simulated stocks?"** So anyone can run it with no account or data licence. It can also import real daily
  history from a CSV file, Upstox or Angel One (read-only data; it never calls an order endpoint).
- **"What is it built with?"** Python (FastAPI, SQLAlchemy, SQLite), plain JavaScript and Plotly. No framework, no
  build step. More than 800 automated tests.
- **"Can I try it?"** It runs on your own computer. It is single-user by design, with no login, and is not set up to be
  put on the internet.
- **"What would you add next?"** Price alerts, side-by-side charts, order-level stops inside backtests, portfolio-level backtests.

## 5. If something goes wrong

- **The page is blank or says "-"** for a few seconds after start: wait, it is loading. If it persists, check the
  terminal running the app for an error.
- **The market is somewhere odd** after you have been playing: stop the app and run `demo_setup.py` again.
- **A backtest or optimiser run is slow:** the optimiser tries up to a few hundred combinations; 56 (the default here)
  takes a couple of seconds.
- **You pressed Reset:** that replays the market from its start with only 60 days of history, which is too short for
  backtests. Rebuild the demo database.

## 6. The video and the README screenshots

Both are recorded by a script that plays the tour by itself in Chrome, on a throwaway copy of the demo database, so
every run is identical and your real data is safe. It needs only Node 22+ and Chrome or Edge (nothing to install).

```bash
python scripts/demo_setup.py                              # once, or after the app changes
node scripts/demo/record.mjs --video docs/demo/algo-lab-demo.webm             # silent, captions only: about 3.5 minutes
node scripts/demo/record.mjs --video docs/demo/algo-lab-demo-narrated.webm --narrate   # with a spoken narration: about 5 minutes
node scripts/demo/record.mjs --shots docs/images                              # the README screenshots
```

A Chrome window opens and runs the tour. **Leave the mouse and keyboard alone until it closes**, and keep the window
uncovered. The video is 1280x720 (YouTube shows it at 1080p) with on-screen captions; the screenshots are 1600x900. The tour takes fifteen screenshots and the README uses nine of them, so delete the others after a run
(or add them to the README). The script prints YouTube chapter markers when a video finishes. The tour itself is
`scripts/demo/record.mjs` (the steps and captions), so changing the story means editing that file and recording again.

**Narration.** With `--narrate` the video also has a spoken track, made from `scripts/demo/narration.mjs` (one line per
caption). Each scene waits for its line to finish, so the narrated video is longer than the silent one. To change
what is said, edit `narration.mjs` and record again. There are two voices:

- **Kokoro** (the default when it is set up): a free AI voice that runs on your computer, with no account and no
  internet once installed. It sounds far more natural. Pick another voice with `--voice` (for example `am_michael`,
  male, or `bf_emma`, British) and change the pace with `--speed 0.95`.
- **The voices built into Windows** (used when Kokoro is not set up, or with `--engine windows`): needs no install, but
  they are plainly synthetic. The default is *Microsoft Zira*; add `--voice "Microsoft David Desktop"` for the other
  one, or `--rate 0` to speak a little faster (the default is `-1`; the range is -10 to 10).

### Setting up Kokoro (once, about 350 MB)

Kokoro lives in its own folder, `C:\Users\<you>\algo-kokoro` (override with the `KOKORO_HOME` environment variable),
outside the project, so nothing is added to the app's own Python environment. In PowerShell:

```powershell
$d = "$HOME\algo-kokoro"
New-Item -ItemType Directory -Force $d | Out-Null
python -m venv "$d\venv"
& "$d\venv\Scripts\python.exe" -m pip install kokoro-onnx soundfile
curl.exe -L -o "$d\kokoro-v1.0.onnx" https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl.exe -L -o "$d\voices-v1.0.bin"  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

That is all: `record.mjs` finds `~/algo-kokoro/venv` by itself and uses it for `--narrate`. It prints the voice it used
(`voice af_heart`). Making the 21 clips takes under a minute. Listen to the result before you upload.

If the recorded `.webm` plays in Chrome but not in another player (it has no duration header), convert it to MP4
with ffmpeg: `ffmpeg -i in.webm -c:v libx264 -c:a aac out.mp4`.

## 7. Putting the video on YouTube

- **File:** upload a `.webm` as it is; YouTube accepts it. It has no duration header, which YouTube works out itself.
  There are two versions: `algo-lab-demo.webm` (captions only) and `algo-lab-demo-narrated.webm` (the same, with the
  spoken narration). Use the narrated one if you are happy with how the voice sounds, otherwise the silent one.
- **Title:** *Algo Trading Learning Lab: practise algorithmic trading with paper money (Python, FastAPI)*
- **Description:** use the template below, with the chapter list that matches the file you upload (the narrated
  video is longer, so its times differ). They are for the videos recorded on 7 Oct 2026; if you re-record, use the
  list the script prints instead.
- **Visibility:** *Unlisted* is a good default for friends and colleagues: anyone with the link can watch, and it stays
  out of search. Switch to Public later if you want.
- **Audience:** choose "No, it's not made for kids".
- **Thumbnail:** a frame of the Optimise verdict or the chart with its stop-loss and take-profit lines, with large text
  such as "Paper trading lab".

```text
A practice lab for algorithmic trading, using paper money only. Write or pick a trading rule, test it on history,
and see whether the result was skill or luck.

Built from scratch with Python (FastAPI, SQLite) and plain JavaScript. The stocks in this demo are simulated.

(paste the chapters for your file here; both lists are just below)

Paper trading only. No real money, and nothing here is investment advice.
Source code: https://github.com/sandeepamrutia0604-cmd/algo-trading-learning-lab
```

Chapters for the **silent** video (`algo-lab-demo.webm`, 3:27):

```text
0:00 Intro
0:07 Home: your paper portfolio
0:14 Learn: ten lessons with quizzes
0:34 Scanner: what is signalling today?
0:52 Trade: stop-loss and take-profit
1:51 Data quality: catching bad prices
2:05 Strategies
2:13 Backtests: replaying history
2:37 Monte Carlo: how lucky was it?
2:49 Optimise: catching overfitting
3:13 Performance and Journal
3:21 Wrap-up
```

Chapters for the **narrated** video (`algo-lab-demo-narrated.webm`, 4:52):

```text
0:00 Intro
0:15 Home: your paper portfolio
0:28 Learn: ten lessons with quizzes
1:03 Scanner: what is signalling today?
1:29 Trade: stop-loss and take-profit
2:46 Data quality: catching bad prices
3:04 Strategies
3:17 Backtests: replaying history
3:49 Monte Carlo: how lucky was it?
4:02 Optimise: catching overfitting
4:29 Performance and Journal
4:41 Wrap-up
```

**Voice-over.** The narrated video already has a voice (see section 6). If you would rather use your own, record
the silent video and read the lines in section 8 over it in a video editor (Windows 11's Clipchamp is free; YouTube
Studio cannot add speech). If your editor refuses a `.webm`, tell me and I will help convert it.

## 8. Narration script

These are the exact lines the narrated video speaks, one per caption, taken from `scripts/demo/narration.mjs`. They
are also a script for reading aloud yourself.

1. **Intro.** "This is the Algo Trading Learning Lab. It is a practice lab for algorithmic trading, and it uses paper money only. Nothing here is real money, and nothing here is advice."
2. **Home.** "Home. You start with a paper portfolio of one lakh rupees, a practice checklist, and a guided course."
3. **Learn.** "Learn. There are ten short lessons with quizzes, from what is a stock, all the way to going live. Each lesson ends with a Try it button that opens the app, ready for the experiment."
4. **Learn, a lesson.** "The lessons use plain language and worked examples. This one covers risk: position sizing, stop losses, and take profits."
5. **Scanner.** "The scanner asks one question: which stocks is a strategy signalling today? It only uses what has happened by the market date, so there is no peeking at the future."
6. **Scanner, a signal.** "There is a buy signal today. Let's take a look at it."
7. **Trade.** "On the Trade page you get candlesticks, moving averages, a watchlist, and an order ticket."
8. **Trade, an open position.** "This open position already has its entry, stop loss and take profit drawn on the chart, with what each one would make or lose."
9. **Trade, the order ticket.** "For a new order, I set a stop loss and a take profit. The chart previews them, and the ticket shows the money at risk and the reward."
10. **Trade, bought.** "Bought. The levels now belong to the position."
11. **Trade, the market moves.** "Now let the market run, one day at a time. Each day's low and high are checked against my levels."
12. **Trade, an exit fires.** "An exit fired by itself. If a stock opens beyond a level, the order fills at the open, and a day that touches both levels takes the stop."
13. **Data quality.** "Data quality catches what quietly fools a backtest. Here it found a half price day that looks like an unadjusted stock split, and ten missing days."
14. **Strategies.** "Strategies. There are six built-in types, or you can build your own rules. Each one marks its signals on the chart."
15. **Backtests.** "A backtest replays history with a strategy, including trading costs and realistic next day fills."
16. **Backtests, the metrics.** "It reports much more than the return: Sharpe and Sortino ratios, the worst fall, how long it lasted, and how a simple buy and hold compares."
17. **Monte Carlo.** "Monte Carlo reshuffles the trades thousands of times, to ask how much of the result was luck."
18. **Optimise.** "The optimiser finds the best settings on a training period, then tests them on data it has never seen."
19. **Optimise, the verdict.** "A big drop from training to test is the signature of overfitting: settings fitted to noise, not to a real pattern."
20. **Performance.** "Performance and Journal. Every paper trade, with drawdown, win rate, and a monthly breakdown."
21. **Wrap-up.** "Paper money, real lessons. The whole project is on GitHub, and it is all paper trading, not investment advice."
