import { $, api } from "../util.js";
import { whyCard } from "../why.js";

export async function renderJournal() {
  const signals = await api("/signals?limit=100");
  $("journal-empty").hidden = signals.length > 0;
  $("journal-feed").innerHTML = signals
    .map(
      (s) => `<div class="panel journal-item">
        <div class="journal-head">
          <div><b>${s.date}</b> &middot; <span class="side-${s.signal.toLowerCase()}">${s.signal}</span> ${s.symbol}</div>
          <span class="chip">${s.strategy_name}</span>
        </div>
        ${whyCard(s)}
      </div>`,
    )
    .join("");
}
