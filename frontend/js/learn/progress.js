/* Learning progress, kept in the browser (localStorage) -- no backend involved. The shape is
 *   { "1": { done: true, best: 4, total: 5, at: "2026-10-02T..." }, ... }
 * where `best` is the most answers a learner has got right on the first try. Everything that
 * touches storage is wrapped in try/catch: private windows and blocked site data make
 * localStorage throw, and the lessons must still work (just without remembering). */

const KEY = "algo-lab-learn-progress";

export function loadProgress(storage = globalThis.localStorage) {
  try {
    const data = JSON.parse(storage.getItem(KEY));
    return data && typeof data === "object" && !Array.isArray(data) ? data : {};
  } catch (err) {
    return {};
  }
}

export function saveProgress(progress, storage = globalThis.localStorage) {
  try {
    storage.setItem(KEY, JSON.stringify(progress));
  } catch (err) {
    // not remembering is acceptable; the lesson itself still works
  }
}

/** A new progress object with module `moduleId` marked complete. Keeps the best score and the
 *  date of the first completion, so retaking a quiz can only improve the record. */
export function recordResult(progress, moduleId, firstTry, total, now = new Date()) {
  const previous = progress[moduleId];
  return {
    ...progress,
    [moduleId]: {
      done: true,
      best: Math.max(previous?.best ?? 0, firstTry),
      total,
      at: previous?.at ?? now.toISOString(),
    },
  };
}

export const isDone = (progress, moduleId) => Boolean(progress[moduleId]?.done);

/** The first module (in order) the learner hasn't completed, or undefined when all are done.
 *  Pass only modules that are written; "coming soon" ones can't be continued. */
export const nextModule = (progress, modules) => modules.find((m) => !isDone(progress, m.id));

export const completedCount = (progress, modules) => modules.filter((m) => isDone(progress, m.id)).length;

/* ---- moving progress between browsers or computers (a small file the learner downloads and loads again) ---- */

export const FILE_KIND = "algo-lab-learn-progress";

/** The object that is written to the downloaded file. */
export const progressFile = (progress, now = new Date()) => ({ kind: FILE_KIND, version: 1, exported_at: now.toISOString(), progress });

/** Read a progress file. Returns a clean progress object (only the fields we know), or throws an Error that says
 *  what is wrong in plain words. Nothing in the file is trusted: it may have been edited, or be something else. */
export function parseProgressFile(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new Error("That file isn't a Learn progress file (it can't be read).");
  }
  if (!data || data.kind !== FILE_KIND || typeof data.progress !== "object" || data.progress === null || Array.isArray(data.progress)) {
    throw new Error("That file isn't a Learn progress file from this app.");
  }
  const clean = {};
  for (const [id, entry] of Object.entries(data.progress)) {
    if (!/^\d{1,3}$/.test(id) || !entry || typeof entry !== "object") continue;
    const count = (n) => (Number.isInteger(n) && n >= 0 && n <= 1000 ? n : 0);
    clean[id] = { done: entry.done === true, best: count(entry.best), total: count(entry.total), at: typeof entry.at === "string" ? entry.at.slice(0, 40) : null };
  }
  return clean;
}

/** Combine two progress objects without ever losing anything: a module is done if either says so, the best score
 *  is the higher one, and the date is the earlier one. */
export function mergeProgress(current, incoming) {
  const merged = { ...current };
  for (const [id, entry] of Object.entries(incoming)) {
    const had = merged[id];
    merged[id] = had
      ? { done: had.done || entry.done, best: Math.max(had.best ?? 0, entry.best ?? 0), total: Math.max(had.total ?? 0, entry.total ?? 0), at: [had.at, entry.at].filter(Boolean).sort()[0] ?? null }
      : entry;
  }
  return merged;
}
