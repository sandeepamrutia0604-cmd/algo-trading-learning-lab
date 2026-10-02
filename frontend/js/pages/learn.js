import { $ } from "../util.js";
import { hooks, store } from "../store.js";
import { MODULES, isReady } from "../learn/lessons.js";
import { completedCount, isDone, loadProgress, recordResult, saveProgress } from "../learn/progress.js";

const esc = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
/* Lesson text is escaped first, then **bold** and *italic* are turned into tags. */
const fmt = (text) => esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>");

const LETTERS = "ABCDE";
let progress = loadProgress();
let shownId = null; // the module currently drawn, so app-wide refreshes don't redraw it mid-lesson
let quiz = null; // { module, results: [{ attempts, correct, firstTry }] } for the quiz on screen

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

function renderProgressSummary() {
  const done = completedCount(progress, MODULES);
  $("learn-progress").innerHTML = `<div class="learn-bar"><i style="width:${(done / MODULES.length) * 100}%"></i></div>
    <span>${done} of ${MODULES.length} modules completed</span>`;
}

function renderList(current) {
  $("learn-modules").innerHTML = MODULES.map((m) => {
    const done = isDone(progress, m.id);
    const state = [m.id === current ? "on" : "", isReady(m) ? "" : "soon", done ? "done" : ""].join(" ").trim();
    return `<li><a class="learn-item ${state}" href="#/learn/${m.id}">
      <span class="num">${done ? "&#10003;" : m.id}</span>
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

/* ---------------- quiz ---------------- */

function quizHtml(module) {
  const record = progress[module.id];
  const banner = record?.done
    ? `<div class="quiz-banner">&#10003; Completed &middot; best score ${record.best} of ${record.total} on the first try</div>`
    : "";
  const questions = module.quiz
    .map(
      (item, q) => `<div class="quiz-q" data-q="${q}">
        <p class="quiz-text"><b>${q + 1}.</b> ${fmt(item.q)}</p>
        <div class="quiz-options">
          ${item.options.map((option, o) => `<button type="button" class="quiz-option" data-q="${q}" data-o="${o}"><span class="quiz-letter">${LETTERS[o]}</span><span>${fmt(option)}</span></button>`).join("")}
        </div>
        <div class="quiz-feedback" aria-live="polite" hidden></div>
      </div>`,
    )
    .join("");
  return `<h4 class="lesson-h">Check your understanding</h4>${banner}${questions}<div class="quiz-result" hidden></div>`;
}

function resetQuiz(module) {
  quiz = { module, results: module.quiz.map(() => ({ attempts: 0, correct: false, firstTry: false })) };
  $("quiz").innerHTML = quizHtml(module);
}

function finishQuiz() {
  const total = quiz.results.length;
  const firstTry = quiz.results.filter((r) => r.firstTry).length;
  progress = recordResult(progress, quiz.module.id, firstTry, total);
  saveProgress(progress);

  const verdict = firstTry === total ? "A perfect score." : "Re-read the explanations above if any of them surprised you.";
  const box = document.querySelector("#quiz .quiz-result");
  box.hidden = false;
  box.innerHTML = `<div><b>${firstTry} of ${total} right on the first try.</b> ${verdict} Module ${quiz.module.id} is complete.</div>
    <button type="button" class="btn" data-retake>Retake the quiz</button>`;
  renderList(quiz.module.id);
  renderProgressSummary();
}

function answer(button) {
  if (!quiz) return;
  const q = Number(button.dataset.q);
  const option = Number(button.dataset.o);
  const item = quiz.module.quiz[q];
  const result = quiz.results[q];
  if (result.correct) return;

  result.attempts += 1;
  const box = button.closest(".quiz-q");
  const feedback = box.querySelector(".quiz-feedback");
  feedback.hidden = false;
  if (option === item.answer) {
    result.correct = true;
    result.firstTry = result.attempts === 1;
    button.classList.add("correct");
    box.querySelectorAll(".quiz-option").forEach((b) => (b.disabled = true));
    feedback.className = "quiz-feedback good";
    feedback.innerHTML = `<b>&#10003; Correct.</b> ${fmt(item.why)}`;
    if (quiz.results.every((r) => r.correct)) finishQuiz();
  } else {
    button.classList.add("wrong");
    button.disabled = true;
    feedback.className = "quiz-feedback bad";
    feedback.textContent = "Not quite. Have another look and try a different answer.";
  }
}

/* ---------------- lesson ---------------- */

function renderLesson(module) {
  quiz = null;
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
    ${module.quiz ? `<section id="quiz" class="quiz"></section>` : ""}
    ${renderNav(module)}`;
  if (module.quiz) resetQuiz(module);
}

/* Called on every app-wide refresh (switching theme, pressing Play, ...). Only a change of
   lesson redraws it, so a half-finished quiz and the scroll position are left alone. */
export function renderLearn() {
  const id = selectedId();
  renderProgressSummary();
  renderList(id);
  if (id === shownId) return;
  shownId = id;
  renderLesson(MODULES.find((m) => m.id === id));
  window.scrollTo(0, 0);
}

export function initLearn() {
  $("learn-lesson").addEventListener("click", (event) => {
    const option = event.target.closest(".quiz-option");
    if (option) return answer(option);

    if (event.target.closest("[data-retake]")) {
      resetQuiz(quiz.module);
      $("quiz").scrollIntoView({ block: "start" });
      return;
    }

    const tryIt = event.target.closest("[data-tryit]");
    if (!tryIt) return;
    if (tryIt.dataset.symbol) store.symbol = tryIt.dataset.symbol;
    hooks.navigate(tryIt.dataset.route);
  });
}
