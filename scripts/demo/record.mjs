// Drives the app through a guided tour, to record a demo video or take the README screenshots.
//
//   python scripts/demo_setup.py                         (once: builds data/demo.db)
//   node scripts/demo/record.mjs --video demo.webm       (a 1280x720 video, on-screen captions)
//   node scripts/demo/record.mjs --shots docs/images     (1600x900 screenshots for the README)
//   node scripts/demo/record.mjs --video demo.webm --narrate [--voice af_heart] [--speed 1]
//                                                        (the same video, spoken by Kokoro, a free local AI voice)
//   ...  --narrate --engine windows [--voice "Microsoft David Desktop"] [--rate -1]
//                                                        (the voices built into Windows; used if Kokoro isn't set up)
//
// It starts its own copy of the app on a throwaway copy of data/demo.db, so it never touches your
// real database or a server you already have running, and every run starts from the same state.
// A Chrome window opens and plays the tour by itself: leave the mouse and keyboard alone until it
// closes (about four minutes for the video). Pass --url http://127.0.0.1:8000 to use a server that
// is already running instead (note that the tour places a trade and moves the market on).
//
// See docs/DEMO.md for the story the tour tells.

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { Browser, sleep } from "./chrome.mjs";
import { NARRATION } from "./narration.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../..");

/* ---------------- options ---------------- */

const argv = process.argv.slice(2);
const option = (name) => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : null);
const videoPath = option("--video");
const shotsDir = option("--shots");
const givenUrl = option("--url");
if (!videoPath && !shotsDir) {
  console.error("Usage: node scripts/demo/record.mjs --video out.webm | --shots docs/images [--url http://127.0.0.1:8000]");
  process.exit(1);
}
const VIDEO = Boolean(videoPath);
const NARRATE = argv.includes("--narrate");
const KOKORO_HOME = process.env.KOKORO_HOME || join(homedir(), "algo-kokoro");
const KOKORO_PYTHON = join(KOKORO_HOME, "venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
// Kokoro (a free AI voice that runs locally) when it is set up, otherwise the voices built into Windows.
const ENGINE = option("--engine") || (existsSync(KOKORO_PYTHON) ? "kokoro" : "windows");
const KOKORO = ENGINE === "kokoro";
const VOICE = option("--voice") || (KOKORO ? "af_heart" : "Microsoft Zira Desktop");
const RATE = Number(option("--rate") ?? -1); // Windows voices only
const TALK_SPEED = Number(option("--speed") ?? 1); // Kokoro only
if (NARRATE && !VIDEO) {
  console.error("--narrate goes with --video.");
  process.exit(1);
}
const SIZE = VIDEO ? { width: 1280, height: 720 } : { width: 1600, height: 900 };
const SPEED = VIDEO ? 1 : 0.2; // screenshots don't need the pauses a viewer does

/* ---------------- the app, on a copy of the demo database ---------------- */

async function startApp() {
  const source = join(root, "data", "demo.db");
  if (!existsSync(source)) throw new Error("data/demo.db is missing. Run: python scripts/demo_setup.py");
  const folder = mkdtempSync(join(tmpdir(), "algo-demo-db-"));
  const database = join(folder, "demo.db");
  copyFileSync(source, database);

  const python = [join(root, ".venv", "Scripts", "python.exe"), join(root, ".venv", "bin", "python")].find(existsSync) || "python";
  const port = 8765;
  const server = spawn(python, ["-m", "uvicorn", "backend.app.main:app", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, DATABASE_URL: `sqlite:///${database.replaceAll("\\", "/")}` },
    stdio: "ignore",
  });
  for (let i = 0; i < 80; i++) {
    try {
      if ((await fetch(`http://127.0.0.1:${port}/api/portfolio`)).ok) return { url: `http://127.0.0.1:${port}`, server, folder };
    } catch {
      // still starting
    }
    await sleep(250);
  }
  server.kill();
  throw new Error("The app didn't start. Is the virtual environment set up (see the README)?");
}

/* ---------------- the voice ---------------- */

function wavSeconds(wav) {
  let at = 12;
  let byteRate = 0;
  while (at + 8 <= wav.length) {
    const id = wav.toString("ascii", at, at + 4);
    const size = wav.readUInt32LE(at + 4);
    if (id === "fmt ") byteRate = wav.readUInt32LE(at + 16);
    if (id === "data") return size / byteRate;
    at += 8 + size + (size % 2);
  }
  throw new Error("Couldn't read the narration audio.");
}

