"use client";

import { Cctv, MapPin, Network, Siren } from "lucide-react";
import Link from "next/link";
import { MODE_LABEL, controllerName, num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { Badge, Card, Empty, PageHeader } from "../ui";
import { JunctionUnavailable } from "./common";

export default function Intersections() {
  const snapshot = useLive((s) => s.eq.snapshot);
  const frame = useLive((s) => s.sumo.frame);
  const geometry = useLive((s) => s.sumo.geometry);
  const status = useLive((s) => s.sumo.status);
  const sigs = snapshot?.intersections ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Intersections"
        description="Every junction the backend controls: the camera-monitored intersection(s) from the configuration, and the signal-controlled junctions of the running SUMO network."
      />

      <Card title="Camera-monitored intersections" icon={Cctv} flush sub="From backend/config.yaml. Signal output passes the conflict monitor.">
        {!snapshot ? (
          <JunctionUnavailable />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Camera-monitored intersections</caption>
              <thead>
                <tr>
                  <th scope="col">Intersection</th>
                  <th scope="col">Location</th>
                  <th scope="col">Controller</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Current green</th>
                  <th scope="col" className="r">Vehicles</th>
                  <th scope="col" className="r">Longest wait</th>
                  <th scope="col">Cameras</th>
                  <th scope="col">Signal output</th>
                  <th scope="col"><span className="sr-only">Links</span></th>
                </tr>
              </thead>
              <tbody>
                {sigs.map((s) => {
                  const srcs = Object.values(s.sources);
                  const up = srcs.filter((x) => x.ok).length;
                  const veh = Object.values(s.vehicles).reduce((a, b) => a + b, 0);
                  const maxWait = Math.max(0, ...Object.values(s.waiting_s));
                  const flashing = !!s.output?.flashing;
                  return (
                    <tr key={s.id} className={flashing ? "is-crit" : s.mode === "PREEMPT" ? "is-emg" : undefined}>
                      <th scope="row">
                        {s.name}
                        <div className="subtle mono" style={{ fontSize: 11.5 }}>{s.id}</div>
                      </th>
                      <td className="num">
                        {s.lat !== null && s.lng !== null ? (
                          <span className="row" style={{ gap: 4 }}>
                            <MapPin size={13} aria-hidden="true" />
                            {s.lat.toFixed(4)}, {s.lng.toFixed(4)}
                          </span>
                        ) : (
                          <span className="subtle">Not set</span>
                        )}
                      </td>
                      <td>{controllerName(s.controller)}</td>
                      <td>
                        <Badge tone={flashing ? "crit" : s.mode === "PREEMPT" ? "emg" : s.mode === "RECOVERY" ? "warn" : "ok"}>
                          {flashing ? "Fail-safe" : MODE_LABEL[s.mode] ?? s.mode}
                        </Badge>
                      </td>
                      <td>{flashing ? "Flashing red" : s.current && s.stage !== "ALL_RED" ? `${s.current} (${s.stage.toLowerCase()})` : "All-red"}</td>
                      <td className="r">{veh}</td>
                      <td className="r">{num(maxWait)} s</td>
                      <td>
                        <Badge tone={up === srcs.length ? "ok" : up ? "warn" : "crit"}>
                          {up}/{srcs.length} up
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={flashing ? "crit" : "ok"}>{flashing ? `Latched: ${s.output?.fault?.kind}` : "Normal"}</Badge>
                      </td>
                      <td>
                        <Link href="/signals" className="btn sm">
                          Signals
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Simulated junctions (SUMO)"
        icon={Network}
        flush
        sub={status?.run ? `${status.run.title} · ${status.run.scenario} traffic · ${controllerName(status.run.controller === "equiflow" ? status.run.base ?? "adaptive" : status.run.controller)}` : undefined}
      >
        {!geometry ? (
          <Empty compact icon={Network} title={status?.available === false ? "SUMO not available" : "No simulation running"}>
            {status?.available === false ? status.reason : <Link href="/simulation">Start a SUMO run</Link>}
          </Empty>
        ) : geometry.tls.length === 0 ? (
          <Empty compact title="This network has no signal-controlled junctions" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Simulated junctions</caption>
              <thead>
                <tr>
                  <th scope="col">Junction</th>
                  <th scope="col" className="r">Approaches</th>
                  <th scope="col">Controller</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Current green</th>
                  <th scope="col" className="r">Vehicles</th>
                  <th scope="col" className="r">Priority runs</th>
                  <th scope="col">Emergency</th>
                </tr>
              </thead>
              <tbody>
                {geometry.tls.map((t) => {
                  const j = frame?.junctions.find((x) => x.id === t.id);
                  const amb = j ? Object.entries(j.ambulance).filter(([, v]) => v).map(([a]) => a) : [];
                  return (
                    <tr key={t.id} className={amb.length ? "is-emg" : undefined}>
                      <th scope="row">{t.id}</th>
                      <td className="r">{t.approaches.length}</td>
                      <td>{j ? controllerName(j.controller) : "–"}</td>
                      <td>{j ? <Badge tone={j.mode === "PREEMPT" ? "emg" : j.mode === "RECOVERY" ? "warn" : "ok"}>{MODE_LABEL[j.mode] ?? j.mode}</Badge> : "–"}</td>
                      <td>{j?.current && j.stage !== "ALL_RED" ? `${j.current} (${j.stage.toLowerCase()})` : j ? "All-red" : "–"}</td>
                      <td className="r">{j ? Object.values(j.vehicles).reduce((a, b) => a + b, 0) : "–"}</td>
                      <td className="r">{j?.stats.preemptions ?? "–"}</td>
                      <td>{amb.length ? <Badge tone="emg" icon={Siren}>{amb.join(", ")}</Badge> : <span className="subtle">None</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
