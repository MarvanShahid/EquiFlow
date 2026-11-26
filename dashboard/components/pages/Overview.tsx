"use client";

import {
  Activity,
  Car,
  Clock,
  Gauge,
  HeartPulse,
  ListOrdered,
  Network,
  Siren,
  TrafficCone,
  Waypoints,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { MODE_LABEL, isNum, mean, num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { VCOLOR, VTYPES } from "@/lib/sumo";
import { smoothRemaining, useTicker } from "@/lib/useEquiflow";
import { SignalHeads } from "../junction";
import Plan from "../Plan";
import NetworkCanvas from "../sumo/NetworkCanvas";
import { Badge, Card, Empty, Kpi, PageHeader } from "../ui";
import { ActivityFeed, JunctionUnavailable, MoreLink, SignalPicker, useSelectedSignal } from "./common";

const simState = (st?: string) =>
  st === "starting" ? "Simulation starting…" : st === "error" ? "Simulation error" : st === "finished" ? "Simulation finished" : "Simulation not running";

export default function Overview() {
  useTicker(250);
  const snapshot = useLive((s) => s.eq.snapshot);
  const receivedAt = useLive((s) => s.eq.receivedAt);
  const eqLink = useLive((s) => s.eq.link);
  const health = useLive((s) => s.health);
  const frame = useLive((s) => s.sumo.frame);
  const geometry = useLive((s) => s.sumo.geometry);
  const sumoStatus = useLive((s) => s.sumo.status);
  const [signal, signals, pick] = useSelectedSignal();

  const k = useMemo(() => {
    const sigs = snapshot?.intersections ?? [];
    const running = sumoStatus?.state === "running" || sumoStatus?.state === "paused";
    const tlsCount = running ? (geometry?.tls.length ?? 0) : 0;
    // queue: calibrated metres when any lane is calibrated, else queued vehicles in configured zones
    const laneM = sigs.flatMap((s) => Object.values(s.lanes ?? {}).flatMap((l) => Object.values(l ?? {}).map((q) => q.queue_m))).filter(isNum);
    const zoneQ = sigs.flatMap((s) => Object.values(s.queues ?? {})).filter(isNum);
    // simulation: mean wait of completed trips, weighted by trips per vehicle class
    const pc = frame?.metrics.per_class;
    let w = 0;
    let n = 0;
    if (pc)
      for (const v of VTYPES) {
        const c = pc[v];
        if (c && isNum(c.mean_waiting_s) && c.completed > 0) {
          w += c.mean_waiting_s * c.completed;
          n += c.completed;
        }
      }
    const latched = sigs.filter((s) => s.output?.flashing).length;
    const srcDown = sigs.flatMap((s) => Object.values(s.sources)).filter((x) => !x.ok).length;
    const issues: string[] = [];
    if (health.ok === false) issues.push("backend unreachable");
    if (eqLink !== "live") issues.push("junction stream not connected");
    if (latched) issues.push(`${latched} fail-safe latched`);
    if (srcDown) issues.push(`${srcDown} camera source${srcDown > 1 ? "s" : ""} down`);
    if (sumoStatus?.state === "error") issues.push("simulation error");
    return {
      sigs,
      running,
      tlsCount,
      queueM: laneM.length ? mean(laneM) : null,
      queueV: zoneQ.length ? mean(zoneQ) : null,
      simWait: n ? w / n : null,
      simTrips: n,
      throughput: frame && frame.t >= 60 ? (frame.metrics.arrived / frame.t) * 3600 : null,
      latched,
      issues,
    };
  }, [snapshot, frame, geometry, sumoStatus, health.ok, eqLink]);

  const m = snapshot?.metrics;
  const activeAmb = snapshot?.ambulances.filter((a) => a.status === "active").length ?? 0;
  const healthWord = health.ok === false ? "Offline" : k.issues.length ? "Degraded" : health.ok ? "Healthy" : "Checking";
  const healthTone = health.ok === false || k.latched ? "crit" : k.issues.length ? "warn" : health.ok ? "ok" : "neutral";
  const remaining = signal ? smoothRemaining(signal.stage_remaining_s, receivedAt) : null;

  return (
    <div className="page">
      <PageHeader
        title="Operations overview"
        description="Live state of the camera-monitored junction and the SUMO simulation network. Every value comes from the backend; a dash means the data is not available."
      />

      <section className="grid g-kpi" aria-label="Key indicators">
        <Kpi
          label="Vehicles detected"
          icon={Car}
          tone="info"
          value={num(m?.total_vehicles)}
          unit="in view"
          na={m ? null : "No data"}
          meta={<>Camera junction, now{frame ? ` · ${frame.metrics.in_network} in simulation` : ""}</>}
        />
        <Kpi
          label="Active intersections"
          icon={Waypoints}
          value={k.sigs.length + k.tlsCount}
          na={!snapshot && !k.tlsCount ? "No data" : null}
          meta={`${k.sigs.length} camera junction · ${k.tlsCount} simulated`}
        />
        <Kpi
          label="Average waiting time"
          icon={Clock}
          value={num(k.simWait, 1)}
          unit="s"
          na={k.simWait === null ? (k.running ? "No trips completed yet" : simState(sumoStatus?.state)) : null}
          meta={k.simWait !== null ? `Simulation, ${k.simTrips} completed trips` : "Simulation, per completed trip"}
        />
        <Kpi
          label="Average queue length"
          icon={ListOrdered}
          value={k.queueM !== null ? num(k.queueM, 1) : num(k.queueV, 1)}
          unit={k.queueM !== null ? "m" : "veh"}
          na={k.queueM === null && k.queueV === null ? "Not configured" : null}
          meta={k.queueM !== null ? "Calibrated lanes, ground distance" : k.queueV !== null ? "Queued vehicles per zone (uncalibrated)" : "No queue zones or lanes in config"}
        />
        <Kpi
          label="Traffic throughput"
          icon={Gauge}
          value={num(k.throughput, 0)}
          unit="veh/h"
          na={k.throughput === null ? (frame ? "Collecting (1 min of sim time)" : simState(sumoStatus?.state)) : null}
          meta={frame ? `Simulation: ${frame.metrics.arrived} trips completed` : "Trips completed per simulated hour"}
        />
        <Kpi
          label="Emergency vehicles detected"
          icon={Siren}
          tone={activeAmb ? "emg" : "neutral"}
          value={num(m?.ambulance_detections)}
          na={m ? null : "No data"}
          meta={
            <>
              {activeAmb ? <Badge tone="emg">{activeAmb} active</Badge> : "None active"} · {m?.preemptions ?? 0} priority runs
            </>
          }
        />
        <Kpi
          label="Signal controllers"
          icon={TrafficCone}
          tone={k.latched ? "crit" : snapshot ? "ok" : "neutral"}
          value={`${k.sigs.length - k.latched}/${k.sigs.length}`}
          unit="normal"
          na={snapshot ? null : "No data"}
          meta={k.latched ? <Badge tone="crit">{k.latched} in fail-safe</Badge> : `Camera junction${k.tlsCount ? ` · ${k.tlsCount} SUMO controllers` : ""}`}
        />
        <Kpi
          label="System health"
          icon={HeartPulse}
          tone={healthTone}
          value={healthWord}
          meta={k.issues.length ? k.issues.join(" · ") : health.data ? `${health.data.mode === "live" ? "Live" : "Simulated"} vision · backend OK` : "Checking backend"}
        />
      </section>

      <div className="grid g-main-side">
        <Card
          title={signal ? `Camera junction · ${signal.name}` : "Camera junction"}
          icon={TrafficCone}
          sub={signal ? `${MODE_LABEL[signal.mode] ?? signal.mode}. Lamps, counts and queues from the live snapshot.` : undefined}
          actions={
            <>
              <SignalPicker signals={signals} value={signal?.id} onChange={pick} />
              <MoreLink href="/signals">Signal control</MoreLink>
            </>
          }
        >
          {!signal ? (
            <JunctionUnavailable />
          ) : (
            <div className="grid g-2" style={{ alignItems: "start" }}>
              <Plan signal={signal} remaining={remaining} />
              <SignalHeads signal={signal} remaining={remaining} />
            </div>
          )}
        </Card>
        <Card title="Real-time activity" icon={Activity} flush actions={<MoreLink href="/logs">All logs</MoreLink>}>
          <ActivityFeed limit={30} maxHeight={560} />
        </Card>
      </div>

      <Card
        title="Simulation network"
        icon={Network}
        sub={sumoStatus?.run ? `${sumoStatus.run.title} · ${sumoStatus.run.scenario} traffic · ${sumoStatus.state}` : "SUMO live view"}
        actions={<MoreLink href="/simulation">Open simulation</MoreLink>}
      >
        {sumoStatus && !sumoStatus.available ? (
          <Empty compact icon={Network} title="SUMO is not available on this backend">
            {sumoStatus.reason}
          </Empty>
        ) : !geometry ? (
          <Empty compact icon={Network} title="No simulation loaded" action={<Link className="btn sm primary" href="/simulation">Start a simulation</Link>}>
            Vehicle positions and junction states appear here once a SUMO run is started.
          </Empty>
        ) : (
          <div className="grid g-main-side">
            <div>
              <div className="netwrap short">
                <NetworkCanvas geometry={geometry} frame={frame} selected={null} onSelect={() => {}} cameraRange={120} />
              </div>
              <ul className="legend" aria-label="Vehicle colours">
                {VTYPES.map((v) => (
                  <li key={v}>
                    <i style={{ background: VCOLOR[v], outline: v === "ambulance" ? "2px solid #ef4b4b" : undefined }} />
                    {v}
                  </li>
                ))}
              </ul>
            </div>
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Simulated junction status</caption>
                <thead>
                  <tr>
                    <th scope="col">Junction</th>
                    <th scope="col">Mode</th>
                    <th scope="col">Green</th>
                    <th scope="col" className="r">Vehicles</th>
                  </tr>
                </thead>
                <tbody>
                  {(frame?.junctions ?? []).map((j) => {
                    const amb = Object.values(j.ambulance).some(Boolean);
                    return (
                      <tr key={j.id} className={amb ? "is-emg" : undefined}>
                        <th scope="row">{j.id}</th>
                        <td>
                          <Badge tone={j.mode === "PREEMPT" ? "emg" : j.mode === "RECOVERY" ? "warn" : "ok"}>{MODE_LABEL[j.mode] ?? j.mode}</Badge>
                        </td>
                        <td>{j.current && j.stage !== "ALL_RED" ? `${j.current} (${j.stage.toLowerCase()})` : "All-red"}</td>
                        <td className="r">{Object.values(j.vehicles).reduce((a, b) => a + b, 0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {!frame ? (
                <p className="muted" style={{ padding: 12 }}>
                  Waiting for the first simulation frame (simulation {sumoStatus?.state ?? "status unknown"}
                  {geometry.tls.length ? `, ${geometry.tls.length} signalised junctions` : ""}).
                </p>
              ) : (
                !frame.junctions.length && <p className="muted" style={{ padding: 12 }}>This network has no signal-controlled junctions.</p>
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
