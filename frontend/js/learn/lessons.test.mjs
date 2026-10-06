// Run with:  node --test frontend/js/learn/lessons.test.mjs
// Checks the lesson data and the progress logic. Lessons are plain data, so a typo (a quiz
// answer index that points nowhere, an unknown block type) would otherwise only show up in
// the browser, in the one lesson that has it.
import assert from "node:assert/strict";
import test from "node:test";

import { MODULES, isReady } from "./lessons.js";
import { completedCount, isDone, loadProgress, nextModule, recordResult, saveProgress } from "./progress.js";

const KNOWN_BLOCKS = ["h", "p", "list", "note", "example", "terms", "tryit"];
const APP_ROUTES = ["home", "trade", "strategies", "scanner", "backtests", "optimise", "performance", "journal"];
const nonEmpty = (value) => typeof value === "string" && value.trim().length > 0;

function checkBlock(block, where) {
  const kinds = Object.keys(block).filter((key) => KNOWN_BLOCKS.includes(key));
  assert.equal(kinds.length, 1, `${where}: needs exactly one of ${KNOWN_BLOCKS.join(", ")}, got ${Object.keys(block)}`);
  assert.equal(Object.keys(block).length, 1, `${where}: unexpected extra keys in ${JSON.stringify(Object.keys(block))}`);
  const [kind] = kinds;
  const value = block[kind];

  if (["h", "p", "note"].includes(kind)) assert.ok(nonEmpty(value), `${where}: ${kind} text is empty`);
  if (kind === "list") {
    assert.ok(Array.isArray(value) && value.length > 0 && value.every(nonEmpty), `${where}: list needs non-empty strings`);
  }
  if (kind === "example") assert.ok(nonEmpty(value.title) && nonEmpty(value.text), `${where}: example needs a title and text`);
  if (kind === "terms") {
    assert.ok(Array.isArray(value) && value.length > 0, `${where}: terms is empty`);
    for (const pair of value) assert.ok(Array.isArray(pair) && pair.length === 2 && pair.every(nonEmpty), `${where}: each term is [term, meaning]`);
  }
  if (kind === "tryit") {
    assert.ok(nonEmpty(value.label) && nonEmpty(value.hint), `${where}: tryit needs a label and a hint`);
    assert.ok(APP_ROUTES.includes(value.route), `${where}: tryit route '${value.route}' isn't an app page`);
    if (value.symbol) assert.match(value.symbol, /^[A-Z0-9&-]{1,10}$/, `${where}: tryit symbol`);
  }
}

test("modules are numbered 1..N in order, each with a title, summary and reading time", () => {
  assert.ok(MODULES.length >= 10);
  MODULES.forEach((module, index) => {
    assert.equal(module.id, index + 1);
    assert.ok(nonEmpty(module.title) && nonEmpty(module.summary), `module ${module.id} needs a title and summary`);
    assert.ok(Number.isInteger(module.minutes) && module.minutes > 0, `module ${module.id} needs a reading time`);
  });
});

test("every written lesson is well formed", () => {
  for (const module of MODULES.filter(isReady)) {
    module.blocks.forEach((block, index) => checkBlock(block, `module ${module.id}, block ${index + 1}`));
    assert.ok(module.blocks.some((b) => "p" in b), `module ${module.id} has no explanation`);
  }
});

test("every written lesson has a quiz whose answers point at real options", () => {
  for (const module of MODULES.filter(isReady)) {
    assert.ok(Array.isArray(module.quiz) && module.quiz.length >= 3, `module ${module.id} needs a quiz of at least 3 questions`);
    const seen = new Set();
    module.quiz.forEach((item, index) => {
      const where = `module ${module.id}, question ${index + 1}`;
      assert.ok(nonEmpty(item.q), `${where}: empty question`);
      assert.ok(!seen.has(item.q), `${where}: duplicate question`);
      seen.add(item.q);
      assert.ok(Array.isArray(item.options) && item.options.length >= 2 && item.options.length <= 5, `${where}: needs 2 to 5 options`);
      assert.ok(item.options.every(nonEmpty), `${where}: an option is empty`);
      assert.equal(new Set(item.options).size, item.options.length, `${where}: duplicate options`);
      assert.ok(Number.isInteger(item.answer) && item.answer >= 0 && item.answer < item.options.length, `${where}: answer ${item.answer} isn't one of the options`);
      assert.ok(nonEmpty(item.why), `${where}: needs an explanation`);
    });
  }
});

