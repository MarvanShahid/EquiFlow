"use client";

import { useState } from "react";
import { cancelPriority, requestPriority } from "@/lib/api";
import { APPROACHES, type AmbulanceRec, type Approach, type EquiEvent, type Metrics, type Signal } from "@/lib/types";

/* ------------------------------------------------------------------ status */
export function StatusPanel({ signal, remaining, ambulances }: { signal: Signal; remaining: number | null; ambulances: AmbulanceRec[] }) {
  const active = ambulances.filter((a) => a.intersection_id === signal.id && a.status === "active");
  const target = signal.active_preempt;
  let title = "Normal cycle";
  let detail = signal.current
    ? `${signal.current} is ${signal.lamps[signal.current]}${remaining !== null ? `, ${Math.ceil(remaining)} s left` : ""}`
    : "Starting up";

  if (signal.mode === "PREEMPT" && target) {
    const served = signal.current === target && signal.stage === "GREEN";
    title = `Ambulance priority: ${target}`;
    detail = served ? `${target} is green and held until the ambulance clears` : `Clearing the junction for ${target}`;
  } else if (signal.mode === "RECOVERY") {
    title = "Fair recovery";
    detail = signal.recovery_plan.length
      ? `${signal.recovery_plan.join(", ")} get extra green after the ambulance`
      : "Last recovery green in progress";
  }

  return (
    <section className={`panel status mode-${signal.mode.toLowerCase()}`} aria-live="polite">
      <h2>{signal.name}</h2>
      <p className="status-title">{title}</p>
      <p className="status-detail">{detail}</p>
      {remaining !== null && (
        <p className="status-count">
          {Math.ceil(remaining)}
          <small>s left in this stage</small>
        </p>
      )}
      <ul className="amb-list" aria-label="Ambulances in view">
        {active.length === 0 ? (
          <li className="none">No ambulance in view</li>
        ) : (
          active.map((a) => (
            <li key={a.id}>
              <strong>{a.approach}</strong>
              <span>track {a.track_id}, {Math.round(a.confidence * 100)}% sure</span>
            </li>
          ))
        )}
      </ul>
      <p className="status-foot">Controller: {signal.controller.replace("_", " ")}</p>
    </section>
  );
}

/* ----------------------------------------------------------------- metrics */
const fmt = (v: number | null | undefined, unit = "") => (v === null || v === undefined ? "–" : `${v}${unit}`);

export function MetricsPanel({ m }: { m: Metrics }) {
  const rows: [string, string][] = [
    ["Ambulances detected", fmt(m.ambulance_detections)],
    ["Priority runs", fmt(m.preemptions)],
    ["Detection to green, last", fmt(m.preempt_latency_last_s, " s")],
    ["Detection to green, average", fmt(m.preempt_latency_avg_s, " s")],
    ["Vehicles in view", fmt(m.total_vehicles)],
    ["Longest wait", fmt(Math.round(m.max_wait_s), " s")],
  ];
  return (
    <section className="panel">
      <h2>Live metrics</h2>
      <dl className="metrics">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/* ---------------------------------------------------------------- controls */
export function ControlsPanel({ signal }: { signal: Signal }) {
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  };
  return (
    <section className="panel">
      <h2>Test ambulance priority</h2>
      <p className="hint">Sends a 20 second ambulance to an approach, as if the camera had seen one.</p>
      <div className="btn-grid">
        {APPROACHES.map((a: Approach) => (
          <button key={a} onClick={() => run(() => requestPriority(signal.id, a))} disabled={signal.ambulance[a]}>
            {a}
          </button>
        ))}
      </div>
      {APPROACHES.some((a) => signal.ambulance[a]) && (
        <button
          className="btn-quiet"
          onClick={() =>
            run(async () => {
              for (const a of APPROACHES) if (signal.ambulance[a]) await cancelPriority(signal.id, a);
            })
          }
        >
          Cancel priority
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

/* --------------------------------------------------------------- event log */
const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });

function describe(e: EquiEvent): { text: string; tone: "amb" | "dim" | "warn" | "ok" } | null {
  const a = e.approach as string | undefined;
  switch (e.type) {
    case "ambulance_detected":
      return { text: `Ambulance confirmed on ${a} (${Math.round(Number(e.confidence) * 100)}%)`, tone: "amb" };
    case "preempt_started":
      return { text: `Priority started for ${a}`, tone: "amb" };
    case "preempt_green":
      return { text: `${a} green, ${e.latency_s} s after detection`, tone: "ok" };
    case "preempt_switched":
      return { text: `Priority moved to ${a}`, tone: "amb" };
    case "preempt_ended":
      return { text: `Priority ended after ${e.duration_s} s`, tone: "amb" };
    case "preempt_timeout":
      return { text: `Priority on ${a} timed out and was released`, tone: "warn" };
    case "recovery_planned":
      return { text: `Recovery: ${(e.plan as string[]).join(", ")} get +${e.extra_green_s} s green`, tone: "ok" };
    case "manual_preempt":
      return { text: `Test priority sent to ${a}`, tone: "dim" };
    case "phase_changed":
      return { text: `${a} green for ${e.green_s} s (${e.source})`, tone: "dim" };
    case "system_started":
      return { text: `Backend started (${e.mode})`, tone: "dim" };
    default:
      return null;
  }
}

export function EventLog({ events, intersectionId }: { events: EquiEvent[]; intersectionId: string }) {
  const rows = events
    .filter((e) => !e.intersection_id || e.intersection_id === intersectionId)
    .map((e) => ({ e, d: describe(e) }))
    .filter((r) => r.d !== null)
    .slice(0, 40);
  return (
    <section className="panel log">
      <h2>Events</h2>
      {rows.length === 0 ? (
        <p className="hint">Nothing yet. Events appear here when an ambulance is detected or the signals change.</p>
      ) : (
        <ol>
          {rows.map(({ e, d }) => (
            <li key={e.id} className={`tone-${d!.tone}`}>
              <time>{time(e.ts)}</time>
              <span>{d!.text}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
