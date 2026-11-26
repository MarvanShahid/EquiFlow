"use client";

import { Siren } from "lucide-react";
import { MODE_LABEL, controllerName, num } from "@/lib/format";
import { sumoApi, type Decision, type JunctionSnap, type TlsGeo } from "@/lib/sumo";
import { useSession } from "../session";
import { Badge, Empty, KV, LampPill, ReadOnlyNote, useCommand, useConfirm } from "../ui";

/** Plain-language reason for a green, built only from the fields the backend put in the decision record. */
export function why(d: Decision, controller: string): string {
  const veh = d.vehicles ?? 0;
  const waited = d.waited_s ?? 0;
  const g = d.green_s !== undefined ? `${Math.round(d.green_s)} s` : "";
  const vw = `${veh} ${veh === 1 ? "vehicle" : "vehicles"}, waited ${Math.round(waited)} s`;
  switch (d.source) {
    case "preempt":
      return `${d.approach}: green for the emergency vehicle, held until it has crossed`;
    case "recovery":
      return `${d.approach}: ${g} recovery green. It waited ${Math.round(waited)} s while the emergency vehicle passed`;
    case "base":
      if (controller === "fixed_time") return `${d.approach}: ${g}, next in the fixed cycle`;
      if (controller.startsWith("marl") && !controller.includes("untrained")) return `${d.approach}: ${g}, chosen by the MARL agent (${vw})`;
      if (waited >= 90) return `${d.approach}: ${g}. It had waited ${Math.round(waited)} s, so the 90 s fairness limit forced its turn`;
      return `${d.approach}: ${g}. Busiest approach (${vw})`;
    default:
      return `${d.approach}: green from SUMO's ${d.source} plan (${vw})`;
  }
}

