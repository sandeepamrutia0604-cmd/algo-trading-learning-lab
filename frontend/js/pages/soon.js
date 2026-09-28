import { $ } from "../util.js";

const INFO = {
  learn: {
    title: "Learn",
    phase: "Learning Mode",
    blurb: "Short lessons with interactive exercises that use this simulator, in the order the concepts build on each other.",
    items: [
      "What is a stock, an order, a portfolio, an indicator, a strategy",
      "What is backtesting, risk management, overfitting and paper trading",
      "Each lesson: a short explanation, an example, an exercise and a quiz",
    ],
  },
};

export function renderSoon(route) {
  const info = INFO[route];
  $("soon-phase").textContent = `Planned: ${info.phase}`;
  $("soon-title").textContent = info.title;
  $("soon-blurb").textContent = info.blurb;
  $("soon-list").innerHTML = info.items.map((item) => `<li>${item}</li>`).join("");
}
