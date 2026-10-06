// Run with:  node --test frontend/js/levels.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { buildLevels, reachableLevelPrices } from "./levels.js";

const held = { average_price: 100, quantity: 10, stop_price: 95, target_price: 110 };
const kinds = (levels) => levels.map((l) => l.kind);
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} is not ${expected}`);

test("nothing is drawn with no position and no order", () => {
  assert.deepEqual(buildLevels({ price: 100 }), []);
  assert.deepEqual(buildLevels({ price: 100, order: { stop: null, target: null, quantity: 5, problems: [] } }), []);
});

test("a position with no exits shows just its entry", () => {
  const levels = buildLevels({ price: 103, position: { average_price: 100, quantity: 10, stop_price: null, target_price: null } });
  assert.deepEqual(kinds(levels), ["entry"]);
  assert.equal(levels[0].price, 100);
  assert.equal(levels[0].preview, false);
  assert.equal(levels[0].ifHit, null);
});

test("a protected position shows entry, stop and target with distances and what each would cost or earn", () => {
  const levels = buildLevels({ price: 102, position: held });
  assert.deepEqual(kinds(levels), ["entry", "stop", "target"]);
  const [, stop, target] = levels;
  near(stop.awayPct, (95 / 102 - 1) * 100);
  near(target.awayPct, (110 / 102 - 1) * 100);
  assert.equal(stop.ifHit, -50); // (95 - 100) x 10: measured from the entry, not from today's price
  assert.equal(target.ifHit, 100);
  assert.ok(levels.every((l) => l.preview === false && l.quantity === 10));
});

test("only the exits that are set are drawn", () => {
  assert.deepEqual(kinds(buildLevels({ price: 100, position: { ...held, target_price: null } })), ["entry", "stop"]);
  assert.deepEqual(kinds(buildLevels({ price: 100, position: { ...held, stop_price: null } })), ["entry", "target"]);
});

test("an order on the ticket previews its levels from the current price", () => {
  const order = { stop: 95, target: 110, quantity: 20, problems: [] };
  const levels = buildLevels({ price: 100, order });
  assert.deepEqual(kinds(levels), ["entry", "stop", "target"]);
  assert.ok(levels.every((l) => l.preview === true));
  assert.equal(levels[0].price, 100); // it would buy at about today's price
  assert.equal(levels[1].ifHit, -100);
  assert.equal(levels[2].ifHit, 200);
});

test("a valid preview wins over the position's own lines", () => {
  const levels = buildLevels({ price: 100, position: held, order: { stop: 90, target: null, quantity: 5, problems: [] } });
  assert.deepEqual(kinds(levels), ["entry", "stop"]);
  assert.equal(levels[1].price, 90);
  assert.equal(levels[1].preview, true);
});

test("an order with a problem (a stop above the price, say) is ignored", () => {
  const order = { stop: 105, target: null, quantity: 5, problems: ["The stop-loss must be below the price."] };
  const levels = buildLevels({ price: 100, position: held, order });
  assert.ok(levels.every((l) => l.preview === false));
  assert.equal(levels[1].price, 95);
  assert.deepEqual(buildLevels({ price: 100, order }), []); // and with no position there is nothing to show
});

test("an order that sets no levels does not hide the position's", () => {
  const levels = buildLevels({ price: 100, position: held, order: { stop: null, target: null, quantity: 5, problems: [] } });
  assert.ok(levels.every((l) => l.preview === false));
});

test("a preview with no quantity yet still draws, but claims no rupee figure", () => {
  const levels = buildLevels({ price: 100, order: { stop: 95, target: null, quantity: 0, problems: [] } });
  assert.deepEqual(kinds(levels), ["entry", "stop"]);
  assert.equal(levels[1].ifHit, null);
});

test("only levels within reach of the price make room on the axis", () => {
  const levels = buildLevels({ price: 100, position: { average_price: 100, quantity: 1, stop_price: 95, target_price: 160 } });
  assert.deepEqual(reachableLevelPrices(levels, 100), [100, 95]); // 160 is 60% away
  assert.deepEqual(reachableLevelPrices(levels, 100, 0.7), [100, 95, 160]);
});
