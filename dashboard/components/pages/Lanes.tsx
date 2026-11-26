"use client";

import { Info, Network, Ruler, Rows3, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { APPROACHES } from "@/lib/types";
import { useTicker } from "@/lib/useEquiflow";
import { HBars, LineChart, SERIES_COLORS, sinceLabel } from "../charts";
import { Badge, Banner, Card, Empty, PageHeader } from "../ui";
import { JunctionUnavailable, SignalPicker, useSelectedSignal } from "./common";

export default function Lanes() {
  useTicker(2000); // the trend axes are relative to "now"
  const history = useLive((s) => s.history);
  const [signal, signals, pick] = useSelectedSignal();
  const frame = useLive((s) => s.sumo.frame);
  const [tls, setTls] = useState<string | null>(null);
  const now = Date.now();

  const lanes = useMemo(
    () =>
      signal
        ? APPROACHES.flatMap((a) => Object.entries(signal.lanes?.[a] ?? {}).map(([id, q]) => ({ a, id, key: `${signal.id}/${a}/${id}`, ...q })))
        : [],
    [signal],
  );
  const lanesConfigured = APPROACHES.filter((a) => signal?.lanes?.[a]);
  const zones = APPROACHES.filter((a) => signal?.queues?.[a] !== null && signal?.queues?.[a] !== undefined);
  const calibrated = lanes.filter((l) => l.queue_m !== null);

  // trends from the samples received since this tab opened
  const hist = history.eq.filter((s) => signal && s.vehicles[signal.id]);
  const vehSeries = signal
    ? APPROACHES.map((a, i) => ({ label: a, color: SERIES_COLORS[i], points: hist.map((s) => [s.wall, s.vehicles[signal.id]?.[a] ?? null] as [number, number | null]) }))
    : [];
  const laneSeries = calibrated.length
    ? lanes.map((l, i) => ({ label: `${l.a} ${l.id}`, color: SERIES_COLORS[i % SERIES_COLORS.length], points: hist.map((s) => [s.wall, s.lanes[l.key]?.queue_m ?? null] as [number, number | null]) }))
    : signal && zones.length
      ? zones.map((a, i) => ({ label: a, color: SERIES_COLORS[i], points: hist.map((s) => [s.wall, s.queues[signal.id]?.[a] ?? null] as [number, number | null]) }))
      : [];

  const j = frame?.junctions.find((x) => x.id === tls) ?? frame?.junctions[0];
  const sumoHist = history.sumo.filter((s) => j && s.approach_vehicles[j.id]);
  const sumoSeries = j
    ? Object.keys(j.vehicles).map((a, i) => ({ label: a, color: SERIES_COLORS[i % SERIES_COLORS.length], points: sumoHist.map((s) => [s.t, s.approach_vehicles[j.id]?.[a] ?? null] as [number, number | null]) }))
    : [];

  return (
    <div className="page">
      <PageHeader
        title="Lane analytics"
        description="Per-approach and per-lane counts and queues from the vision pipeline. Queue length in metres is shown only for lanes with a ground-plane calibration; otherwise only counts are reported."
        actions={<SignalPicker signals={signals} value={signal?.id} onChange={pick} />}
      />

      {!signal ? (
        <Card>
          <JunctionUnavailable />
        </Card>
      ) : (
        <>
          <section className="grid g-3" aria-label="Measurement configuration">
            <CalibCard
              title="Lane polygons"
              ok={lanesConfigured.length > 0}
              okText={`${lanes.length} lanes on ${lanesConfigured.join(", ")}`}
              noText="Not configured: no per-lane counts"
            />
            <CalibCard
              title="Ground-plane calibration"
              ok={calibrated.length > 0}
              okText={`${calibrated.length} of ${lanes.length} lanes report metres`}
              noText={lanes.length ? "Lanes are uncalibrated: counts only, no metres" : "No lanes to calibrate"}
            />
            <CalibCard title="Queue zones" ok={zones.length > 0} okText={`Configured on ${zones.join(", ")}`} noText="Not configured: no approach queue counts" />
          </section>

          {!lanes.length && (
            <Banner tone="info" title="Lane-level measurement is not configured for this intersection" icon={Info}>
              Add <code>lanes</code> (and optionally <code>calibration</code>) for each approach in the backend config. Projects/calibrate_lanes.py
              creates them by clicking on a video frame. Until then only approach totals are available.
            </Banner>
          )}

          <div className="grid g-2">
            <Card title="Approach comparison" icon={Rows3} sub="Vehicles tracked now, and queued vehicles where a queue zone exists">
              <h4 className="section-title">Vehicles tracked</h4>
              <HBars ariaLabel="Vehicles tracked per approach" rows={APPROACHES.map((a, i) => ({ label: a, value: signal.vehicles[a], color: SERIES_COLORS[i] }))} />
              <h4 className="section-title">Queued in zone</h4>
              <HBars
                ariaLabel="Queued vehicles per approach"
                rows={APPROACHES.map((a) => {
                  const q = signal.queues?.[a];
                  return { label: a, value: q ?? null, display: q === null || q === undefined ? "no zone" : String(q), color: "#f59e0b" };
                })}
              />
              <h4 className="section-title">Waiting since last green</h4>
              <HBars ariaLabel="Waiting time per approach" rows={APPROACHES.map((a) => ({ label: a, value: signal.waiting_s[a], display: `${Math.round(signal.waiting_s[a])} s`, color: "#94a3b8" }))} />
            </Card>
            <Card title="Vehicles per approach over time" icon={TrendingUp} sub="Samples every 2 s since this tab opened (not stored history)">
              {hist.length < 2 ? (
                <Empty compact title="Collecting samples…">The trend appears after a few snapshots.</Empty>
              ) : (
                <LineChart series={vehSeries} xFormat={sinceLabel(now)} yLabel="vehicles" ariaLabel="Vehicles tracked per approach over time" />
              )}
            </Card>
          </div>

          <Card title="Per-lane measurements" icon={Ruler} flush sub="Queue length is the ground distance from the stop line to the last queued vehicle, plus half a vehicle.">
            {!lanes.length ? (
              <Empty compact title="No lanes configured" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <caption className="sr-only">Per-lane vehicle counts and queues</caption>
                  <thead>
                    <tr>
                      <th scope="col">Approach</th>
                      <th scope="col">Lane</th>
                      <th scope="col" className="r">Vehicles</th>
                      <th scope="col" className="r">Queued</th>
                      <th scope="col" className="r">Queue length</th>
                      <th scope="col" className="r" title="Queued vehicles as a share of vehicles in the lane">Queued share</th>
                      <th scope="col">Calibration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lanes.map((l) => (
                      <tr key={l.key}>
                        <td>{l.a}</td>
                        <th scope="row">{l.id}</th>
                        <td className="r">{l.vehicles}</td>
                        <td className="r">{l.queued}</td>
                        <td className="r">{l.queue_m !== null ? `${num(l.queue_m, 1)} m` : <span className="subtle">no metres (uncalibrated)</span>}</td>
                        <td className="r">{l.vehicles ? `${Math.round((100 * l.queued) / l.vehicles)}%` : "–"}</td>
                        <td>{l.queue_m !== null ? <Badge tone="ok">Calibrated</Badge> : <Badge tone="warn">Uncalibrated</Badge>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="chart-note" style={{ padding: "0 16px 14px" }}>
              Stop-line positions and calibration points live in the backend configuration and are not exposed by the API. Lane
              occupancy and per-lane waiting time are not measured by the pipeline.
            </p>
          </Card>

          {laneSeries.length > 0 && (
            <Card title={calibrated.length ? "Queue length trend (calibrated, metres)" : "Queued vehicles trend (zones, count)"} icon={TrendingUp} sub="Since this tab opened">
              {hist.length < 2 ? (
                <Empty compact title="Collecting samples…" />
              ) : (
                <LineChart series={laneSeries} xFormat={sinceLabel(now)} yLabel={calibrated.length ? "metres" : "vehicles"} ariaLabel="Queue trend" />
              )}
            </Card>
          )}
        </>
      )}

      <Card
        title="Simulated approaches (SUMO)"
        icon={Network}
        sub="SUMO reports vehicles per approach from its virtual cameras; it does not report per-lane queues."
        actions={
          frame && frame.junctions.length > 1 ? (
            <div className="chips" role="group" aria-label="Junction">
              {frame.junctions.map((x) => (
                <button key={x.id} type="button" aria-pressed={x.id === j?.id} onClick={() => setTls(x.id)}>
                  {x.id}
                </button>
              ))}
            </div>
          ) : undefined
        }
      >
        {!j ? (
          <Empty compact icon={Network} title="No simulation running">
            <Link href="/simulation">Start a SUMO run</Link> to compare simulated approaches.
          </Empty>
        ) : (
          <div className="grid g-2">
            <div>
              <h4 className="section-title">Vehicles in camera range, now</h4>
              <HBars ariaLabel={`Vehicles per approach at ${j.id}`} rows={Object.keys(j.vehicles).map((a, i) => ({ label: a, value: j.vehicles[a], color: SERIES_COLORS[i % SERIES_COLORS.length] }))} />
              <h4 className="section-title">Waiting since last green</h4>
              <HBars ariaLabel={`Waiting per approach at ${j.id}`} rows={Object.keys(j.waiting_s).map((a) => ({ label: a, value: j.waiting_s[a], display: `${Math.round(j.waiting_s[a])} s`, color: "#94a3b8" }))} />
            </div>
            <div>
              {sumoHist.length < 2 ? (
                <Empty compact title="Collecting samples…" />
              ) : (
                <LineChart series={sumoSeries} xFormat={(t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`} xLabel="Simulation time (m:ss), sampled every second of real time" yLabel="vehicles" ariaLabel={`Vehicles per approach at ${j.id} over simulation time`} />
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function CalibCard({ title, ok, okText, noText }: { title: string; ok: boolean; okText: string; noText: string }) {
  return (
    <div className="kpi">
      <div className="kpi-top">
        <span className="kpi-label">{title}</span>
        <Badge tone={ok ? "ok" : "warn"}>{ok ? "Configured" : "Not configured"}</Badge>
      </div>
      <div style={{ fontSize: 13 }}>{ok ? okText : noText}</div>
    </div>
  );
}
