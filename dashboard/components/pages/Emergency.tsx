"use client";

import { Activity, Clock, Network, Siren, Timer } from "lucide-react";
import { useMemo } from "react";
import type { FeedItem } from "@/lib/events";
import { num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { AmbulanceTable } from "../junction";
import { Badge, Banner, Card, Empty, Kpi, PageHeader } from "../ui";
import { ActivityFeed, JunctionUnavailable } from "./common";

export default function Emergency() {
  const snapshot = useLive((s) => s.eq.snapshot);
  const frame = useLive((s) => s.sumo.frame);
  const geometry = useLive((s) => s.sumo.geometry);
  const m = snapshot?.metrics;
  const active = snapshot?.ambulances.filter((a) => a.status === "active") ?? [];
  const priority = snapshot?.intersections.filter((s) => s.mode === "PREEMPT" && s.active_preempt) ?? [];
  const simPriority = frame?.junctions.filter((j) => j.mode === "PREEMPT") ?? [];
  const filter = useMemo(() => (f: FeedItem) => f.d.category === "emergency" || (f.d.category === "operator" && f.type.includes("preempt")), []);

  return (
    <div className="page">
      <PageHeader
        title="Emergency vehicle monitoring"
        description="Ambulances confirmed by the vision pipeline (5-of-8 frame vote) and how the signal controller responded. Manual operator tests and simulation events are labelled as such and are never counted as camera detections."
      />

      {active.map((a) => (
        <Banner key={a.id} tone="emg" icon={Siren} title={`Emergency vehicle on ${a.intersection_id} ${a.approach}`}>
          Track {a.track_id}, {Math.round(a.confidence * 100)}% confidence, first seen {new Date(a.first_seen * 1000).toLocaleTimeString([], { hour12: false })}.{" "}
          {snapshot?.mode === "live" ? "Camera detection." : "Simulated vision source."}
        </Banner>
      ))}

      <section className="grid g-kpi" aria-label="Emergency indicators">
        <Kpi label="Active now" icon={Siren} tone={active.length ? "emg" : "neutral"} value={active.length} meta="Camera junction" na={snapshot ? null : "No data"} />
        <Kpi label="Detections since start" icon={Activity} value={num(m?.ambulance_detections)} na={m ? null : "No data"} meta={m ? `Backend up ${Math.round(m.uptime_s / 60)} min` : undefined} />
        <Kpi label="Priority runs" icon={Timer} value={num(m?.preemptions)} na={m ? null : "No data"} meta={m ? `${m.active_preemptions} in progress` : undefined} />
        <Kpi
          label="Detection to green, average"
          icon={Clock}
          tone="info"
          value={num(m?.preempt_latency_avg_s, 1)}
          unit="s"
          na={m?.preempt_latency_avg_s == null ? "No priority run yet" : null}
          meta={m?.preempt_latency_max_s != null ? `last ${num(m.preempt_latency_last_s, 1)} s · max ${num(m.preempt_latency_max_s, 1)} s` : undefined}
        />
        <Kpi
          label="Simulation: ambulances in network"
          icon={Network}
          value={num(frame?.metrics.ambulances_in_network)}
          na={frame ? null : "Not running"}
          meta={frame ? `${frame.metrics.preemptions} priority runs · avg ${num(frame.metrics.latency_avg_s, 1)} s to green` : undefined}
        />
      </section>

      <div className="grid g-main-side">
        <div className="stack">
          <Card title="Detections at the camera junction" icon={Siren} flush sub="Active and recently cleared tracks reported by the backend">
            {!snapshot ? <JunctionUnavailable /> : <AmbulanceTable ambulances={snapshot.ambulances} mode={snapshot.mode} />}
          </Card>
          <Card title="Controller response" icon={Timer} flush sub="Intersections currently giving emergency priority">
            {priority.length === 0 && simPriority.length === 0 ? (
              <Empty compact title="No priority in progress">The controller is in its normal cycle everywhere.</Empty>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Intersection</th>
                      <th scope="col">Source</th>
                      <th scope="col">Priority approach</th>
                      <th scope="col">State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {priority.map((s) => (
                      <tr key={s.id} className="is-emg">
                        <th scope="row">{s.name}</th>
                        <td><Badge icon={false}>Camera junction</Badge></td>
                        <td>{s.active_preempt}</td>
                        <td>{s.current === s.active_preempt && s.stage === "GREEN" ? "Green, held until clear" : "Clearing (yellow / all-red)"}</td>
                      </tr>
                    ))}
                    {simPriority.map((j) => (
                      <tr key={j.id} className="is-emg">
                        <th scope="row">{j.id}</th>
                        <td><Badge icon={false}>Simulation</Badge></td>
                        <td>{j.active_preempt}</td>
                        <td>{j.current === j.active_preempt && j.stage === "GREEN" ? "Green, held until clear" : "Clearing (yellow / all-red)"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
        <Card title="Emergency timeline" icon={Activity} flush sub="Detections, priority start / green / end, corridor requests and operator tests">
          <ActivityFeed filter={filter} limit={60} maxHeight={620} />
        </Card>
      </div>
      {!geometry && <p className="chart-note">Simulation emergency events appear when a SUMO run is active.</p>}
    </div>
  );
}
