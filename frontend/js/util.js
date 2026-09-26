export const $ = (id) => document.getElementById(id);

export const money = (n) => {
  const rounded = Math.round(Number(n) * 100) / 100;
  const text = Math.abs(rounded).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (rounded < 0 ? "-₹" : "₹") + text;
};

export const signedMoney = (n) => (Math.round(Number(n) * 100) > 0 ? "+" : "") + money(n);

export const percent = (n) => {
  const rounded = Math.round(Number(n) * 100) / 100;
  return (rounded === 0 ? 0 : rounded).toFixed(2) + "%";
};

export const signedPercent = (n) => (Math.round(Number(n) * 100) > 0 ? "+" : "") + percent(n);

export const pnlClass = (n) => (Math.round(Number(n) * 100) > 0 ? "up" : Math.round(Number(n) * 100) < 0 ? "down" : "");

export function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = "toast" + (isError ? " error" : "");
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 3500);
}

export async function api(path, options) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

export function sparkline(values, width = 64, height = 26) {
  if (!values || values.length < 2) return `<svg class="spark" width="${width}" height="${height}"></svg>`;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = 3 + (height - 6) * (1 - (v - min) / span);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const color = values[values.length - 1] >= values[0] ? "var(--up)" : "var(--down)";
  return `<svg class="spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}
