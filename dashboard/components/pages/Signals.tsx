"use client";

import { Network, ShieldCheck, Siren, TrafficCone } from "lucide-react";
import Link from "next/link";
import { MODE_LABEL, controllerName } from "@/lib/format";
import { useLive } from "@/lib/live";
import { smoothRemaining, useTicker } from "@/lib/useEquiflow";
import { PhaseStatus, PriorityControls, ResetControl, SafetyChain, SignalHeads } from "../junction";
import { Badge, Banner, Card, Empty, LampPill, PageHeader } from "../ui";
import { JunctionUnavailable, MoreLink, SignalPicker, useSelectedSignal } from "./common";

export default function Signals() {
  useTicker(200);
  const receivedAt = useLive((s) => s.eq.receivedAt);
  const frame = useLive((s) => s.sumo.frame);
  const geometry = useLive((s) => s.sumo.geometry);
  const [signal, signals, pick] = useSelectedSignal();
  const remaining = signal ? smoothRemaining(signal.stage_remaining_s, receivedAt) : null;
  const flashing = !!signal?.output?.flashing;

  return (
    <div className="page">
      <PageHeader
        title="Traffic signal control"
        description="Current phase, signal heads and the safety chain between the controller and the lamps. Operator requests go to the backend, which validates them; the independent conflict monitor checks every lamp change and cannot be overridden from here."
        actions={<SignalPicker signals={signals} value={signal?.id} onChange={pick} />}
      />

      {!signal ? (
        <Card>
          <JunctionUnavailable />
        </Card>
      ) : (
        <>
          {flashing && (
            <Banner tone="crit" title={`${signal.name} is in latched fail-safe: all heads flashing red`}>
              Normal control is suspended. Investigate the fault shown under Safety chain, then request an operator reset. The
              backend refuses the reset while the cause is still present.
            </Banner>
          )}
          <div className="grid g-main-side">
            <div className="stack">
              <Card
                title={`${signal.name} (${signal.id})`}
                icon={TrafficCone}
                sub={`Controller: ${controllerName(signal.controller)}`}
                className={flashing ? "is-critical" : signal.mode === "PREEMPT" ? "is-emergency" : ""}
              >
                <PhaseStatus signal={signal} remaining={remaining} />
                <h4 className="section-title">Signal heads by approach</h4>
                <SignalHeads signal={signal} remaining={remaining} />
              </Card>
              <Card
                title="Emergency priority test"
                icon={Siren}
                sub="Simulate a confirmed emergency vehicle on one approach, e.g. to verify the response on site."
              >
                <PriorityControls signal={signal} />
              </Card>
            </div>
            <Card
              title="Safety chain"
              icon={ShieldCheck}
              sub="Controller → conflict monitor → output driver. A fault latches the fail-safe."
              className={flashing ? "is-critical" : ""}
            >
              <div className="stack">
                <SafetyChain signal={signal} />
                <ResetControl signal={signal} />
              </div>
            </Card>
          </div>
        </>
      )}

      <Card
        title="Simulated signal controllers (SUMO)"
        icon={Network}
        sub="Read-only here. Ambulance dispatch and test priority for these junctions are on the Simulation page."
        actions={<MoreLink href="/simulation">Simulation controls</MoreLink>}
        flush
      >
        {!geometry || !frame ? (
          <Empty compact icon={Network} title="No simulation running">
            <Link href="/simulation">Start a SUMO run</Link> to see its signal controllers.
          </Empty>
        ) : frame.junctions.length === 0 ? (
          <Empty compact title="This network has no traffic signals" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Signal state of each simulated junction</caption>
              <thead>
                <tr>
                  <th scope="col">Junction</th>
                  <th scope="col">Controller</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Approach lamps</th>
                  <th scope="col" className="r">Stage left</th>
                </tr>
              </thead>
              <tbody>
                {frame.junctions.map((j) => (
                  <tr key={j.id} className={j.mode === "PREEMPT" ? "is-emg" : undefined}>
                    <th scope="row">{j.id}</th>
                    <td>{controllerName(j.controller)}</td>
                    <td>
                      <Badge tone={j.mode === "PREEMPT" ? "emg" : j.mode === "RECOVERY" ? "warn" : "ok"}>{MODE_LABEL[j.mode] ?? j.mode}</Badge>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 12 }}>
                        {Object.entries(j.lamps).map(([a, l]) => (
                          <span key={a} className="row" style={{ gap: 4 }}>
                            <span className="subtle">{a}</span>
                            <LampPill lamp={l} />
                            {j.ambulance[a] && <Badge tone="emg" icon={Siren}>EV</Badge>}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="r num">{j.stage_remaining_s !== null ? `${Math.ceil(j.stage_remaining_s)} s` : "held"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
