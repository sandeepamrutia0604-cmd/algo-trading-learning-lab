import { $ } from "../util.js";
import { hooks, store } from "../store.js";
import { MODULES, isReady } from "../learn/lessons.js";

const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
/* Lesson text is escaped first, then **bold** and *italic* are turned into tags. */
const fmt = (text) => esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>");

const RENDER = {
  h: (text) => `<h4 class="lesson-h">${fmt(text)}</h4>`,
  p: (text) => `<p>${fmt(text)}</p>`,
  list: (items) => `<ul>${items.map((item) => `<li>${fmt(item)}</li>`).join("")}</ul>`,
  note: (text) => `<div class="lesson-note">${fmt(text)}</div>`,
  example: (e) => `<div class="lesson-example"><b>${fmt(e.title)}</b><p>${fmt(e.text)}</p></div>`,
  terms: (items) => `<dl class="lesson-terms">${items.map(([term, meaning]) => `<dt>${fmt(term)}</dt><dd>${fmt(meaning)}</dd>`).join("")}</dl>`,
  tryit: (t) => `<div class="lesson-tryit">
      <div><b>Try it</b><p>${fmt(t.hint)}</p></div>
      <button class="btn btn-primary" data-tryit data-route="${esc(t.route)}" data-symbol="${esc(t.symbol || "")}">${esc(t.label)}</button>
    </div>`,
};

function renderBlock(block) {
  const kind = Object.keys(RENDER).find((key) => key in block);
  return kind ? RENDER[kind](block[kind]) : "";
}

/* #/learn or #/learn/3 -> the module number, defaulting to the first lesson. */
function selectedId() {
  const id = parseInt(location.hash.replace(/^#\//, "").split("/")[1], 10);
  return MODULES.some((m) => m.id === id) ? id : MODULES[0].id;
}

function renderList(current) {
  $("learn-modules").innerHTML = MODULES.map((m) => {
    const state = [m.id === current ? "on" : "", isReady(m) ? "" : "soon"].join(" ").trim();
    return `<li><a class="learn-item ${state}" href="#/learn/${m.id}">
      <span class="num">${m.id}</span>
      <span class="learn-title">${esc(m.title)}</span>
      ${isReady(m) ? `<span class="muted">${m.minutes} min</span>` : `<em>Soon</em>`}
    </a></li>`;
  }).join("");
}

function renderNav(module) {
  const previous = MODULES.find((m) => m.id === module.id - 1);
  const next = MODULES.find((m) => m.id === module.id + 1);
  const prevButton = previous ? `<a class="btn" href="#/learn/${previous.id}">&larr; ${esc(previous.title)}</a>` : `<span></span>`;
  let nextButton = `<span></span>`;
  if (next) {
    nextButton = isReady(next)
      ? `<a class="btn btn-primary" href="#/learn/${next.id}">${esc(next.title)} &rarr;</a>`
      : `<span class="btn lesson-nav-soon" aria-disabled="true">${esc(next.title)} &mdash; coming soon</span>`;
  }
  return `<div class="lesson-nav">${prevButton}${nextButton}</div>`;
}

function renderLesson(module) {
  const header = `<span class="chip">Module ${module.id} of ${MODULES.length}</span>
    <h2>${esc(module.title)}</h2>`;
  if (!isReady(module)) {
    $("learn-lesson").innerHTML = `${header}
      <p class="muted">${esc(module.summary)}</p>
      <div class="lesson-note">This lesson is coming soon. Lessons are being added one module at a time.</div>
      ${renderNav(module)}`;
    return;
  }
  $("learn-lesson").innerHTML = `${header}
    <p class="muted lesson-meta">About ${module.minutes} minutes &middot; ${esc(module.summary)}</p>
    ${module.blocks.map(renderBlock).join("")}
    ${renderNav(module)}`;
}

export function renderLearn() {
  const id = selectedId();
  const module = MODULES.find((m) => m.id === id);
  renderList(id);
  renderLesson(module);
  window.scrollTo(0, 0);
}

export function initLearn() {
  $("learn-lesson").addEventListener("click", (event) => {
    const button = event.target.closest("[data-tryit]");
    if (!button) return;
    if (button.dataset.symbol) store.symbol = button.dataset.symbol;
    hooks.navigate(button.dataset.route);
  });
}