export default function JunctionPanel({ geo, snap, equiflow, simTime, running }: {
  geo: TlsGeo;
  snap: JunctionSnap | undefined;
  equiflow: boolean;
  simTime: number;
  running: boolean;
}) {
  const { canOperate } = useSession();
  const { confirm, dialog } = useConfirm();
  const { run, busy } = useCommand();

  if (!snap) return <Empty compact title="Waiting for the first frame…" />;

  const target = snap.active_preempt;
  const stageWord = snap.stage === "GREEN" ? "green" : snap.stage === "YELLOW" ? "yellow" : "all-red clearance";
  let detail = snap.current && snap.stage !== "ALL_RED" ? `${snap.current}: ${stageWord}` : "All-red clearance";
  if (snap.stage_remaining_s !== null && snap.current) detail += `, ${Math.ceil(snap.stage_remaining_s)} s left`;
  if (snap.mode === "PREEMPT" && target)
    detail = snap.current === target && snap.stage === "GREEN" ? `${target} is green and held until the emergency vehicle clears` : `Clearing the junction (yellow, then all-red) for ${target}`;
  else if (snap.mode === "RECOVERY")
    detail = snap.recovery_plan.length ? `${snap.recovery_plan.join(", ")} get extra green next` : "Last recovery green in progress";

  const dispatch = async (a: string) => {
    const ok = await confirm({
      tone: "emg",
      title: `Dispatch an ambulance from ${a}?`,
      body: `Adds a simulated ambulance to the SUMO run, approaching junction ${geo.id} from ${a}. It is labelled as a simulation event, never as a real detection.`,
      confirmLabel: "Dispatch",
    });
    if (ok) await run(`Dispatch ambulance ${geo.id} ${a}`, () => sumoApi.ambulance(geo.id, a), "Ambulance added to the simulation.");
  };
  const testPriority = async (a: string) => {
    const ok = await confirm({
      tone: "emg",
      title: `Test priority on ${geo.id} ${a}?`,
      body: "Gives this approach emergency priority for 20 s without an ambulance. The controller still runs minimum green, yellow and all-red first.",
      confirmLabel: "Request 20 s priority",
    });
    if (ok) await run(`Test priority ${geo.id} ${a}`, () => sumoApi.preempt(geo.id, a, 20), `Priority requested for ${a}.`);
  };

  return (
    <div className="stack">
      <div className="row">
        <Badge tone={snap.mode === "PREEMPT" ? "emg" : snap.mode === "RECOVERY" ? "warn" : "ok"} lg>
          {MODE_LABEL[snap.mode] ?? snap.mode}
        </Badge>
        <span className="muted">{detail}</span>
      </div>

      <div className="table-wrap">
        <table className="table">
          <caption className="sr-only">Approaches of junction {geo.id}</caption>
          <thead>
            <tr>
              <th scope="col">Approach</th>
              <th scope="col">Signal</th>
              <th scope="col" className="r" title="Vehicles the virtual camera tracks on this approach">
                In view
              </th>
              <th scope="col" className="r">Waiting</th>
            </tr>
          </thead>
          <tbody>
            {geo.approaches.map((a) => {
              const amb = snap.ambulance[a.id];
              return (
                <tr key={a.id} className={amb ? "is-emg" : undefined}>
                  <th scope="row">
                    {a.id}{" "}
                    {amb && (
                      <Badge tone="emg" icon={Siren}>
                        Emergency
                      </Badge>
                    )}
                  </th>
                  <td>
                    <LampPill lamp={snap.lamps[a.id]} />
                  </td>
                  <td className="r">{snap.vehicles[a.id] ?? 0}</td>
                  <td className="r">{Math.round(snap.waiting_s[a.id] ?? 0)} s</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {snap.phases.length > 0 && (
        <div className="ph-list" aria-label="Signal phases">
          <span className="field-label">Phases:</span>
          {snap.phases.map((p) => (
            <span key={p.id} className={p.id === snap.current && snap.stage !== "ALL_RED" ? `ph ph-${snap.stage.toLowerCase()}` : "ph"} title={`Serves ${p.approaches.join(", ")}`}>
              {p.id}
            </span>
          ))}
        </div>
      )}

      <div>
        <h4 className="section-title">Why this green</h4>
        {snap.decisions.length === 0 ? (
          <p className="muted">No signal change yet.</p>
        ) : (
          <ol className="why">
            {snap.decisions.slice(0, 5).map((d, i) => (
              <li key={`${d.t}-${i}`}>
                <time>{Math.max(0, Math.round(simTime - d.t))} s ago</time>
                <span className={d.source === "preempt" ? "src-preempt" : d.source === "recovery" ? "src-recovery" : undefined}>{why(d, snap.controller)}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {equiflow && (
        <KV
          rows={[
            ["Priority runs here", snap.stats.preemptions],
            ["Detection to green, average", snap.stats.latency_avg_s === null ? "–" : `${num(snap.stats.latency_avg_s, 1)} s`],
          ]}
        />
      )}

      <div>
        <h4 className="section-title">Send an ambulance from</h4>
        {!canOperate && <ReadOnlyNote />}
        <div className="approach-grid">
          {geo.approaches.map((a) => (
            <button key={a.id} type="button" className="btn sm" disabled={!canOperate || !running || busy} onClick={() => dispatch(a.id)}>
              {a.id}
            </button>
          ))}
        </div>
      </div>
      {equiflow && (
        <div>
          <h4 className="section-title">Test priority without an ambulance</h4>
          <div className="approach-grid">
            {geo.approaches.map((a) => (
              <button key={a.id} type="button" className="btn sm emg" disabled={!canOperate || !running || busy || snap.ambulance[a.id]} onClick={() => testPriority(a.id)}>
                <Siren size={13} aria-hidden="true" />
                {a.id}
              </button>
            ))}
          </div>
        </div>
      )}
      <p className="field-hint">Controller: {controllerName(snap.controller)}</p>
      {dialog}
    </div>
  );
}
