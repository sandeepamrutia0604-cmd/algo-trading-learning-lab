import assert from "node:assert/strict";
import { test } from "node:test";
import { basketLabel, checkSelection, inOrder, keepExisting, skipText } from "./portfolio.js";

test("a basket needs between 2 and 20 different stocks", () => {
  assert.match(checkSelection([]), /at least 2/);
  assert.match(checkSelection(["A"]), /at least 2/);
  assert.match(checkSelection(["A", "A"]), /at least 2/);
  assert.equal(checkSelection(["A", "B"]), null);
  assert.match(checkSelection(Array.from({ length: 21 }, (_, i) => `S${i}`)), /at most 20/);
  assert.equal(checkSelection(Array.from({ length: 20 }, (_, i) => `S${i}`)), null);
});

test("skipped buys are explained in words, and nothing is said when there were none", () => {
  assert.equal(skipText({ cash: 0, allocation: 0, max_positions: 0, size: 0 }), "");
  assert.equal(skipText(undefined), "");
  assert.equal(skipText({ cash: 3, allocation: 0, max_positions: 1, size: 0 }), "3 for lack of cash, 1 because the maximum number of open positions was reached");
});

test("trades are listed in the order they happened, symbols breaking ties, without changing the input", () => {
  const trades = [
    { entry_date: "2025-02-01", symbol: "B" },
    { entry_date: "2025-01-05", symbol: "C" },
    { entry_date: "2025-01-05", symbol: "A" },
  ];
  assert.deepEqual(inOrder(trades).map((t) => t.symbol), ["A", "C", "B"]);
  assert.equal(trades[0].symbol, "B");
});

test("picks that no longer exist are dropped and the rest keep the list's order", () => {
  assert.deepEqual(keepExisting(["C", "A", "Z"], ["A", "B", "C"]), ["A", "C"]);
  assert.deepEqual(keepExisting([], ["A"]), []);
});

test("a long basket is shortened", () => {
  assert.equal(basketLabel(["A", "B"]), "A, B");
  assert.equal(basketLabel(["A", "B", "C", "D", "E", "F"]), "A, B, C, D +2");
});