test("a quiz doesn't always put the right answer in the same place", () => {
  for (const module of MODULES.filter(isReady)) {
    assert.ok(new Set(module.quiz.map((item) => item.answer)).size >= 2, `module ${module.id}: every answer is in the same position`);
  }
});

test("modules that are not written yet have no half-finished content", () => {
  for (const module of MODULES.filter((m) => !isReady(m))) assert.equal(module.quiz, undefined, `module ${module.id} has a quiz but no lesson`);
});

// ---------- progress ----------

const memoryStorage = (initial) => {
  const data = new Map(initial === undefined ? [] : [["algo-lab-learn-progress", initial]]);
  return { getItem: (key) => (data.has(key) ? data.get(key) : null), setItem: (key, value) => data.set(key, value) };
};

test("recording a result marks the module done and remembers when", () => {
  const next = recordResult({}, 1, 4, 5, new Date("2026-10-02T10:00:00Z"));
  assert.deepEqual(next, { 1: { done: true, best: 4, total: 5, at: "2026-10-02T10:00:00.000Z" } });
  assert.equal(isDone(next, 1), true);
  assert.equal(isDone(next, 2), false);
});

test("retaking a quiz can raise the best score but never lowers it or moves the first date", () => {
  const first = recordResult({}, 1, 3, 5, new Date("2026-10-02T10:00:00Z"));
  const worse = recordResult(first, 1, 1, 5, new Date("2026-10-03T10:00:00Z"));
  assert.equal(worse[1].best, 3);
  assert.equal(worse[1].at, "2026-10-02T10:00:00.000Z");
  assert.equal(recordResult(worse, 1, 5, 5)[1].best, 5);
});

test("recording a result does not mutate the previous progress", () => {
  const before = {};
  recordResult(before, 1, 5, 5);
  assert.deepEqual(before, {});
});

test("completed modules are counted", () => {
  const progress = recordResult(recordResult({}, 1, 5, 5), 3, 2, 4);
  assert.equal(completedCount(progress, MODULES), 2);
  assert.equal(completedCount({}, MODULES), 0);
});

test("progress round-trips through storage", () => {
  const storage = memoryStorage();
  const progress = recordResult({}, 1, 5, 5, new Date("2026-10-02T10:00:00Z"));
  saveProgress(progress, storage);
  assert.deepEqual(loadProgress(storage), progress);
});

test("unreadable or missing stored progress means no progress, not a crash", () => {
  assert.deepEqual(loadProgress(memoryStorage()), {});
  assert.deepEqual(loadProgress(memoryStorage("{not json")), {});
  assert.deepEqual(loadProgress(memoryStorage("[1,2,3]")), {});
  assert.deepEqual(loadProgress(memoryStorage("null")), {});
});

test("blocked storage doesn't crash the lessons", () => {
  const blocked = {
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("blocked");
    },
  };
  assert.deepEqual(loadProgress(blocked), {});
  assert.doesNotThrow(() => saveProgress({ 1: { done: true } }, blocked));
});

test("the next module to continue is the first one not yet completed", () => {
  const written = MODULES.filter(isReady);
  assert.equal(nextModule({}, written).id, 1);
  const some = recordResult(recordResult({}, 1, 4, 4), 2, 4, 4);
  assert.equal(nextModule(some, written).id, 3);
  // skipping ahead doesn't hide the gap: module 2 is still next
  assert.equal(nextModule(recordResult(recordResult({}, 1, 4, 4), 3, 4, 4), written).id, 2);
});

test("there is nothing to continue once every written module is done", () => {
  const written = MODULES.filter(isReady);
  const all = written.reduce((progress, m) => recordResult(progress, m.id, 1, 1), {});
  assert.equal(nextModule(all, written), undefined);
  assert.equal(nextModule({}, []), undefined);
});

test("every module is written, so there are no 'coming soon' leftovers", () => {
  assert.equal(MODULES.filter(isReady).length, MODULES.length);
});