/** Speak every narration line, with Kokoro or the voices built into Windows. Returns { key: { wav, seconds } }. */
function synthesise() {
  if (!KOKORO && process.platform !== "win32") throw new Error("The built-in voices are Windows only. Set up Kokoro (docs/DEMO.md).");
  const folder = mkdtempSync(join(tmpdir(), "algo-demo-voice-"));
  const lines = join(folder, "lines.json");
  writeFileSync(lines, JSON.stringify(NARRATION), "utf8");
  const run = KOKORO
    ? spawnSync(KOKORO_PYTHON, [join(here, "speak_kokoro.py"), "--json", lines, "--out", folder, "--voice", VOICE, "--speed", String(TALK_SPEED)], {
        encoding: "utf8",
        env: { ...process.env, KOKORO_HOME },
      })
    : spawnSync(
        "powershell.exe",
        ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", join(here, "speak.ps1"), "-Json", lines, "-OutDir", folder, "-Voice", VOICE, "-Rate", String(RATE)],
        { encoding: "utf8" },
      );
  if (run.status !== 0) throw new Error(`Couldn't make the narration with ${VOICE}: ${run.stderr || run.stdout}`);
  const clips = {};
  let total = 0;
  for (const key of Object.keys(NARRATION)) {
    const wav = readFileSync(join(folder, `${key}.wav`));
    clips[key] = { wav, seconds: wavSeconds(wav) };
    total += clips[key].seconds;
  }
  rmSync(folder, { recursive: true, force: true });
  console.log(`Narration: ${Object.keys(clips).length} lines, ${total.toFixed(0)} seconds of speech, voice ${VOICE}`);
  return clips;
}

/* ---------------- helpers that play the tour ---------------- */

class Tour {
  constructor(browser) {
    this.b = browser;
    this.chapters = [];
    this.started = Date.now();
    this.clips = {};
  }

  /** Note where a part of the tour begins, for the chapter list printed at the end (YouTube's format). */
  chapter(title) {
    const seconds = Math.max(0, Math.round((Date.now() - this.started) / 1000));
    const stamp = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    this.chapters.push(`${stamp} ${title}`);
  }

  async pause(ms) {
    await sleep(ms * SPEED);
  }

  async ready() {
    await this.b.eval(`(() => {
      const style = document.createElement("style");
      style.textContent = "html { scrollbar-width: none; } ::-webkit-scrollbar { display: none; }";
      document.head.append(style);
    })()`);
    if (VIDEO) await this.b.eval(readFileSync(join(here, "overlay.js"), "utf8"));
    if (NARRATE) {
      await this.b.prepareAudio();
      for (const [key, clip] of Object.entries(this.clips)) await this.b.loadAudio(key, clip.wav);
    }
  }

  // ----- what the viewer reads
  async say(html, ms = 4500, top = false, key = null) {
    if (!VIDEO) return;
    await this.b.eval(`__demo.caption(${JSON.stringify(html)}, ${top})`);
    await this.speak(key, ms);
  }
  /** Play narration line `key` (when narrating) and wait for it to finish, or `ms`, whichever is longer. */
  async speak(key, ms) {
    const clip = key && this.clips[key];
    if (clip) {
      const was = await this.b.playAudio(key);
      if (was !== "running") console.warn(`  audio engine was ${was} before "${key}"; resumed it`);
    }
    await sleep(Math.max(ms, clip ? clip.seconds * 1000 + 800 : 0));
  }
  async hush() {
    if (VIDEO) await this.b.eval("__demo.clearCaption()");
  }
  async card(title, sub, foot, ms, key = null) {
    if (!VIDEO) return;
    await this.b.eval(`__demo.card(${JSON.stringify(title)}, ${JSON.stringify(sub)}, ${JSON.stringify(foot || "")})`);
    await this.speak(key, ms);
  }
  async hideCard() {
    if (VIDEO) await this.b.eval("__demo.clearCard()");
    await sleep(VIDEO ? 800 : 0);
  }

