/* Plain-language descriptions, severities and categories for the backend's events.
   Runtime events come from the camera-junction controller (/ws, /api/events); SUMO events from the simulation
   frames (/ws/sumo). Unknown event types are still listed (as their raw type) so nothing is silently hidden. */

import type { SumoEvent } from "./sumo";
import type { EquiEvent } from "./types";

export type Severity = "crit" | "warn" | "emg" | "ok" | "info";
export type Category = "safety" | "emergency" | "signal" | "operator" | "system";
export type Origin = "junction" | "simulation";

export const SEVERITY_LABEL: Record<Severity, string> = {
  crit: "Critical",
  warn: "Warning",
  emg: "Emergency",
  ok: "Resolved",
  info: "Info",
};
export const CATEGORY_LABEL: Record<Category, string> = {
  safety: "Safety",
  emergency: "Emergency",
  signal: "Signal",
  operator: "Operator / access",
  system: "System",
};

/** Conflict-monitor fault kinds (backend/app/signals/monitor.py), in plain words. */
export const FAULT_LABEL: Record<string, string> = {
  conflict: "Two conflicting approaches were non-red together",
  no_yellow: "A green ended without its yellow",
  short_yellow: "A yellow was too short",
  short_all_red: "A green started before the all-red was over",
  short_green: "A green was too short (flicker)",
  watchdog: "The controller stopped sending commands (watchdog)",
  mismatch: "The signals do not show what was commanded",
  bad_state: "An invalid lamp state was commanded",
};

export interface Described {
  text: string;
  severity: Severity;
  category: Category;
  /** how the event came about, when it matters for trust: a manual test is not a detection */
  provenance?: "manual" | "simulated" | "detected";
}

const pct = (v: unknown) => `${Math.round(Number(v) * 100)}%`;

export function describeRuntime(e: EquiEvent, mode?: "live" | "sim"): Described {
  const a = e.approach as string | undefined;
  const at = e.intersection_id ? `${e.intersection_id}${a ? ` ${a}` : ""}` : a ?? "";
  const det = mode === "live" ? "detected" : "simulated";
  switch (e.type) {
    case "ambulance_detected":
      return {
        text: `${at}: ambulance confirmed by ${mode === "live" ? "the camera pipeline" : "the simulated vision source"} (${pct(e.confidence)} confidence)`,
        severity: "emg",
        category: "emergency",
        provenance: det,
      };
    case "preempt_started":
      return { text: `${at}: emergency priority started`, severity: "emg", category: "emergency" };
    case "preempt_green":
      return { text: `${at}: green given ${e.latency_s} s after detection`, severity: "emg", category: "emergency" };
    case "preempt_switched":
      return { text: `${at}: priority moved to ${a}`, severity: "emg", category: "emergency" };
    case "preempt_ended":
      return { text: `${e.intersection_id ?? ""}: priority ended after ${e.duration_s} s`.trim(), severity: "ok", category: "emergency" };
    case "preempt_timeout":
      return { text: `${at}: priority timed out and was released (fail-safe limit)`, severity: "warn", category: "emergency" };
    case "manual_preempt":
      return { text: `${at}: operator test priority requested (${e.duration_s ?? "?"} s)`, severity: "info", category: "operator", provenance: "manual" };
    case "manual_preempt_cancelled":
      return { text: `${at}: operator cancelled the test priority`, severity: "info", category: "operator", provenance: "manual" };
    case "recovery_planned":
      return { text: `${e.intersection_id ?? ""}: fair recovery, ${((e.plan as string[]) ?? []).join(", ")} served first`.trim(), severity: "info", category: "signal" };
    case "green_extended":
      return { text: `${at}: green extended, still the busiest approach (${e.vehicles} vehicles)`, severity: "info", category: "signal" };
    case "green_ended_early":
      return { text: `${at}: green ended early after ${e.after_s} s (no vehicles left)`, severity: "info", category: "signal" };
    case "phase_changed":
      return { text: `${at}: green for ${e.green_s} s (${e.source})`, severity: "info", category: "signal" };
    case "signal_fault":
      return {
        text: `${e.intersection_id ?? ""}: conflict monitor latched fail-safe flash. ${FAULT_LABEL[String(e.kind)] ?? e.kind}${e.detail ? ` (${e.detail})` : ""}`.trim(),
        severity: "crit",
        category: "safety",
      };
    case "signal_reset":
      return { text: `${e.intersection_id ?? ""}: signal output reset, cleared ${e.cleared}`.trim(), severity: "ok", category: "safety" };
    case "signal_reset_requested":
      return e.ok
        ? { text: `${e.intersection_id}: operator reset accepted (${e.message})`, severity: "ok", category: "operator" }
        : { text: `${e.intersection_id}: operator reset refused: ${e.message}`, severity: "warn", category: "operator" };
    case "stale_event_rejected":
      return { text: `${at}: stale detection rejected (${e.age_s} s old)`, severity: "warn", category: "safety" };
    case "api_write":
      return {
        text: `${e.method} ${e.path} by ${e.role ?? "?"} from ${e.client ?? "?"}: HTTP ${e.status ?? "?"}`,
        severity: Number(e.status) >= 400 ? "warn" : "info",
        category: "operator",
      };
    case "auth_failed":
      return { text: `Failed sign-in from ${e.client ?? "unknown client"}`, severity: "warn", category: "operator" };
    case "mode_changed":
      return { text: `${e.intersection_id ?? "Controller"}: mode changed${e.to_mode ? ` to ${String(e.to_mode).toLowerCase()}` : ""}`, severity: "info", category: "signal" };
    case "system_started":
      return { text: `Backend started (${e.mode} mode, ${e.controller} controller)`, severity: "info", category: "system" };
    default:
      return { text: `${e.type}${at ? ` (${at})` : ""}`, severity: "info", category: "system" };
  }
}

