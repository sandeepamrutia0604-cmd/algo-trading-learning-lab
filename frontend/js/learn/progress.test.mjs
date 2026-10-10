// Run with:  node --test frontend/js/learn/progress.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { FILE_KIND, mergeProgress, parseProgressFile, progressFile } from "./progress.js";

const one = { 1: { done: true, best: 4, total: 5, at: "2026-10-02T10:00:00.000Z" } };

test("a progress file round-trips", () => {
  const file = progressFile(one, new Date("2026-10-10T00:00:00Z"));
  assert.equal(file.kind, FILE_KIND);
  assert.deepEqual(parseProgressFile(JSON.stringify(file)), one);
});

test("a file that is not JSON, or not ours, is refused with a plain message", () => {
  assert.throws(() => parseProgressFile("not json"), /can't be read/);
  assert.throws(() => parseProgressFile(JSON.stringify({ hello: 1 })), /isn't a Learn progress file/);
  assert.throws(() => parseProgressFile(JSON.stringify({ kind: FILE_KIND, progress: [] })), /isn't a Learn progress file/);
});

test("unknown fields and bad entries are dropped, numbers are bounded", () => {
  const text = JSON.stringify({
    kind: FILE_KIND,
    version: 1,
    progress: { 2: { done: true, best: 99999, total: 5, at: "x", evil: "<script>" }, abc: { done: true }, 3: "nope" },
  });
  assert.deepEqual(parseProgressFile(text), { 2: { done: true, best: 0, total: 5, at: "x" } });
});

test("merging never loses progress: done wins, best is the higher, the date is the earlier", () => {
  const current = { 1: { done: true, best: 3, total: 5, at: "2026-10-05T00:00:00.000Z" }, 2: { done: false, best: 0, total: 5, at: null } };
  const incoming = { 1: { done: false, best: 5, total: 5, at: "2026-10-01T00:00:00.000Z" }, 3: { done: true, best: 2, total: 4, at: null } };
  assert.deepEqual(mergeProgress(current, incoming), {
    1: { done: true, best: 5, total: 5, at: "2026-10-01T00:00:00.000Z" },
    2: { done: false, best: 0, total: 5, at: null },
    3: { done: true, best: 2, total: 4, at: null },
  });
});
