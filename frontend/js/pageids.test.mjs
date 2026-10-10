// Every element id in index.html must be unique. The pages find their elements with getElementById, which silently
// returns the FIRST match, so a clashing id makes one page draw into another page's hidden element (this once
// broke the Performance page's equity curve). Run with `node --test frontend/js/pageids.test.mjs`.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("no id appears twice in index.html", () => {
  const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const seen = new Map();
  for (const [, id] of html.matchAll(/\bid="([^"]+)"/g)) seen.set(id, (seen.get(id) || 0) + 1);
  const repeated = [...seen].filter(([, n]) => n > 1).map(([id, n]) => `${id} x${n}`);
  assert.deepEqual(repeated, []);
});