export function describeSumo(e: SumoEvent): Described {
  const a = e.approach;
  const at = e.tls ? `${e.tls}${a ? ` ${a}` : ""}` : a ?? "";
  switch (e.type) {
    case "ambulance_dispatched":
      return { text: `Ambulance dispatched into the simulation${e.tls ? ` towards ${e.tls} from ${a}` : ""}`, severity: "info", category: "emergency", provenance: "manual" };
    case "ambulance_detected":
      return { text: `${at}: virtual camera confirmed an ambulance ${e.distance_m} m out (${pct(e.confidence)})`, severity: "emg", category: "emergency", provenance: "simulated" };
    case "corridor_request":
      return { text: `${at}: green corridor requested, ambulance ${e.distance_m} m away (about ${e.eta_s} s)`, severity: "emg", category: "emergency" };
    case "preempt_started":
      return { text: `${at}: emergency priority started`, severity: "emg", category: "emergency" };
    case "preempt_green":
      return { text: `${at}: green ${e.latency_s} s after detection`, severity: "emg", category: "emergency" };
    case "preempt_ended":
      return { text: `${e.tls}: priority ended after ${e.duration_s} s`, severity: "ok", category: "emergency" };
    case "recovery_planned":
      return { text: `${e.tls}: fair recovery, ${((e.plan as string[]) ?? []).join(", ")} served first`, severity: "info", category: "signal" };
    case "green_extended":
      return { text: `${at}: green extended, still the busiest (${e.vehicles} vehicles)`, severity: "info", category: "signal" };
    case "green_ended_early":
      return { text: `${at}: green ended early after ${e.after_s} s`, severity: "info", category: "signal" };
    case "preempt_timeout":
      return { text: `${at}: priority timed out (fail-safe limit)`, severity: "warn", category: "emergency" };
    case "manual_preempt":
      return { text: `${at}: operator test priority (no ambulance)`, severity: "info", category: "operator", provenance: "manual" };
    case "phase_changed":
      return { text: `${at}: green for ${e.green_s} s (${e.source})`, severity: "info", category: "signal" };
    case "mode_changed":
      return { text: `${e.tls}: mode changed${e.to_mode ? ` to ${String(e.to_mode).toLowerCase()}` : ""}`, severity: "info", category: "signal" };
    case "sumo_started":
      return { text: `Simulation started (${e.network}, ${e.scenario}, ${e.controller})`, severity: "info", category: "system" };
    case "sumo_finished":
      return { text: "Simulation finished", severity: "info", category: "system" };
    default:
      return { text: `${e.type}${at ? ` (${at})` : ""}`, severity: "info", category: "system" };
  }
}

export interface FeedItem {
  key: string;
  ts: number; // unix seconds
  simTime?: number;
  origin: Origin;
  type: string;
  d: Described;
}

/** Merges the event bus (/ws, /api/events) with the SUMO frames' events. The backend publishes SUMO events on the
 *  same bus (origin "sumo", same id), so items are keyed by id and classified by their origin, never duplicated. */
export function toFeed(runtime: EquiEvent[], sumo: SumoEvent[], mode?: "live" | "sim"): FeedItem[] {
  const byId = new Map<number, FeedItem>();
  for (const e of runtime) {
    if (e.origin === "sumo") {
      const se = e as unknown as SumoEvent;
      byId.set(e.id, { key: `e${e.id}`, ts: e.ts, simTime: se.sim_time, origin: "simulation", type: e.type, d: describeSumo(se) });
    } else byId.set(e.id, { key: `e${e.id}`, ts: e.ts, origin: "junction", type: e.type, d: describeRuntime(e, mode) });
  }
  for (const e of sumo) byId.set(e.id, { key: `e${e.id}`, ts: e.ts, simTime: e.sim_time, origin: "simulation", type: e.type, d: describeSumo(e) });
  return [...byId.values()].sort((x, y) => y.ts - x.ts);
}

/** Events that should raise the notification indicator. */
export const NOTIFY: Severity[] = ["crit", "warn", "emg"];
