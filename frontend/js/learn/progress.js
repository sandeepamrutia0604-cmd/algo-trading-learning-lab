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
