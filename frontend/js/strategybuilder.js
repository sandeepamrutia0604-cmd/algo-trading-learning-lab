// The "pick a strategy type and its settings, or build custom rules" part of a builder form, for a page whose
// element ids all start with `prefix` (<prefix>-type, -desc, -params, -rule, -custom, -entry-rows ...). The Portfolio
// page uses it; the older Backtests page still carries its own copy of the same logic.
import { $ } from "./util.js";
import { store } from "./store.js";
import * as rb from "./rulebuilder.js";

export function createStrategyBuilder(prefix) {
  const el = (name) => $(`${prefix}-${name}`);
  const typeOf = (key) => store.strategyTypes.find((t) => t.key === key);
  const isCustom = () => el("type").value === "custom";

  function readParams() {
    const values = {};
    el("params").querySelectorAll("input[data-param]").forEach((input) => {
      values[input.dataset.param] = input.dataset.kind === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
    });
    return values;
  }

  function renderRule() {
    const type = typeOf(el("type").value);
    if (!type) return;
    const values = readParams();
    const fill = (text) => text.replace(/\{(\w+)\}/g, (_, key) => (Number.isNaN(values[key]) || values[key] === undefined ? "?" : values[key]));
    el("rule").innerHTML = `<div><b class="up">BUY</b> when ${fill(type.entry_text)}</div><div><b class="down">SELL</b> when ${fill(type.exit_text)}</div>`;
  }

  function renderTypeFields() {
    const type = typeOf(el("type").value);
    if (!type) return;
    el("desc").innerHTML = `<p>${type.summary}</p><p><b class="up">Works best:</b> ${type.works_best}</p><p><b class="down">Struggles:</b> ${type.struggles}</p>`;
    el("params").innerHTML = type.params
      .map(
        (p) => `<label class="field">${p.label}
          <input type="number" data-param="${p.name}" data-kind="${p.kind}" min="${p.min}" max="${p.max}" step="${p.step}" value="${p.default}" />
        </label>`,
      )
      .join("");
    el("params").querySelectorAll("input").forEach((input) => input.addEventListener("input", renderRule));
    renderRule();
  }

  const readRules = () => ({ entry: rb.readSide(el("entry-rows"), el("entry-logic").value), exit: rb.readSide(el("exit-rows"), el("exit-logic").value) });
  const updatePreview = () => (el("custom-preview").textContent = rb.ruleSummaryText(readRules()));

  function renderCustomRules(rules) {
    el("entry-logic").value = rules.entry.logic;
    el("exit-logic").value = rules.exit.logic;
    rb.renderSide(el("entry-rows"), rules.entry);
    rb.renderSide(el("exit-rows"), rules.exit);
    updatePreview();
  }

  function applyDefaults() {
    const custom = isCustom();
    el("desc").hidden = custom;
    el("params").hidden = custom;
    el("rule").hidden = custom;
    el("custom").hidden = !custom;
    if (custom) renderCustomRules(rb.DEFAULT_RULES);
    else renderTypeFields();
  }

  return {
    /** Fill the type list once the strategy types are known (and again if they change). */
    render() {
      const select = el("type");
      if (select.options.length !== store.strategyTypes.length + 1) {
        select.innerHTML = store.strategyTypes.map((t) => `<option value="${t.key}">${t.label}</option>`).join("") + `<option value="custom">Custom (build your own rules)</option>`;
        applyDefaults();
      }
    },
    /** {type, params} or {type: "custom", rules}, ready to merge into a request body. */
    read() {
      return isCustom() ? { type: "custom", rules: readRules() } : { type: el("type").value, params: readParams() };
    },
    /** Put a saved request's strategy back in the form. */
    write(req) {
      el("type").value = req.type;
      applyDefaults();
      if (req.type === "custom") return renderCustomRules(req.rules);
      for (const [name, value] of Object.entries(req.params || {})) {
        const input = el("params").querySelector(`input[data-param="${name}"]`);
        if (input) input.value = value;
      }
      renderRule();
    },
    init() {
      el("type").addEventListener("change", applyDefaults);
      el("entry-add").addEventListener("click", () => {
        rb.addRow(el("entry-rows"));
        updatePreview();
      });
      el("exit-add").addEventListener("click", () => {
        rb.addRow(el("exit-rows"));
        updatePreview();
      });
      rb.initSide(el("entry-rows"), updatePreview);
      rb.initSide(el("exit-rows"), updatePreview);
      el("entry-logic").addEventListener("change", updatePreview);
      el("exit-logic").addEventListener("change", updatePreview);
    },
  };
}
