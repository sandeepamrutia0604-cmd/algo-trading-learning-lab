// Turning table data into a CSV file the user can open in Excel. The building is pure (no DOM) so it can be
// tested with `node --test frontend/js/csv.test.mjs`; only downloadFile() touches the page.
//
// Two things matter beyond quoting:
//   * Excel needs a byte-order mark to read UTF-8 (the rupee sign, accented names) correctly.
//   * Spreadsheet formula injection: a text cell that starts with = + - @ (or a tab / carriage return) is run as a
//     formula when the file is opened, and some text here is typed by the user (strategy names, alert notes).
//     Such text gets a leading apostrophe. Numbers are written as numbers and are never touched.

export const BOM = "﻿";

/** One value as a CSV cell. */
export function csvCell(value) {
  if (value === null || value === undefined) return "";
  // Rounded to 4 decimals: it hides floating-point noise (651.6300000000007) and keeps every real digit of a price or a percentage.
  if (typeof value === "number") return Number.isFinite(value) ? String(Math.round(value * 1e4) / 1e4) : "";
  if (typeof value === "boolean") return value ? "true" : "false";
  let text = String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * @param {{header: string, value: string|((row: object) => any)}[]} columns  `value` is a field name or a function
 * @param {object[]} rows
 * @returns {string} CSV text, one line per row (CRLF, as spreadsheets expect), a header line first
 */
export function toCsv(columns, rows) {
  const read = (column, row) => (typeof column.value === "function" ? column.value(row) : row[column.value]);
  const lines = [columns.map((c) => csvCell(c.header)).join(",")];
  for (const row of rows) lines.push(columns.map((c) => csvCell(read(c, row))).join(","));
  return lines.join("\r\n") + "\r\n";
}

/** A file name that is safe on every system: letters, digits, dot, dash and underscore only. */
export const safeFileName = (name) => name.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "export";

/** Hand `content` (a string or Blob) to the browser as a download. */
export function downloadFile(filename, content, type = "text/csv;charset=utf-8") {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = safeFileName(filename);
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Build a CSV and download it (with the byte-order mark Excel needs). */
export function downloadCsv(filename, columns, rows) {
  downloadFile(filename, BOM + toCsv(columns, rows));
}
