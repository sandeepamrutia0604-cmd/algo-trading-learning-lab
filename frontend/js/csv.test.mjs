// Run with:  node --test frontend/js/csv.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { BOM, csvCell, safeFileName, toCsv } from "./csv.js";

test("plain values are written as they are, numbers stay numbers", () => {
  assert.equal(csvCell("ALPHA"), "ALPHA");
  assert.equal(csvCell(12.5), "12.5");
  assert.equal(csvCell(-3), "-3");
  assert.equal(csvCell(0), "0");
  assert.equal(csvCell(true), "true");
});

test("floating-point noise is rounded away but real digits are kept", () => {
  assert.equal(csvCell(651.6300000000007), "651.63");
  assert.equal(csvCell(369.98066666666665), "369.9807");
  assert.equal(csvCell(0.1 + 0.2), "0.3");
  assert.equal(csvCell(1234567.891), "1234567.891");
});

test("empty and non-finite values become empty cells", () => {
  assert.equal(csvCell(null), "");
  assert.equal(csvCell(undefined), "");
  assert.equal(csvCell(NaN), "");
  assert.equal(csvCell(Infinity), "");
});

test("commas, quotes and line breaks are quoted, quotes doubled", () => {
  assert.equal(csvCell("a,b"), '"a,b"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell("two\nlines"), '"two\nlines"');
});

test("text that a spreadsheet would run as a formula gets a leading apostrophe", () => {
  assert.equal(csvCell("=SUM(A1:A9)"), "'=SUM(A1:A9)");
  assert.equal(csvCell("+1+1"), "'+1+1");
  assert.equal(csvCell("-cmd"), "'-cmd");
  assert.equal(csvCell("@x"), "'@x");
  assert.equal(csvCell('=HYPERLINK("http://x","y")'), `"'=HYPERLINK(""http://x"",""y"")"`);
  assert.equal(csvCell("2025-01-31"), "2025-01-31"); // a date is not a formula
});

test("a negative number is a number, not a formula", () => {
  assert.equal(csvCell(-12.34), "-12.34");
});

test("a table has a header line, one line per row, and CRLF endings", () => {
  const text = toCsv(
    [
      { header: "Symbol", value: "symbol" },
      { header: "Value", value: (r) => r.qty * r.price },
    ],
    [
      { symbol: "ALPHA", qty: 2, price: 10.5 },
      { symbol: "BE,TA", qty: 1, price: 3 },
    ],
  );
  assert.equal(text, 'Symbol,Value\r\nALPHA,21\r\n"BE,TA",3\r\n');
});

test("no rows still gives the header, and the rupee sign survives", () => {
  assert.equal(toCsv([{ header: "Price (₹)", value: "p" }], []), "Price (₹)\r\n");
  assert.equal(BOM, "﻿");
});

test("file names keep only safe characters", () => {
  assert.equal(safeFileName("trades 2025/01/31.csv"), "trades-2025-01-31.csv");
  assert.equal(safeFileName("///"), "export");
  assert.equal(safeFileName("M&M backtest.csv"), "M-M-backtest.csv");
});
