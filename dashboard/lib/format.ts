/** Formatting helpers. Every helper returns "–" for missing values instead of inventing a number. */

export const DASH = "–";

export const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function num(v: number | null | undefined, digits = 0): string {
  return isNum(v) ? v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits }) : DASH;
}

export function clock(tsSeconds: number): string {
  return new Date(tsSeconds * 1000).toLocaleTimeString([], { hour12: false });
}

export function dateTime(tsSeconds: number): string {
  return new Date(tsSeconds * 1000).toLocaleString([], { hour12: false });
}

export function ago(tsSeconds: number, now = Date.now() / 1000): string {
  const s = Math.max(0, Math.round(now - tsSeconds));
  if (s < 60) return `${s} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)} h ago`;
}

export function duration(s: number | null | undefined): string {
  if (!isNum(s)) return DASH;
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const r = t % 60;
  if (h) return `${h} h ${m} min`;
  if (m) return `${m} min ${r} s`;
  return `${r} s`;
}

/** Simulation clock m:ss */
export function simClock(s: number): string {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

export const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

export const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Human name of a controller id as reported by the backend. */
export const CONTROLLER_LABEL: Record<string, string> = {
  adaptive: "EquiFlow adaptive",
  marl: "EquiFlow MARL",
  "marl (untrained: adaptive)": "EquiFlow MARL (no trained weights, adaptive fallback)",
  fixed_time: "EquiFlow fixed cycle",
  fixed: "SUMO fixed-time plan (baseline)",
  actuated: "SUMO actuated plan (baseline)",
  equiflow: "EquiFlow",
};
export const controllerName = (c: string | undefined | null) => (c ? CONTROLLER_LABEL[c] ?? c.replace(/_/g, " ") : DASH);

export const STAGE_LABEL: Record<string, string> = { GREEN: "Green", YELLOW: "Yellow (change)", ALL_RED: "All-red clearance" };
export const MODE_LABEL: Record<string, string> = { NORMAL: "Normal cycle", PREEMPT: "Emergency priority", RECOVERY: "Fair recovery" };
