/* Live updates: the backend tells every open tab "something changed" over a WebSocket (see
 * backend/app/live.py), and the tab re-reads what it shows. Messages carry no data, only the kind
 * of change, so this never needs to merge state: it just calls `onChange`.
 *
 * - A tab ignores changes it made itself (it already refreshed), via the X-Client-Id it sends.
 * - A burst of changes (another tab playing the market) becomes one refresh at a time.
 * - A hidden tab doesn't redraw its charts in the background; it catches up when shown again.
 * - If the connection drops (the backend restarted, say) it reconnects with a growing delay and
 *   refreshes once it is back, since it may have missed changes. */

import { $, CLIENT_ID } from "./util.js";

const DEBOUNCE_MS = 150;
const FIRST_RETRY_MS = 1000;
const MAX_RETRY_MS = 10000;

export function initLive(onChange) {
  const pill = $("live-status");
  const pending = new Set(); // kinds of change waiting to be handled
  let socket = null;
  let retryMs = FIRST_RETRY_MS;
  let flushTimer = null;
  let running = false;
  let wasDown = false;

  const show = (state, text, title) => {
    if (!pill) return;
    pill.className = `status-pill ${state}`;
    pill.textContent = text;
    pill.title = title;
  };

  async function flush() {
    flushTimer = null;
    if (document.hidden || !pending.size) return; // a hidden tab catches up when it is shown again
    if (running) {
      flushTimer = setTimeout(flush, DEBOUNCE_MS);
      return;
    }
    const kinds = new Set(pending);
    pending.clear();
    running = true;
    try {
      await onChange(kinds);
    } finally {
      running = false;
    }
  }

  function schedule(kind) {
    pending.add(kind);
    if (!flushTimer) flushTimer = setTimeout(flush, DEBOUNCE_MS);
  }

  function connect() {
    try {
      socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws`);
    } catch (err) {
      return retry();
    }
    socket.onopen = () => {
      retryMs = FIRST_RETRY_MS;
      show("ok", "Live updates on", "Other tabs' changes appear here as they happen");
      if (wasDown) schedule("reconnected"); // changes may have happened while we were away
    };
    socket.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch (err) {
        return;
      }
      if (message.type === "changed" && message.origin !== CLIENT_ID) schedule(message.kind || "other");
    };
    socket.onclose = () => {
      wasDown = true;
      show("error", "Live updates off", "Reconnecting...");
      retry();
    };
    socket.onerror = () => socket.close();
  }

  function retry() {
    setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && pending.size && !flushTimer) flushTimer = setTimeout(flush, 0);
  });

  show("", "Live updates...", "Connecting");
  connect();
}
