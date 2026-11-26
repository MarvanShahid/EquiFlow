"use client";

import { Cctv, Network, Siren, TrafficCone } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { MODE_LABEL, num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { VCOLOR, VTYPES } from "@/lib/sumo";
import { APPROACHES } from "@/lib/types";
import { smoothRemaining, useTicker } from "@/lib/useEquiflow";
import Camera from "../Camera";
import { AmbulanceTable } from "../junction";
import Plan from "../Plan";
import NetworkCanvas from "../sumo/NetworkCanvas";
import { Badge, Banner, Card, Empty, LampPill, PageHeader, Tabs } from "../ui";
import { JunctionUnavailable, MoreLink, SignalPicker, useSelectedSignal } from "./common";

type View = "junction" | "simulation";

export default function LiveTraffic() {
  const [view, setView] = useState<View>("junction");
  return (
    <div className="page">
      <PageHeader
        title="Live traffic monitoring"
        description="Vehicle detection, tracking and queues as they happen. The camera junction runs the vision pipeline (YOLO detector + ByteTrack + emergency classifier); the simulation view shows the SUMO network."
      />
      <Tabs
        label="Data source"
        value={view}
        onChange={setView}
        tabs={[
          { id: "junction", label: "Camera junction", icon: Cctv },
          { id: "simulation", label: "Simulation network", icon: Network },
        ]}
      />
      {view === "junction" ? <JunctionView /> : <SimulationView />}
    </div>
  );
}

function JunctionView() {
  useTicker(250);
  const snapshot = useLive((s) => s.eq.snapshot);
  const link = useLive((s) => s.eq.link);
  const receivedAt = useLive((s) => s.eq.receivedAt);
  const [signal, signals, pick] = useSelectedSignal();
  if (!signal || !snapshot)
    return (
      <Card>
        <JunctionUnavailable />
      </Card>
    );
  const remaining = smoothRemaining(signal.stage_remaining_s, receivedAt);
  const kinds = new Set(Object.values(signal.sources).map((s) => s.kind));
  const allSim = kinds.size === 1 && kinds.has("sim");
  const ambs = snapshot.ambulances.filter((a) => a.intersection_id === signal.id);

  return (
    <>
      <div className="row-between">
        <SignalPicker signals={signals} value={signal.id} onChange={pick} />
        <div className="row">
          <Badge tone={allSim ? "neutral" : "info"} lg icon={Cctv}>
            {allSim ? "Simulation mode: synthetic camera sources" : snapshot.mode === "live" ? "Camera pipeline: video files or live streams" : "Mixed sources"}
          </Badge>
          <Badge lg tone={signal.mode === "PREEMPT" ? "emg" : signal.mode === "RECOVERY" ? "warn" : "ok"}>
            {MODE_LABEL[signal.mode] ?? signal.mode}
          </Badge>
        </div>
      </div>
      {snapshot.mode === "sim" && (
        <Banner tone="info" title="Simulated vision">
          The backend is not running the vision models ({snapshot.metrics.mode_reason}). Counts and detections come from its built-in
          traffic generator, not a camera. Configure <code>config.live.yaml</code> for recorded videos or live cameras.
        </Banner>
      )}

      <div className="grid g-side-main">
        <Card title="Junction plan" icon={TrafficCone} sub="Lamps, counts and queues from the live snapshot">
          <Plan signal={signal} remaining={remaining} />
        </Card>
        <Card title="Approach cameras" icon={Cctv} sub="Annotated feed from the backend; boxes are drawn by the detector and tracker." actions={<MoreLink href="/cameras">Camera health</MoreLink>}>
          <div className="camgrid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
            {APPROACHES.map((a) => (
              <Camera key={a} signal={signal} approach={a} linkUp={link === "live"} />
            ))}
          </div>
        </Card>
      </div>

      <Card title="Per-approach detection" icon={TrafficCone} flush sub="Vehicles currently tracked in each camera's view, the queue inside its configured zone, and processing rate.">
        <div className="table-wrap">
          <table className="table">
            <caption className="sr-only">Detection and queue per approach</caption>
            <thead>
              <tr>
                <th scope="col">Approach</th>
                <th scope="col">Signal</th>
                <th scope="col" className="r">Vehicles tracked</th>
                <th scope="col" className="r">Queued</th>
                <th scope="col" className="r">Waiting</th>
                <th scope="col">Emergency</th>
                <th scope="col">Source</th>
                <th scope="col" className="r">Processing</th>
              </tr>
            </thead>
            <tbody>
              {APPROACHES.map((a) => {
                const src = signal.sources[a];
                const q = signal.queues?.[a];
                return (
                  <tr key={a} className={signal.ambulance[a] ? "is-emg" : !src?.ok ? "is-crit" : undefined}>
                    <th scope="row">{a}</th>
                    <td>
                      <LampPill lamp={signal.output?.flashing ? "red" : signal.lamps[a]} />
                    </td>
                    <td className="r">{signal.vehicles[a]}</td>
                    <td className="r">{q === null || q === undefined ? <span className="subtle">no zone</span> : q}</td>
                    <td className="r">{Math.round(signal.waiting_s[a])} s</td>
                    <td>{signal.ambulance[a] ? <Badge tone="emg" icon={Siren}>Detected</Badge> : <span className="subtle">None</span>}</td>
                    <td>
                      {src?.ok ? <Badge tone="ok">{src.kind === "sim" ? "Simulated" : "Running"}</Badge> : <Badge tone="crit">{src?.error ?? "Down"}</Badge>}
                    </td>
                    <td className="r num" title="Frames processed per second (detector + tracker + classifier)">
                      {src?.ok ? `${num(src.fps, 1)} fps` : "–"}
                      {src?.ok && src.fps > 0 && <span className="subtle"> · ≈{Math.round(1000 / src.fps)} ms/frame</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Emergency vehicle tracks" icon={Siren} flush sub="Tracks the classifier confirmed (K-of-M frame vote) at this junction" actions={<MoreLink href="/emergency">Emergency monitoring</MoreLink>}>
        <AmbulanceTable ambulances={ambs} mode={snapshot.mode} />
      </Card>
    </>
  );
}

function SimulationView() {
  const geometry = useLive((s) => s.sumo.geometry);
  const frame = useLive((s) => s.sumo.frame);
  const status = useLive((s) => s.sumo.status);
  const [picked, setPicked] = useState<string | null>(null);
  if (!geometry)
    return (
      <Card>
        <Empty icon={Network} title={status?.available === false ? "SUMO not available" : "No simulation running"} action={<Link className="btn sm primary" href="/simulation">Open simulation</Link>}>
          {status?.available === false ? status.reason : "Start a SUMO run to see simulated traffic here."}
        </Empty>
      </Card>
    );
  const j = frame?.junctions.find((x) => x.id === picked) ?? frame?.junctions[0];
  return (
    <>
      <Banner tone="info" title="Simulation mode">
        Vehicles, positions and signal states below come from SUMO ({status?.run?.title ?? "current run"}), not from a camera.
      </Banner>
      <div className="grid g-main-side">
        <Card title="Network" icon={Network} sub="Click a junction to see its approaches">
          <NetworkCanvas geometry={geometry} frame={frame} selected={j?.id ?? null} onSelect={setPicked} cameraRange={120} />
          <ul className="legend">
            {VTYPES.map((v) => (
              <li key={v}>
                <i style={{ background: VCOLOR[v], outline: v === "ambulance" ? "2px solid #ef4b4b" : undefined }} />
                {v}
              </li>
            ))}
          </ul>
        </Card>
        <Card title={j ? `Junction ${j.id}` : "Junction"} actions={<MoreLink href="/simulation">Full detail</MoreLink>} flush>
          {!j ? (
            <Empty compact title="Waiting for the first frame" />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Approach</th>
                    <th scope="col">Signal</th>
                    <th scope="col" className="r">Tracked</th>
                    <th scope="col" className="r">Waiting</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(j.lamps).map((a) => (
                    <tr key={a} className={j.ambulance[a] ? "is-emg" : undefined}>
                      <th scope="row">
                        {a} {j.ambulance[a] && <Badge tone="emg" icon={Siren}>EV</Badge>}
                      </th>
                      <td>
                        <LampPill lamp={j.lamps[a]} />
                      </td>
                      <td className="r">{j.vehicles[a] ?? 0}</td>
                      <td className="r">{Math.round(j.waiting_s[a] ?? 0)} s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