  // ----- finding things
  async rect(selector) {
    return this.b.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      el.scrollIntoView({ block: "nearest", behavior: "instant" });
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    })()`);
  }

  async need(selector, timeout = 20000) {
    await this.b.waitFor(`document.querySelector(${JSON.stringify(selector)})`, { timeout, what: selector });
  }

  /** Highlight an element for a moment. */
  async spot(selector) {
    if (!VIDEO) return;
    const r = await this.rect(selector);
    if (r) await this.b.eval(`__demo.spot(${JSON.stringify(r)})`);
  }
  async unspot() {
    if (VIDEO) await this.b.eval("__demo.clearSpots()");
  }

  // ----- acting like a person
  async glideTo(selector) {
    await this.need(selector);
    const r = await this.rect(selector);
    if (!r) return null;
    const x = Math.round(r.x + Math.min(r.w / 2, 90));
    const y = Math.round(r.y + r.h / 2);
    if (VIDEO) {
      await this.b.eval(`__demo.moveTo(${x}, ${y})`);
      await sleep(750);
    }
    return { x, y };
  }

  async click(selector) {
    const at = await this.glideTo(selector);
    if (VIDEO && at) {
      await this.b.eval(`__demo.click(${at.x}, ${at.y})`);
      await sleep(200);
    }
    await this.b.eval(`document.querySelector(${JSON.stringify(selector)}).click()`);
    await sleep(VIDEO ? 500 : 150);
  }

  async choose(selector, value) {
    await this.glideTo(selector);
    await this.b.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      el.value = ${JSON.stringify(value)};
      el.dispatchEvent(new Event("change", { bubbles: true }));
    })()`);
    await sleep(VIDEO ? 600 : 150);
  }

  async type(selector, text) {
    await this.glideTo(selector);
    await this.b.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.focus(); el.select(); })()`);
    let typed = "";
    for (const ch of text) {
      typed += ch;
      await this.b.eval(`(() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        el.value = ${JSON.stringify(typed)};
        el.dispatchEvent(new Event("input", { bubbles: true }));
      })()`);
      await sleep(VIDEO ? 130 : 0);
    }
    await sleep(VIDEO ? 300 : 100);
  }

  async go(route) {
    await this.click(`#nav a[data-route="${route}"]`);
    await this.b.waitFor(`!document.getElementById("page-${route}").hidden`, { what: `the ${route} page` });
    await sleep(VIDEO ? 900 : 500);
  }

  async scrollTo(selector, block = "start") {
    await this.b.eval(`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({ block: ${JSON.stringify(block)}, behavior: "smooth" })`);
    await sleep(VIDEO ? 1100 : 300);
  }

  async scrollMain(by) {
    await this.b.eval(`(document.querySelector("main") || document.scrollingElement).scrollBy({ top: ${by}, behavior: "smooth" })`);
    await sleep(VIDEO ? 1300 : 300);
  }

  /** A README screenshot (does nothing while recording the video). */
  async shot(name) {
    if (VIDEO) return;
    mkdirSync(shotsDir, { recursive: true });
    await sleep(350);
    await this.b.screenshot(join(shotsDir, `${name}.png`));
    console.log("  screenshot", name);
  }
}

/* ---------------- the tour ---------------- */

