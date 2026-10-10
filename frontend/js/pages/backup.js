// The Backup tab on the Trade page: save everything the app knows to one file, put it back, and move the
// Learn progress (which lives only in this browser) to another computer.
import { $, CLIENT_ID, api, toast } from "../util.js";
import { downloadFile } from "../csv.js";
import { loadProgress, mergeProgress, parseProgressFile, progressFile, saveProgress } from "../learn/progress.js";

const size = (bytes) => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

export async function renderBackup() {
  try {
    const info = await api("/backup/info");
    $("bk-info").innerHTML =
      (info.location ? `Your data is in <code>${escapeText(info.location)}</code> (${size(info.database_bytes)}). ` : `Your data is ${size(info.database_bytes)}. `) +
      (info.safety_copies
        ? `${info.safety_copies} safety cop${info.safety_copies === 1 ? "y" : "ies"} of earlier data ${info.safety_copies === 1 ? "is" : "are"} kept; the newest is <code>${escapeText(info.newest_safety_copy)}</code>.`
        : "No restore has been done yet, so there are no safety copies.");
  } catch (err) {
    $("bk-info").textContent = "";
  }
}

const escapeText = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function downloadBackup() {
  const button = $("bk-download");
  button.disabled = true;
  try {
    const res = await fetch("/api/backup/download", { headers: { "X-Client-Id": CLIENT_ID } });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    const name = /filename="?([^";]+)"?/.exec(res.headers.get("content-disposition") || "")?.[1] || "algo-lab-backup.db";
    downloadFile(name, await res.blob());
    toast("Backup downloaded. Keep it somewhere safe.");
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
  }
}

async function restoreBackup() {
  const file = $("bk-file").files[0];
  if (!file) return toast("Choose a backup file first", true);
  if (
    !confirm(
      `Replace EVERYTHING in the app (portfolio, trades, strategies, saved backtests, alerts, settings and price history) with the contents of "${file.name}"?\n\n` +
        "A safety copy of your current data is saved first, but anything you have done since this backup was made will be gone from the app.",
    )
  )
    return;
  const button = $("bk-restore");
  button.disabled = true;
  try {
    const res = await fetch("/api/backup/restore", {
      method: "POST",
      headers: { "X-Client-Id": CLIENT_ID, "X-Algo-Backup": "restore", "Content-Type": "application/octet-stream" },
      body: file,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail || `HTTP ${res.status}`);
    $("bk-result").textContent = `Restored: ${data.stocks} stocks and ${data.trades} trades, market date ${data.market_date}. Your earlier data was saved to ${data.safety_copy}. Reloading...`;
    toast("Backup restored");
    setTimeout(() => location.reload(), 1500);
  } catch (err) {
    $("bk-result").textContent = "";
    toast(err.message, true);
    button.disabled = false;
  }
}

function downloadLearnProgress() {
  const json = JSON.stringify(progressFile(loadProgress()), null, 2);
  downloadFile("algo-lab-learn-progress.json", json, "application/json");
  toast("Learn progress downloaded");
}

async function loadLearnProgress() {
  const file = $("bk-progress-file").files[0];
  if (!file) return toast("Choose a Learn progress file first", true);
  try {
    const incoming = parseProgressFile(await file.text());
    const merged = mergeProgress(loadProgress(), incoming);
    saveProgress(merged);
    $("bk-progress-file").value = "";
    toast(`Learn progress loaded (${Object.keys(incoming).length} module${Object.keys(incoming).length === 1 ? "" : "s"}). Open Learn to see it.`);
  } catch (err) {
    toast(err.message, true);
  }
}

export function initBackup() {
  $("bk-download").addEventListener("click", downloadBackup);
  $("bk-restore").addEventListener("click", restoreBackup);
  $("bk-progress-download").addEventListener("click", downloadLearnProgress);
  $("bk-progress-load").addEventListener("click", loadLearnProgress);
}
