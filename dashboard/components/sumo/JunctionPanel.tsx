"use client";

import { useState } from "react";
import { sumoApi, type Decision, type JunctionSnap, type TlsGeo } from "@/lib/sumo";

function why(d: Decision, controller: string): string {
  const veh = d.vehicles ?? 0;
  const waited = d.waited_s ?? 0;
  const g = d.green_s !== undefined ? `${Math.round(d.green_s)} s` : "";
  switch (d.source) {
    case "preempt":
      return `${d.approach}: green for the ambulance, held until it has crossed`;
    case "recovery":
      return `${d.approach}: ${g} recovery green. It waited ${Math.round(waited)} s while the ambulance passed`;
    case "base":
      if (controller === "fixed_time") return `${d.approach}: ${g}, next in the fixed cycle`;
      if (controller.startsWith("marl") && !controller.includes("untrained"))
        return `${d.approach}: ${g}, chosen by the MARL agent (${veh} ${veh === 1 ? "vehicle" : "vehicles"}, waited ${Math.round(waited)} s)`;
      if (waited >= 90) return `${d.approach}: ${g}. It had waited ${Math.round(waited)} s, so the fairness limit forced its turn`;
      return `${d.approach}: ${g}. Busiest approach (${veh} ${veh === 1 ? "vehicle" : "vehicles"}, waited ${Math.round(waited)} s)`;
    default:
      return `${d.approach}: green from SUMO's ${d.source} plan (${veh} vehicles, waited ${Math.round(waited)} s)`;
  }
}

export default function JunctionPanel({
  geo,
  snap,
  equiflow,
  simTime,
}: {
  geo: TlsGeo;
  snap: JunctionSnap | undefined;
  equiflow: boolean;
  simTime: number;
}) {
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  };

  if (!snap) return <section className="panel">Waiting for the first frame…</section>;

  const target = snap.active_preempt;
  let title = "Normal cycle";
  const stageWord = snap.stage === "GREEN" ? "green" : snap.stage === "YELLOW" ? "yellow" : "all red (clearance)";
  let detail = snap.current && snap.stage !== "ALL_RED" ? `${snap.current}: ${stageWord}` : "All red (clearance)";
  if (snap.stage_remaining_s !== null && snap.current) detail += `, ${Math.ceil(snap.stage_remaining_s)} s left`;
  if (snap.mode === "PREEMPT" && target) {
    title = `Ambulance priority: ${target}`;
    detail =
      snap.current === target && snap.stage === "GREEN"
        ? `${target} is green and held until the ambulance clears`
        : `Clearing the junction (yellow, then all-red) for ${target}`;
  } else if (snap.mode === "RECOVERY") {
    title = "Fair recovery";
    detail = snap.recovery_plan.length
      ? `${snap.recovery_plan.join(", ")} get extra green next`
      : "Last recovery green in progress";
  }
  const ctrlName: Record<string, string> = {
    adaptive: "EquiFlow (adaptive + ambulance priority)",
    marl: "EquiFlow MARL (learned greens + ambulance priority)",
    "marl (untrained: adaptive)": "EquiFlow MARL: no trained weights found, using adaptive",
    fixed_time: "EquiFlow (fixed cycle + ambulance priority)",
    fixed: "SUMO fixed-time plan (baseline)",
    actuated: "SUMO actuated plan (baseline)",
  };

  return (
    <section className={`panel status mode-${snap.mode.toLowerCase()}`} aria-live="polite">
      <h2>Junction {geo.id}</h2>
      <p className="status-title">{title}</p>
      <p className="status-detail">{detail}</p>

      <table className="appr">
        <thead>
          <tr>
            <th>Approach</th>
            <th>Signal</th>
            <th title="Vehicles the camera tracks on this approach">In view</th>
            <th>Waiting</th>
          </tr>
        </thead>
        <tbody>
          {geo.approaches.map((a) => {
            const lamp = snap.lamps[a.id] ?? "red";
            const amb = snap.ambulance[a.id];
            return (
              <tr key={a.id} className={amb ? "is-amb" : undefined}>
                <th scope="row">
                  {a.id}
                  {amb && <span className="tag-amb">ambulance</span>}
                </th>
                <td>
                  <span className={`chip chip-${lamp}`} /> {lamp}
                </td>
                <td>{snap.vehicles[a.id] ?? 0}</td>
                <td>{Math.round(snap.waiting_s[a.id] ?? 0)} s</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {snap.phases.length > 0 && (
        <p className="phases">
          Phases:{" "}
          {snap.phases.map((p) => (
            <span key={p.id} className={p.id === snap.current && snap.stage !== "ALL_RED" ? `ph ph-${snap.stage.toLowerCase()}` : "ph"}>
              {p.id}
            </span>
          ))}
        </p>
      )}

      <h3>Why this green</h3>
      {snap.decisions.length === 0 ? (
        <p className="hint">No signal change yet.</p>
      ) : (
        <ol className="why">
          {snap.decisions.slice(0, 5).map((d, i) => (
            <li key={`${d.t}-${i}`} className={d.source === "preempt" ? "tone-amb" : d.source === "recovery" ? "tone-warn" : undefined}>
              <time>{Math.max(0, Math.round(simTime - d.t))} s ago</time>
              <span>{why(d, snap.controller)}</span>
            </li>
          ))}
        </ol>
      )}

      {equiflow && (
        <dl className="metrics compact">
          <div>
            <dt>Priority runs here</dt>
            <dd>{snap.stats.preemptions}</dd>
          </div>
          <div>
            <dt>Detection to green, average</dt>
            <dd>{snap.stats.latency_avg_s === null ? "–" : `${snap.stats.latency_avg_s} s`}</dd>
          </div>
        </dl>
      )}

      <h3>Send an ambulance from</h3>
      <div className="btn-grid">
        {geo.approaches.map((a) => (
          <button key={a.id} onClick={() => run(() => sumoApi.ambulance(geo.id, a.id))}>
            {a.id}
          </button>
        ))}
      </div>
      {equiflow && (
        <>
          <h3>Test priority without an ambulance</h3>
          <div className="btn-grid">
            {geo.approaches.map((a) => (
              <button key={a.id} className="btn-amb" disabled={snap.ambulance[a.id]} onClick={() => run(() => sumoApi.preempt(geo.id, a.id, 20))}>
                {a.id}
              </button>
            ))}
          </div>
        </>
      )}
      {error && <p className="error">{error}</p>}
      <p className="status-foot">Controller: {ctrlName[snap.controller] ?? snap.controller}</p>
    </section>
  );
}