async function tour(t, b) {
  const api = (path) => b.eval(`fetch(${JSON.stringify(path)}).then((r) => r.json())`);

  t.chapter("Intro");
  await t.card(
    "Algo Trading Learning Lab",
    "Learn how algorithmic trading works, using paper money.<br>Nothing here is real money, and nothing here is advice.",
    "Built with Python (FastAPI), SQLite and plain JavaScript",
    5500,
    "intro",
  );
  await t.hideCard();

  // ---- Home
  t.chapter("Home: your paper portfolio");
  await b.waitFor(String.raw`/PORTFOLIO VALUE\s*₹/.test(document.body.innerText)`, { what: "the portfolio to load" });
  await t.say("<b>Home:</b> a paper portfolio of ₹1,00,000, a practice checklist, and a guided course.", 5000, false, "home");
  await t.spot("#page-home .panel");
  await t.pause(2500);
  await t.unspot();
  await t.shot("01-home");
  await t.hush();

  // ---- Learn
  t.chapter("Learn: ten lessons with quizzes");
  await t.go("learn");
  await t.say("<b>Learn:</b> ten short lessons with quizzes, from “What is a stock?” to going live.<small>Each ends with a Try it button that opens the app ready for the experiment.</small>", 5500, false, "learn");
  await t.shot("02-learn");
  await t.click('a.learn-item[href="#/learn/7"]');
  await t.hush();
  await t.pause(1200);
  await t.say("Plain-language lessons with worked examples. This one covers risk: position sizing, stop-losses and take-profits.", 4500, false, "lesson");
  await t.scrollMain(650);
  await t.shot("03-lesson");
  await t.scrollMain(700);
  await t.pause(2000);
  await t.hush();

  // ---- Scanner
  t.chapter("Scanner: what is signalling today?");
  await t.go("scanner");
  await t.choose("#sc-source", "type:breakout");
  await b.waitFor(`document.querySelector(".sc-table tbody tr")`, { what: "scanner rows" });
  await t.pause(800);
  await t.say("<b>Scanner:</b> which stocks is a strategy signalling today?<small>It only uses what has happened by the market date, so there is no peeking at the future.</small>", 6000, false, "scanner");
  await t.spot(".sc-table tr.sc-buy");
  await t.pause(2200);
  await t.unspot();
  await t.shot("04-scanner");
  const symbol = await b.eval(`document.querySelector(".sc-table tr.sc-buy")?.dataset.symbol || "GAMMA"`);
  await t.say(`A BUY signal today on <b>${symbol}</b>. Let's look at it.`, 3500, false, "scannerBuy");
  await t.click(`[data-open="${symbol}"]`);
  await t.hush();

  // ---- Trade
  t.chapter("Trade: stop-loss and take-profit");
  await b.waitFor(`!document.getElementById("page-trade").hidden && document.querySelector("#chart .main-svg")`, { what: "the chart" });
  await t.pause(1200);
  await t.say("<b>Trade:</b> candlesticks, moving averages, a watchlist and an order ticket.", 4500, false, "trade");
  await t.shot("05-trade");
  await t.click('.trow[data-symbol="BETA"]');
  await t.pause(1200);
  await t.say("An open BETA position: its entry, stop-loss and take-profit are drawn on the chart, with what each would make or lose.", 6000, false, "position");
  await t.shot("06-position-lines");
  await t.hush();

  await t.click(`.trow[data-symbol="${symbol}"]`);
  await t.pause(1000);
  await t.type("#o-qty", "250");
  await t.type("#o-sl", "1");
  await t.type("#o-tp", "2");
  await t.pause(600);
  await t.spot("#o-exits");
  await t.say("Set a <b>stop-loss</b> and a <b>take-profit</b> on the order. The chart previews them, and the ticket shows the money at risk and the reward.", 8000, false, "ticket");
  await t.pause(1500);
  await t.unspot();
  await t.shot("07-order-ticket");
  await t.hush();
  await t.click("#o-submit");
  await t.pause(1500);
  await t.say("Bought. The levels now belong to the position.", 3500, false, "bought");
  await t.hush();

  await t.say("Now let the market run, one day at a time. Each day's low and high are checked against your levels.", 5000, false, "advance");
  let sold = false;
  for (let day = 1; day <= 9 && !sold; day++) {
    await t.click("#adv-1");
    await t.pause(1600);
    sold = !(await api("/api/positions")).some((p) => p.symbol === symbol);
  }
  await t.hush();
  if (sold) {
    await t.click('#t-tabs button[data-tab="trades"]');
    await t.scrollTo("#t-tabs");
    await t.pause(800);
    await t.spot("#trades-table tbody tr:first-child");
    await t.say("An exit fired by itself. If a stock opens beyond a level it fills at the open, and a day that touches both takes the stop.", 8000, false, "exit");
    await t.pause(1500);
    await t.unspot();
    await t.shot("08-exit-fired");
    await t.hush();
  }

  // ---- Data quality
  t.chapter("Data quality: catching bad prices");
  await t.click('#t-tabs button[data-tab="quality"]');
  await t.need("#dq-list tr[data-symbol]");
  await t.click('#dq-list tr[data-symbol="BADDATA"]');
  await t.need(".dq-issue");
  await t.pause(600);
  await t.scrollTo("#dq-detail", "center");
  await t.spot("#dq-detail");
  await t.say("<b>Data quality:</b> catches what quietly fools a backtest.<small>Here, a half-price day that looks like an unadjusted stock split, and ten missing days.</small>", 8500, true, "dataQuality");
  await t.pause(1500);
  await t.unspot();
  await t.shot("09-data-quality");
  await t.hush();

  // ---- Strategies
  t.chapter("Strategies");
  await t.go("strategies");
  await t.need("#strat-list");
  await t.say("<b>Strategies:</b> six built-in types, or build your own rules. Each marks its signals on the chart.", 5000, false, "strategies");
  await t.shot("10-strategies");
  await t.hush();

  // ---- Backtests
  t.chapter("Backtests: replaying history");
  await t.go("backtests");
  await t.choose("#bt-symbol", "BETA");
  await t.choose("#bt-type", "ma_crossover");
  await t.type("#bt-qty", "200");
  await t.say("<b>Backtests:</b> replay history with a strategy, with trading costs and realistic next-day fills.", 4500, false, "backtests");
  await t.click("#bt-run");
  await b.waitFor(`!document.getElementById("bt-results").hidden`, { timeout: 60000, what: "backtest results" });
  await t.scrollMain(-5000);
  await t.pause(1200);
  await t.shot("11-backtest");
  await t.hush();
  await t.scrollTo("#bt-more-panel");
  await t.say("It reports more than the return: Sharpe and Sortino, the worst fall, how long it lasted, and how a simple buy-and-hold compares.", 8500, false, "metrics");
  await t.shot("12-backtest-metrics");
  await t.hush();

  t.chapter("Monte Carlo: how lucky was it?");
  await t.scrollTo("#mc-panel");
  await t.click("#mc-run");
  await b.waitFor(`!document.getElementById("mc-results").hidden`, { timeout: 60000, what: "Monte Carlo results" });
  await t.pause(1000);
  await t.say("<b>Monte Carlo:</b> reshuffles the trades thousands of times to ask how much of the result was luck.", 6500, false, "monteCarlo");
  await t.scrollTo("#mc-results");
  await t.shot("13-monte-carlo");
  await t.hush();

  // ---- Optimise
  t.chapter("Optimise: catching overfitting");
  await t.go("optimise");
  await t.choose("#op-symbol", "ALPHA");
  await t.type("#op-qty", "300");
  await t.say("<b>Optimise:</b> finds the best settings on a training period, then tests them on data it has never seen.", 5500, false, "optimise");
  await t.click("#op-run");
  await b.waitFor(`!document.getElementById("op-results").hidden`, { timeout: 90000, what: "optimiser results" });
  await t.scrollTo("#op-verdict", "center");
  await t.pause(1000);
  await t.hush();
  await t.spot("#op-verdict");
  await t.say("A big drop from training to test is the signature of overfitting: settings fitted to noise, not to a real pattern.", 8000, false, "overfit");
  await t.pause(1500);
  await t.unspot();
  await t.shot("14-optimise");
  await t.hush();

  // ---- Performance
  t.chapter("Performance and Journal");
  await t.go("performance");
  await b.waitFor(`!document.getElementById("pf-content").hidden`, { what: "performance" });
  await t.pause(800);
  await t.say("<b>Performance and Journal:</b> every paper trade, with drawdown, win rate and a monthly breakdown.", 5000, false, "performance");
  await t.shot("15-performance");
  await t.hush();

  t.chapter("Wrap-up");
  await t.card(
    "Paper money, real lessons",
    "Strategies · backtests · risk management · walk-forward testing · Monte Carlo<br>More than 800 automated tests.",
    "github.com/sandeepamrutia0604-cmd/algo-trading-learning-lab",
    7000,
    "outro",
  );
}

/* ---------------- run ---------------- */

const clips = NARRATE ? synthesise() : {};
const app = givenUrl ? { url: givenUrl } : await startApp();
let browser;
try {
  browser = await Browser.launch(`${app.url}/#/home`, SIZE);
  const t = new Tour(browser);
  if (NARRATE) t.clips = clips;
  await browser.waitFor(`document.querySelector("#nav a")`, { what: "the app" });
  await t.ready();
  if (VIDEO) {
    await browser.startRecording(resolve(videoPath));
    await sleep(600);
  }
  t.started = Date.now();
  await tour(t, browser);
  if (VIDEO) {
    const saved = await browser.stopRecording();
    console.log("Video saved:", saved);
    console.log("\nChapters (paste into the YouTube description):\n" + t.chapters.join("\n"));
  }
} finally {
  if (browser) await browser.close();
  if (app.server) app.server.kill();
  if (app.folder) {
    await sleep(500);
    try {
      rmSync(app.folder, { recursive: true, force: true });
    } catch {
      // the database file may still be released a moment later; the temp folder is harmless
    }
  }
}
