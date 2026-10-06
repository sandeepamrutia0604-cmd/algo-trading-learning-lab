import { $, api, toast } from "../util.js";

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const state = { rows: [], symbol: null, loading: false };

const STATUS_LABEL = { clean: "Looks clean", check: "Worth a look", problems: "Problems" };
const SOURCE_LABEL = { simulated: "Simulated", upstox: "Upstox", angel_one: "Angel One", csv: "File" };
const SEVERITY_ICON = { error: "&#10007;", warning: "&#9888;", info: "&#8505;" };
const KIND_LABEL = {
  bad_ohlc: "Impossible candle",
  non_positive: "Zero or negative price",
  wide_range: "Wild day",
  big_jump: "Big one-day move",
  possible_split: "Possible split or bonus",
  weekend_candle: "Weekend candle",
  missing_days: "Missing days",
  flat_run: "Price didn't move",
  zero_volume: "Zero volume",
  no_volume: "No volume data",
  short_history: "Short history",
};

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

/* One sentence on how a stock's data looks, for an import result: "Looks clean." or "2 warnings: worth a look." */
export function qualityLine(summary) {
  if (!summary) return "";
  if (summary.status === "clean") return "Data check: looks clean.";
  const parts = [];
  if (summary.errors) parts.push(plural(summary.errors, "problem"));
  if (summary.warnings) parts.push(plural(summary.warnings, "warning"));
  return `Data check: ${parts.join(" and ")}. See the Data quality tab.`;
}

function statusChip(status) {
  return `<span class="dq-status ${status}">${STATUS_LABEL[status]}</span>`;
}

function renderList() {
  const body = state.rows
    .map((r) => {
      const notes = [r.errors && plural(r.errors, "problem"), r.warnings && plural(r.warnings, "warning"), r.infos && plural(r.infos, "note")].filter(Boolean);
      return `<tr class="dq-row ${r.symbol === state.symbol ? "sel" : ""}" data-symbol="${escapeHtml(r.symbol)}">
        <td><b>${escapeHtml(r.symbol)}</b></td>
        <td>${escapeHtml(SOURCE_LABEL[r.source] || r.source)}</td>
        <td class="num">${r.candles.toLocaleString("en-IN")}</td>
        <td>${r.first_date ? `${r.first_date} to ${r.last_date}` : "-"}</td>
        <td>${statusChip(r.status)}</td>
        <td class="muted">${notes.join(", ") || "-"}</td>
      </tr>`;
    })
    .join("");
  $("dq-list").innerHTML = state.rows.length
    ? `<table class="dq-table"><thead><tr><th>Stock</th><th>Source</th><th class="num">Days</th><th>History</th><th>Status</th><th>Found</th></tr></thead><tbody>${body}</tbody></table>`
    : `<p class="hint">No stocks yet.</p>`;
}

function issueRow(issue) {
  const label = KIND_LABEL[issue.kind] || issue.kind;
  return `<div class="dq-issue ${issue.severity}">
    <span class="dq-icon" title="${issue.severity}">${SEVERITY_ICON[issue.severity]}</span>
    <div><b>${escapeHtml(label)}</b>${issue.date ? ` <span class="muted">&middot; ${issue.date}</span>` : ""}
      <div>${escapeHtml(issue.message)}</div></div>
  </div>`;
}

function renderDetail(report) {
  const serious = report.issues.filter((i) => i.severity !== "info");
  const notes = report.issues.filter((i) => i.severity === "info");
  const head = `<h4 class="lesson-h" style="margin:4px 0">${escapeHtml(report.symbol)} ${statusChip(report.status)}</h4>`;
  const verdict = serious.length
    ? ""
    : `<p class="hint">Nothing here should distort a backtest.${notes.length ? " The notes below are for your information." : ""}</p>`;
  $("dq-detail").innerHTML =
    head +
    verdict +
    serious.map(issueRow).join("") +
    (notes.length ? `<details class="dq-notes" ${serious.length ? "" : "open"}><summary>${plural(notes.length, "note")}</summary>${notes.map(issueRow).join("")}</details>` : "");
}

async function showStock(symbol) {
  state.symbol = symbol;
  renderList();
  $("dq-detail").innerHTML = `<p class="hint">Checking ${escapeHtml(symbol)}...</p>`;
  try {
    const report = await api(`/data-quality/${encodeURIComponent(symbol)}`);
    if (symbol !== state.symbol) return; // another row was chosen while loading
    renderDetail(report);
  } catch (err) {
    $("dq-detail").innerHTML = "";
    toast(err.message, true);
  }
}

export async function renderDataQuality() {
  if (state.loading) return;
  state.loading = true;
  try {
    state.rows = await api("/data-quality");
    if (!state.rows.some((r) => r.symbol === state.symbol)) {
      // open the first stock that needs attention, else the first stock
      state.symbol = (state.rows.find((r) => r.status !== "clean") || state.rows[0] || {}).symbol || null;
    }
    renderList();
    if (state.symbol) await showStock(state.symbol);
    else $("dq-detail").innerHTML = "";
  } catch (err) {
    toast(err.message, true);
  } finally {
    state.loading = false;
  }
}

export function initDataQuality() {
  $("dq-scan").addEventListener("click", renderDataQuality);
  $("dq-list").addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-symbol]");
    if (row) showStock(row.dataset.symbol);
  });
}
