import { $ } from "./util.js";

const KEY = "algo-lab-theme";

function apply(theme) {
  document.documentElement.dataset.theme = theme;
  $("theme-toggle").textContent = theme === "dark" ? "Light mode" : "Dark mode";
}

export function currentTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function initTheme(onChange) {
  apply(currentTheme());
  $("theme-toggle").addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem(KEY, next);
    } catch (e) {}
    onChange();
  });
}

export function themeColors() {
  const style = getComputedStyle(document.documentElement);
  const get = (name) => style.getPropertyValue(name).trim();
  return {
    text: get("--text"),
    muted: get("--muted"),
    line: get("--line"),
    panel: get("--panel"),
    up: get("--up"),
    down: get("--down"),
    accent: get("--accent"),
    warn: get("--warn"),
  };
}
