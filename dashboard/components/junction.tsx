"use client";

/* Building blocks for one camera-junction intersection (backend/app/runtime.py IntersectionRuntime):
   signal heads, phase status, the safety chain (output driver, conflict monitor, watchdog, fail-safe latch)
   and the operator controls. Controls only send requests; the backend validates every one of them, and the
   conflict monitor sits after the controller where the UI cannot reach it. */

import { Cpu, HardDrive, ShieldAlert, ShieldCheck, Siren, Timer, TimerReset, XCircle } from "lucide-react";
import { useState } from "react";
import { cancelPriority, requestPriority, resetSignalOutput } from "@/lib/api";
import { FAULT_LABEL } from "@/lib/events";
import { MODE_LABEL, STAGE_LABEL, clock, controllerName, num } from "@/lib/format";
import { APPROACHES, type AmbulanceRec, type Approach, type Signal } from "@/lib/types";
import { useSession } from "./session";
import { Badge, Empty, InlineMsg, KV, LampStack, LampWord, ReadOnlyNote, useCommand, useConfirm } from "./ui";

/* ------------------------------------------------------------------ heads */
export function SignalHeads({ signal, remaining }: { signal: Signal; remaining: number | null }) {
  const flashing = !!signal.output?.flashing;
  return (
    <ul className="heads" aria-label={`Signal heads at ${signal.name}`}>
      {APPROACHES.map((a) => {
        const cur = !flashing && signal.current === a && signal.stage !== "ALL_RED";
        const amb = signal.ambulance[a];
        return (
          <li key={a} className={`head-card${cur ? " is-current" : ""}${amb ? " is-emg" : ""}`}>
            <LampStack lamp={signal.lamps[a]} flashing={flashing} />
            <div className="head-info">
              <strong>{a}</strong>
              <LampWord lamp={signal.lamps[a]} flashing={flashing} />
              <span className="num">
                {cur ? (remaining !== null ? `${Math.ceil(remaining)} s left` : "held for priority") : `waiting ${Math.round(signal.waiting_s[a])} s`}
              </span>
              {amb && (
                <Badge tone="emg" icon={Siren}>
                  Emergency
                </Badge>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------------------ phase */
export function PhaseStatus({ signal, remaining }: { signal: Signal; remaining: number | null }) {
  const flashing = !!signal.output?.flashing;
  const total = signal.stage_remaining_s !== null ? signal.stage_elapsed_s + signal.stage_remaining_s : null;
  const pctDone = total && remaining !== null ? Math.min(100, Math.max(0, (100 * (total - remaining)) / total)) : null;
  const modeTone = flashing ? "crit" : signal.mode === "PREEMPT" ? "emg" : signal.mode === "RECOVERY" ? "warn" : "ok";
  return (
    <div className="stack">
      <div className="row">
        <Badge tone={modeTone} lg>
          {flashing ? "Fail-safe flash" : MODE_LABEL[signal.mode] ?? signal.mode}
        </Badge>
        {!flashing && <Badge lg icon={false}>{STAGE_LABEL[signal.stage] ?? signal.stage}</Badge>}
        {signal.mode === "PREEMPT" && signal.active_preempt && (
          <Badge tone="emg" lg icon={Siren}>
            Priority: {signal.active_preempt}
          </Badge>
        )}
      </div>
      <div className="phase-strip">
        <div>
          <div className="subtle" style={{ fontSize: 12 }}>
            {flashing ? "Normal operation suspended" : signal.current && signal.stage !== "ALL_RED" ? `${signal.current} approach` : "Clearance interval"}
          </div>
          <div className="phase-count num" aria-live="off">
            {flashing ? "—" : remaining !== null ? Math.ceil(remaining) : "Hold"}
            {!flashing && remaining !== null && <small>s remaining</small>}
          </div>
        </div>
        <KV
          rows={[
            ["Stage elapsed", `${num(signal.stage_elapsed_s, 1)} s`],
            ["Planned stage length", total !== null ? `${num(total, 1)} s` : "Held until clear"],
            ["Controller", controllerName(signal.controller)],
          ]}
        />
      </div>
      {pctDone !== null && !flashing && (
        <div className="progress" role="progressbar" aria-label="Stage progress" aria-valuenow={Math.round(pctDone)} aria-valuemin={0} aria-valuemax={100}>
          <i style={{ width: `${pctDone}%` }} />
        </div>
      )}
      {signal.mode === "RECOVERY" && signal.recovery_plan.length > 0 && (
        <InlineMsg tone="warn">Fair recovery: {signal.recovery_plan.join(", ")} get extra green next, longest wait first.</InlineMsg>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ safety chain */
type Tone = "ok" | "warn" | "crit" | "neutral";
function Item({ tone, icon: Icon, title, detail, status }: { tone: Tone; icon: typeof Cpu; title: string; detail: string; status: string }) {
  return (
    <li className={`safety-item ${tone}`}>
      <span className="si-icon" aria-hidden="true">
        <Icon size={16} />
      </span>
      <span className="si-text">
        <strong>{title}</strong>
        <span>{detail}</span>
      </span>
      <Badge tone={tone === "neutral" ? "neutral" : tone}>{status}</Badge>
    </li>
  );
}

export function SafetyChain({ signal }: { signal: Signal }) {
  const out = signal.output;
  if (!out) return <Empty compact title="No signal output status" icon={ShieldAlert}>This backend did not report its signal output.</Empty>;
  const d = out.driver;
  const fault = out.fault;
  const stuck = d.stuck && Object.keys(d.stuck).length ? Object.entries(d.stuck).map(([a, l]) => `${a}=${l}`).join(", ") : null;
  const driverTone: Tone = d.link_down ? "crit" : stuck ? "warn" : "ok";
  const driverName = d.driver === "none" ? "No hardware (software only)" : d.driver === "simulated" ? "Simulated signal controller" : d.driver;
  const monitorFault = fault && fault.kind !== "watchdog";
  const wdFault = fault?.kind === "watchdog";

  return (
    <ul className="safety" aria-label="Signal safety chain">
      <Item
        tone={driverTone}
        icon={HardDrive}
        title="Output driver"
        detail={`${driverName}${d.latency_s !== undefined ? `, ${d.latency_s} s latency` : ""}${d.writes !== undefined ? `, ${d.writes} writes` : ""}${stuck ? `, stuck lamps: ${stuck}` : ""}`}
        status={d.link_down ? "Link down" : stuck ? "Degraded" : "Connected"}
      />
      <Item
        tone={monitorFault ? "crit" : "ok"}
        icon={monitorFault ? ShieldAlert : ShieldCheck}
        title="Independent conflict monitor"
        detail={monitorFault ? `${FAULT_LABEL[fault!.kind] ?? fault!.kind}. ${fault!.detail}` : `Checks every command and read-back. ${out.commands.toLocaleString()} commands checked.`}
        status={monitorFault ? "Fault latched" : "Monitoring"}
      />
      <Item
        tone={wdFault ? "crit" : fault ? "neutral" : "ok"}
        icon={Timer}
        title="Watchdog"
        detail={wdFault ? `${FAULT_LABEL.watchdog}. ${fault!.detail}` : fault ? "Paused while the output is latched." : "Independent thread: trips if the controller stops sending commands."}
        status={wdFault ? "Tripped" : fault ? "Paused" : "Armed"}
      />
      <Item
        tone={out.flashing ? "crit" : "ok"}
        icon={out.flashing ? XCircle : ShieldCheck}
        title="Fail-safe latch"
        detail={
          out.flashing
            ? "All heads flashing red. No command reaches the signals until an operator reset is accepted."
            : `Not active. ${out.faults_total} fault${out.faults_total === 1 ? "" : "s"} since start, ${out.resets} reset${out.resets === 1 ? "" : "s"}.`
        }
        status={out.flashing ? "LATCHED" : "Clear"}
      />
    </ul>
  );
}

/** Operator reset of a latched output. The backend refuses it (409) while the cause is still present. */
export function ResetControl({ signal }: { signal: Signal }) {
  const { canOperate } = useSession();
  const { confirm, dialog } = useConfirm();
  const { run, busy } = useCommand();
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const flashing = !!signal.output?.flashing;
  if (!flashing && !result) return null;

  const onReset = async () => {
    const ok = await confirm({
      tone: "crit",
      title: `Reset the signal output at ${signal.name}?`,
      body: (
        <>
          <p>
            The backend brings the heads back to all-red and resumes normal operation only if the hardware reads back all-red and
            the controller link is up. If the cause is still present it refuses the reset and the fail-safe stays latched.
          </p>
          <p style={{ marginTop: 8 }}>Confirm that the junction has been checked on site.</p>
        </>
      ),
      confirmLabel: "Request reset",
    });
    if (!ok) return;
    setResult(null);
    let msg = "";
    const success = await run(`Reset ${signal.id} output`, async () => {
      const r = await resetSignalOutput(signal.id);
      msg = r.message;
      return r;
    }, () => `Backend accepted: ${msg}`);
    setResult(success ? { ok: true, text: `Reset accepted: ${msg}` } : { ok: false, text: "Reset refused by the backend. The fail-safe is still latched; see the notification for the reason." });
  };

  return (
    <div className="stack">
      {flashing && (
        <>
          {canOperate ? (
            <button type="button" className="btn danger" onClick={onReset} disabled={busy}>
              <TimerReset size={16} aria-hidden="true" /> Request operator reset
            </button>
          ) : (
            <ReadOnlyNote>An operator must reset the latched output.</ReadOnlyNote>
          )}
        </>
      )}
      {result &&
        (result.ok && flashing ? (
          <InlineMsg tone="crit">
            The reset was accepted, but the conflict monitor latched the fail-safe again
            {signal.output?.fault ? ` (${signal.output.fault.kind})` : ""}: the cause is still present.
          </InlineMsg>
        ) : (
          <InlineMsg tone={result.ok ? "ok" : "crit"}>{result.text}</InlineMsg>
        ))}
      {dialog}
    </div>
  );
}

/* ------------------------------------------------------------------ operator priority test */
const DURATIONS = [10, 20, 30, 60, 120];

export function PriorityControls({ signal }: { signal: Signal }) {
  const { canOperate } = useSession();
  const { confirm, dialog } = useConfirm();
  const { run, busy } = useCommand();
  const [duration, setDuration] = useState(20);
  const flashing = !!signal.output?.flashing;
  const active = APPROACHES.filter((a) => signal.ambulance[a]);

  const request = async (a: Approach) => {
    const ok = await confirm({
      tone: "emg",
      title: `Request emergency priority for ${a}?`,
      body: `This is a manual test: the controller treats it like a confirmed emergency vehicle on ${a} for ${duration} s. It still runs the minimum green, yellow and all-red before ${a} turns green, and the conflict monitor checks every lamp change. Other approaches will wait.`,
      confirmLabel: `Request ${duration} s priority`,
    });
    if (ok) await run(`Priority request ${signal.id} ${a}`, () => requestPriority(signal.id, a, duration), `Accepted: ${a} priority for ${duration} s.`);
  };
  const cancel = async (a: Approach) => {
    const ok = await confirm({
      tone: "warn",
      title: `Cancel priority on ${a}?`,
      body: "If a real emergency vehicle is still being detected on this approach, the cameras will request priority again.",
      confirmLabel: "Cancel priority",
    });
    if (ok) await run(`Cancel priority ${signal.id} ${a}`, () => cancelPriority(signal.id, a), `Priority on ${a} cancelled.`);
  };

  return (
    <div className="stack">
      {!canOperate && <ReadOnlyNote />}
      {flashing && <InlineMsg tone="crit">Priority requests are disabled while the output is latched in fail-safe: commands would not reach the signals.</InlineMsg>}
      <label className="field" style={{ maxWidth: 220 }}>
        <span>Test duration</span>
        <select className="select" value={duration} onChange={(e) => setDuration(Number(e.target.value))} disabled={!canOperate || flashing}>
          {DURATIONS.map((d) => (
            <option key={d} value={d}>
              {d} seconds
            </option>
          ))}
        </select>
      </label>
      <div className="approach-grid" role="group" aria-label="Request priority for an approach">
        {APPROACHES.map((a) => (
          <button
            key={a}
            type="button"
            className="btn emg"
            onClick={() => request(a)}
            disabled={!canOperate || flashing || busy || signal.ambulance[a]}
            title={signal.ambulance[a] ? `${a} already has priority` : `Request priority for ${a}`}
          >
            <Siren size={15} aria-hidden="true" />
            {a}
          </button>
        ))}
      </div>
      {active.length > 0 && (
        <div className="stack">
          <span className="field-label">Active priority</span>
          <div className="row">
            {active.map((a) => (
              <button key={a} type="button" className="btn sm" onClick={() => cancel(a)} disabled={!canOperate || busy}>
                <XCircle size={14} aria-hidden="true" /> Cancel {a}
              </button>
            ))}
          </div>
        </div>
      )}
      <p className="field-hint">Backend limits: 1 to 300 s. A 60 s fail-safe releases a stuck priority.</p>
      {dialog}
    </div>
  );
}

/* ------------------------------------------------------------------ ambulances */
export function AmbulanceTable({ ambulances, mode, emptyText }: { ambulances: AmbulanceRec[]; mode?: "live" | "sim"; emptyText?: string }) {
  if (!ambulances.length)
    return (
      <Empty compact icon={Siren} title="No emergency vehicles detected">
        {emptyText ?? "Detections appear here as soon as the camera pipeline confirms one."}
      </Empty>
    );
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">Emergency vehicles reported by the camera junction</caption>
        <thead>
          <tr>
            <th scope="col">Status</th>
            <th scope="col">Intersection</th>
            <th scope="col">Approach</th>
            <th scope="col">Track ID</th>
            <th scope="col" className="r">Confidence</th>
            <th scope="col">First seen</th>
            <th scope="col">Last seen</th>
            <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {ambulances.map((a) => (
            <tr key={a.id} className={a.status === "active" ? "is-emg" : undefined}>
              <td>
                {a.status === "active" ? (
                  <Badge tone="emg" icon={Siren}>
                    Active
                  </Badge>
                ) : (
                  <Badge icon={false}>Cleared</Badge>
                )}
              </td>
              <td>{a.intersection_id}</td>
              <td>{a.approach}</td>
              <td className="mono">{a.track_id}</td>
              <td className="r">{Math.round(a.confidence * 100)}%</td>
              <td className="num">{clock(a.first_seen)}</td>
              <td className="num">{clock(a.last_seen)}</td>
              <td>
                <Badge icon={false} tone={mode === "live" ? "info" : "neutral"}>
                  {mode === "live" ? "Camera pipeline" : "Simulated vision"}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
