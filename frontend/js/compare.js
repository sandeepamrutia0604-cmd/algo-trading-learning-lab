// Comparing stocks: aligning their price histories, rebasing them to 100 and working out the figures the Compare page
// shows. Pure logic (no DOM, no network) so it can be tested with `node --test frontend/js/compare.test.mjs`.
//
// Every series is { symbol, dates: ["2025-01-31", ...] (ascending ISO dates), closes: [...] }. Calendars differ
// (holidays, different history spans), so comparisons use only the dates *every* stock has: aligning first means a
// stock that skipped a day is never silently paired with the wrong day of another.
//
// Definitions (the page repeats them in plain words):
//   return          last / first - 1, over the shared dates in the period
//   volatility      standard deviation of daily returns x sqrt(252), as a percentage (annualised)
//   max drawdown    the largest fall from a peak to a later low, as a percentage of the peak
//   correlation     Pearson correlation of the two stocks' daily returns (+1 move together, -1 opposite)
//   beta            how much the first stock moved per 1% the other moved: covariance / variance of the other

export const PRESETS = { "1M": 30, "3M": 91, "6M": 182, "1Y": 365, all: null };
const TRADING_DAYS = 252;

/** The dates every series has, ascending, with each series' closes on exactly those dates. */
export function alignSeries(list) {
  if (!list.length) return { dates: [], series: [] };
  const lookups = list.map((s) => new Map(s.dates.map((d, i) => [d, s.closes[i]])));
  const dates = [...lookups[0].keys()].filter((d) => lookups.every((m) => m.has(d))).sort();
  return { dates, series: list.map((s, i) => ({ symbol: s.symbol, closes: dates.map((d) => lookups[i].get(d)) })) };
}

const daysBefore = (iso, days) => new Date(new Date(`${iso}T00:00:00Z`).getTime() - days * 86400000).toISOString().slice(0, 10);

/** Keep only the last `preset` ("1M", "3M", "6M", "1Y") of an aligned set, counted back from its last date; "all" keeps everything. */
export function applyPreset(aligned, preset) {
  const days = PRESETS[preset];
  if (days == null || !aligned.dates.length) return aligned;
  const cutoff = daysBefore(aligned.dates[aligned.dates.length - 1], days);
  const from = aligned.dates.findIndex((d) => d >= cutoff);
  return {
    dates: aligned.dates.slice(from),
    series: aligned.series.map((s) => ({ ...s, closes: s.closes.slice(from) })),
  };
}

/** Closes expressed as "start = 100". Empty when there is nothing to start from. */
export function rebase(values) {
  const base = values[0];
  return values.length && base > 0 ? values.map((v) => (v / base) * 100) : [];
}

/** How the first stock did against the second: their ratio, starting at 100. Above 100 means the first is ahead. */
export function relative(a, b) {
  return rebase(a.map((v, i) => (b[i] > 0 ? v / b[i] : NaN)));
}

export function periodReturn(values) {
  return values.length >= 2 && values[0] > 0 ? (values[values.length - 1] / values[0] - 1) * 100 : null;
}

export function maxDrawdown(values) {
  let peak = -Infinity;
  let worst = 0;
  for (const v of values) {
    peak = Math.max(peak, v);
    if (peak > 0) worst = Math.max(worst, ((peak - v) / peak) * 100);
  }
  return values.length >= 2 ? worst : null;
}

export const dailyReturns = (values) => values.slice(1).map((v, i) => v / values[i] - 1);

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const covariance = (xs, ys) => {
  const mx = mean(xs);
  const my = mean(ys);
  return xs.reduce((sum, x, i) => sum + (x - mx) * (ys[i] - my), 0) / (xs.length - 1);
};

export function volatility(values) {
  const returns = dailyReturns(values);
  if (returns.length < 2) return null;
  return Math.sqrt(covariance(returns, returns)) * Math.sqrt(TRADING_DAYS) * 100;
}

export function correlation(a, b) {
  const x = dailyReturns(a);
  const y = dailyReturns(b);
  if (x.length < 2 || x.length !== y.length) return null;
  const spread = Math.sqrt(covariance(x, x) * covariance(y, y));
  return spread > 1e-12 ? covariance(x, y) / spread : null;
}

export function beta(a, b) {
  const x = dailyReturns(a);
  const y = dailyReturns(b);
  if (x.length < 2 || x.length !== y.length) return null;
  const variance = covariance(y, y);
  return variance > 1e-12 ? covariance(x, y) / variance : null;
}

/**
 * The figures for an aligned set (the first series is the one the others are compared against).
 * @returns {{days: number, from: string|null, to: string|null,
 *            rows: {symbol: string, return_pct: number|null, volatility_pct: number|null, max_drawdown_pct: number|null}[],
 *            pairs: {symbol: string, correlation: number|null, beta: number|null, return_diff_pct: number|null}[]}}
 */
export function summarise(aligned) {
  const { dates, series } = aligned;
  const rows = series.map((s) => ({
    symbol: s.symbol,
    return_pct: periodReturn(s.closes),
    volatility_pct: volatility(s.closes),
    max_drawdown_pct: maxDrawdown(s.closes),
  }));
  const [first, ...others] = series;
  const pairs = others.map((o, i) => ({
    symbol: o.symbol,
    correlation: correlation(first.closes, o.closes),
    beta: beta(first.closes, o.closes),
    return_diff_pct: rows[0].return_pct !== null && rows[i + 1].return_pct !== null ? rows[0].return_pct - rows[i + 1].return_pct : null,
  }));
  return { days: dates.length, from: dates[0] ?? null, to: dates[dates.length - 1] ?? null, rows, pairs };
}
