// Run with:  node --test frontend/js/compare.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { alignSeries, applyPreset, beta, correlation, dailyReturns, maxDrawdown, periodReturn, rebase, relative, summarise, volatility } from "./compare.js";

const near = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) < tolerance, `${actual} is not ${expected}`);

// ---------- alignment ----------

test("only the dates every stock has are kept, in order, with each stock's own close", () => {
  const a = { symbol: "A", dates: ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-05"], closes: [1, 2, 3, 5] };
  const b = { symbol: "B", dates: ["2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"], closes: [20, 30, 40, 50] };

  const aligned = alignSeries([a, b]);

  assert.deepEqual(aligned.dates, ["2025-01-02", "2025-01-03", "2025-01-05"]);
  assert.deepEqual(aligned.series.map((s) => s.closes), [[2, 3, 5], [20, 30, 50]]);
  assert.deepEqual(aligned.series.map((s) => s.symbol), ["A", "B"]);
});

test("stocks with no dates in common align to nothing, and an empty list is fine", () => {
  const a = { symbol: "A", dates: ["2024-01-01", "2024-01-02"], closes: [1, 2] };
  const b = { symbol: "B", dates: ["2025-01-01", "2025-01-02"], closes: [1, 2] };
  assert.deepEqual(alignSeries([a, b]).dates, []);
  assert.deepEqual(alignSeries([]), { dates: [], series: [] });
});

test("three stocks keep only the dates all three share", () => {
  const mk = (symbol, dates) => ({ symbol, dates, closes: dates.map((_, i) => i + 1) });
  const aligned = alignSeries([mk("A", ["d1", "d2", "d3"]), mk("B", ["d2", "d3", "d4"]), mk("C", ["d3", "d4", "d5"])]);
  assert.deepEqual(aligned.dates, ["d3"]);
});

// ---------- periods ----------

const daily = (n, start = "2025-01-01") => {
  const out = [];
  for (let i = 0; i < n; i++) out.push(new Date(new Date(`${start}T00:00:00Z`).getTime() + i * 86400000).toISOString().slice(0, 10));
  return out;
};

test("a preset counts back from the last shared date", () => {
  const dates = daily(400);
  const aligned = { dates, series: [{ symbol: "A", closes: dates.map((_, i) => i + 1) }] };

  const month = applyPreset(aligned, "1M");

  assert.equal(month.dates[month.dates.length - 1], dates[399]);
  assert.equal(month.dates.length, 31); // 30 days back, both ends included
  assert.equal(month.series[0].closes.length, 31);
  assert.equal(month.series[0].closes[30], 400);
  assert.equal(applyPreset(aligned, "all").dates.length, 400);
  assert.equal(applyPreset(aligned, "1Y").dates.length, 366);
});

test("a preset longer than the history keeps everything", () => {
  const aligned = { dates: daily(20), series: [{ symbol: "A", closes: Array(20).fill(1) }] };
  assert.equal(applyPreset(aligned, "1Y").dates.length, 20);
});

// ---------- rebasing and relative performance ----------

test("rebasing starts at exactly 100", () => {
  const out = rebase([50, 55, 60]);
  assert.equal(out[0], 100);
  near(out[1], 110);
  near(out[2], 120);
});

test("nothing to rebase from gives an empty series", () => {
  assert.deepEqual(rebase([]), []);
  assert.deepEqual(rebase([0, 1, 2]), []);
});

test("relative performance is the ratio, starting at 100: above 100 means the first stock is ahead", () => {
  const out = relative([10, 12, 15], [10, 10, 10]);
  assert.deepEqual(out.map((v) => Math.round(v * 1e6) / 1e6), [100, 120, 150]);
  const behind = relative([10, 9], [10, 10]);
  near(behind[1], 90);
});

// ---------- return, drawdown, volatility ----------

test("the period return is last over first", () => {
  near(periodReturn([100, 110]), 10);
  near(periodReturn([200, 150]), -25);
  assert.equal(periodReturn([100]), null);
});

test("max drawdown is the biggest fall from a peak, as a percentage of that peak", () => {
  near(maxDrawdown([100, 120, 90, 110]), 25);
  near(maxDrawdown([100, 110, 120]), 0);
  assert.equal(maxDrawdown([100]), null);
});

test("volatility is the annualised standard deviation of daily returns", () => {
  // returns +10% then -10%: sample standard deviation sqrt(0.02) = 0.141421, times sqrt(252), as a percentage
  near(volatility([100, 110, 99]), 0.1414213562 * Math.sqrt(252) * 100, 1e-4);
  assert.equal(volatility([100, 101]), null); // one return is not enough
  assert.equal(volatility([100, 100, 100, 100]), 0);
});

// ---------- how two stocks move together ----------

const A = [100, 110, 99, 108.9]; // +10%, -10%, +10%
const HALF = [100, 105, 99.75, 104.7375]; // +5%, -5%, +5%: moves half as much, in step with A
const OPPOSITE = [100, 95, 99.75, 94.7625]; // -5%, +5%, -5%

test("daily returns are simple percentage changes", () => {
  const r = dailyReturns(A);
  near(r[0], 0.1);
  near(r[1], -0.1);
});

test("stocks that move in step are correlated +1 and opposite ones -1", () => {
  near(correlation(A, HALF), 1);
  near(correlation(A, OPPOSITE), -1);
});

test("beta is how much the first moves per 1% of the second", () => {
  near(beta(A, HALF), 2);
  near(beta(A, OPPOSITE), -2);
  near(beta(A, A), 1);
});

test("a flat stock has no correlation or beta, and too little data gives nothing", () => {
  assert.equal(correlation(A, [100, 100, 100, 100]), null);
  assert.equal(beta(A, [100, 100, 100, 100]), null);
  assert.equal(correlation([1, 2], [1, 2]), null);
  assert.equal(beta([1, 2, 3], [1, 2]), null);
});

// ---------- the table ----------

test("the summary has a row per stock and a pair for each other stock against the first", () => {
  const dates = ["d1", "d2", "d3", "d4"];
  const summary = summarise({ dates, series: [{ symbol: "A", closes: A }, { symbol: "B", closes: HALF }] });

  assert.equal(summary.days, 4);
  assert.equal(summary.from, "d1");
  assert.equal(summary.to, "d4");
  assert.deepEqual(summary.rows.map((r) => r.symbol), ["A", "B"]);
  near(summary.rows[0].return_pct, 8.9);
  near(summary.rows[1].return_pct, 4.7375);
  assert.equal(summary.pairs.length, 1);
  assert.equal(summary.pairs[0].symbol, "B");
  near(summary.pairs[0].correlation, 1);
  near(summary.pairs[0].beta, 2);
  near(summary.pairs[0].return_diff_pct, 8.9 - 4.7375);
});

test("a summary of nothing is empty but safe", () => {
  const summary = summarise({ dates: [], series: [{ symbol: "A", closes: [] }, { symbol: "B", closes: [] }] });
  assert.equal(summary.days, 0);
  assert.equal(summary.from, null);
  assert.equal(summary.rows[0].return_pct, null);
  assert.equal(summary.pairs[0].correlation, null);
  assert.equal(summary.pairs[0].return_diff_pct, null);
});
