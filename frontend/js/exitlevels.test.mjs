// Run with:  node --test frontend/js/exitlevels.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { describeExitLevels, parseExitLevels } from "./exitlevels.js";

test("empty boxes mean no levels", () => {
  assert.deepEqual(parseExitLevels("", ""), { values: {}, error: null });
  assert.deepEqual(parseExitLevels("  ", undefined), { values: {}, error: null });
});

test("each level can be set alone or together", () => {
  assert.deepEqual(parseExitLevels("5", "").values, { stop_loss_pct: 5 });
  assert.deepEqual(parseExitLevels("", "10.5").values, { take_profit_pct: 10.5 });
  assert.deepEqual(parseExitLevels("5", "10").values, { stop_loss_pct: 5, take_profit_pct: 10 });
});

test("a stop must be more than 0 and less than 100", () => {
  for (const bad of ["0", "100", "150", "-3", "abc"]) assert.match(parseExitLevels(bad, "").error, /stop-loss/, bad);
  assert.equal(parseExitLevels("99.9", "").error, null);
});

test("a take-profit must be more than 0 and at most 1000", () => {
  for (const bad of ["0", "-1", "1001", "x"]) assert.match(parseExitLevels("", bad).error, /take-profit/, bad);
  assert.equal(parseExitLevels("", "1000").error, null);
});

test("an error returns no values at all", () => {
  assert.deepEqual(parseExitLevels("5", "0").values, {});
});

test("levels are described in a short phrase", () => {
  assert.equal(describeExitLevels(5, 10), "5% stop / 10% target");
  assert.equal(describeExitLevels(5, null), "5% stop");
  assert.equal(describeExitLevels(undefined, 10), "10% target");
  assert.equal(describeExitLevels(null, null), "");
});
