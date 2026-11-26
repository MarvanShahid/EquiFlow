"use client";

import { Cctv, Network, Video } from "lucide-react";
import Link from "next/link";
import { num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { APPROACHES } from "@/lib/types";
import Camera from "../Camera";
import { Badge, Banner, Card, Empty, Kpi, PageHeader } from "../ui";
import { JunctionUnavailable, SignalPicker, useSelectedSignal } from "./common";

export default function Cameras() {
  const snapshot = useLive((s) => s.eq.snapshot);
  const link = useLive((s) => s.eq.link);
  const geometry = useLive((s) => s.sumo.geometry);
  const [signal, signals, pick] = useSelectedSignal();
  const srcs = signal ? APPROACHES.map((a) => ({ a, ...signal.sources[a] })) : [];
  const up = srcs.filter((s) => s.ok);
  const fps = up.map((s) => s.fps).filter((f) => f > 0);
  const virtual = geometry?.tls.reduce((n, t) => n + t.approaches.length, 0) ?? 0;

  return (
    <div className="page">
      <PageHeader
        title="Camera monitoring"
        description="Health of every camera source feeding the vision pipeline, and the annotated feeds themselves. A feed is only shown when the backend reports the source as running."
        actions={<SignalPicker signals={signals} value={signal?.id} onChange={pick} />}
      />
      {!signal || !snapshot ? (
        <Card>
          <JunctionUnavailable />
        </Card>
      ) : (
        <>
          {snapshot.mode === "sim" && (
            <Banner tone="info" title="Simulation mode: no physical cameras">
              The sources below are the backend&apos;s synthetic traffic generator ({snapshot.metrics.mode_reason}). Use <code>config.live.yaml</code> with
              recorded videos or RTSP / webcam sources for the real pipeline.
            </Banner>
          )}
          <section className="grid g-kpi" aria-label="Camera health">
            <Kpi label="Sources running" icon={Cctv} tone={up.length === srcs.length ? "ok" : up.length ? "warn" : "crit"} value={`${up.length}/${srcs.length}`} meta={signal.name} />
            <Kpi
              label="Average processing rate"
              icon={Video}
              value={fps.length ? num(fps.reduce((a, b) => a + b, 0) / fps.length, 1) : "–"}
              unit="fps"
              na={fps.length ? null : "No running source"}
              meta={fps.length ? `≈${Math.round(1000 / (fps.reduce((a, b) => a + b, 0) / fps.length))} ms per frame (from the reported fps)` : undefined}
            />
            <Kpi label="Source type" icon={Cctv} value={snapshot.mode === "live" ? "Camera pipeline" : "Simulated"} meta={snapshot.mode === "live" ? "Video file, RTSP stream or webcam (set in config)" : "Synthetic detections"} />
            <Kpi label="SUMO virtual cameras" icon={Network} value={virtual} na={geometry ? null : "No simulation"} meta={geometry ? "One per approach of each simulated junction" : undefined} />
          </section>

          <Card title="Source status" icon={Cctv} flush>
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Camera source status</caption>
                <thead>
                  <tr>
                    <th scope="col">Approach</th>
                    <th scope="col">Type</th>
                    <th scope="col">Status</th>
                    <th scope="col" className="r">Processing rate</th>
                    <th scope="col">Last error</th>
                  </tr>
                </thead>
                <tbody>
                  {srcs.map((s) => (
                    <tr key={s.a} className={!s.ok ? "is-crit" : undefined}>
                      <th scope="row">{s.a}</th>
                      <td>{s.kind === "sim" ? "Simulated" : s.kind === "live" ? "Camera pipeline" : s.kind ?? "–"}</td>
                      <td>{s.ok ? <Badge tone="ok">Running</Badge> : <Badge tone="crit">Not running</Badge>}</td>
                      <td className="r num">{s.ok ? `${num(s.fps, 1)} fps` : "–"}</td>
                      <td className={s.error ? "error" : "subtle"}>{s.error ?? "None"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Annotated feeds" icon={Video} sub="Detector boxes, track IDs and the emergency classifier's votes are drawn by the backend.">
            <div className="camgrid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 420px), 1fr))" }}>
              {APPROACHES.map((a) => (
                <Camera key={a} signal={signal} approach={a} linkUp={link === "live"} />
              ))}
            </div>
          </Card>
        </>
      )}
      {!geometry && (
        <Card title="Virtual cameras (SUMO)" icon={Network}>
          <Empty compact title="No simulation running">
            Each simulated approach has a virtual camera. <Link href="/simulation">Start a run</Link> to view them.
          </Empty>
        </Card>
      )}
    </div>
  );
}
