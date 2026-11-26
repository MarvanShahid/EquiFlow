"use client";

import { Activity, Cctv, Gauge, Network, Pause, Play, RotateCcw, Siren, Square, Timer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { num, simClock } from "@/lib/format";
import { useLive } from "@/lib/live";
import { VCOLOR, VTYPES, sumoApi, useSumo, type Base, type Controller, type NetworkInfo, type Scenario, type Veh } from "@/lib/sumo";
import { useSession } from "../session";
import CameraView from "../sumo/CameraView";
import JunctionPanel from "../sumo/JunctionPanel";
import NetworkCanvas from "../sumo/NetworkCanvas";
import { Badge, Banner, Card, Empty, Kpi, PageHeader, ReadOnlyNote, Segmented, useCommand, useConfirm } from "../ui";
import { ActivityFeed } from "./common";

export const CONTROLLERS: { id: string; controller: Controller; base?: Base; label: string; hint: string }[] = [
  { id: "equiflow", controller: "equiflow", base: "adaptive", label: "EquiFlow", hint: "Adaptive greens with gap-out and green extension, plus safe emergency priority" },
  { id: "marl", controller: "equiflow", base: "marl", label: "EquiFlow MARL", hint: "Same priority and safety layer, with the trained multi-agent RL controller choosing the greens" },
  { id: "fixed", controller: "fixed", label: "Fixed-time", hint: "Baseline: SUMO's static signal plan" },
  { id: "actuated", controller: "actuated", label: "Actuated", hint: "Baseline: SUMO's detector-actuated plan" },
];
const choiceOf = (c: Controller, b?: string) => (c === "equiflow" ? (b === "marl" ? "marl" : "equiflow") : c);
const SCEN_LABEL: Record<Scenario, string> = { low: "Light", medium: "Medium", high: "Heavy", asymmetric: "Asymmetric" };
const SPEEDS = [1, 2, 5, 10, 20];
export const CAMERA_RANGE = 120;
export const VOTE_M = 8;

const STATE_TONE = { running: "ok", paused: "warn", starting: "info", finished: "neutral", idle: "neutral", error: "crit" } as const;

export default function Simulation() {
  const { geometry, frame, status, link } = useSumo();
  const { canOperate } = useSession();
  const { confirm, dialog } = useConfirm();
  const { run: exec, busy } = useCommand();
  const [nets, setNets] = useState<NetworkInfo[]>([]);
  const [netsError, setNetsError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [form, setForm] = useState<{ network: string; scenario: Scenario; choice: string }>({ network: "sector_grid", scenario: "medium", choice: "equiflow" });
  const [formTouched, setFormTouched] = useState(false);
  const sumoEvents = useLive((s) => s.sumo.events.length);

  useEffect(() => {
    sumoApi
      .networks()
      .then((r) => {
        setNets(r.networks);
        setNetsError(null);
        if (r.status.run && !formTouched)
          setForm({ network: r.status.run.network, scenario: r.status.run.scenario, choice: choiceOf(r.status.run.controller, r.status.run.base) });
      })
      .catch((e) => setNetsError(e.message));
    // re-read when the connection comes back
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [link]);

  const run = status?.run ?? null;
  const tls = geometry?.tls ?? [];
  const selected = tls.find((t) => t.id === picked) ?? tls[0];
  const snap = frame?.junctions.find((j) => j.id === selected?.id);
  const vehicles = useMemo(() => new Map<string, Veh>((frame?.vehicles ?? []).map((v) => [v[0], v])), [frame]);
  const equiflow = run?.controller === "equiflow";
  const running = status?.state === "running" || status?.state === "paused";
  const netInfo = nets.find((n) => n.id === form.network);
  const m = frame?.metrics;
  const amb = m?.per_class.ambulance;
  const car = m?.per_class.car;
  const update = (p: Partial<typeof form>) => {
    setFormTouched(true);
    setForm((f) => ({ ...f, ...p }));
  };

  const start = async () => {
    const c = CONTROLLERS.find((x) => x.id === form.choice) ?? CONTROLLERS[0];
    if (running) {
      const ok = await confirm({
        tone: "warn",
        title: "Restart the simulation?",
        body: `The current run (${run?.title ?? "unknown"}, ${run?.scenario}) stops and its live state is discarded. A new run starts on ${netInfo?.title ?? form.network}, ${SCEN_LABEL[form.scenario]} traffic, ${c.label}.`,
        confirmLabel: "Restart",
      });
      if (!ok) return;
    }
    await exec("Start simulation", () => sumoApi.start({ network: form.network, scenario: form.scenario, controller: c.controller, base: c.base, speed: run?.speed }), "SUMO run started.");
  };
  const stop = async () => {
    const ok = await confirm({
      tone: "crit",
      title: "Stop the simulation?",
      body: "SUMO stops and the live network view is cleared. Results files from earlier batch runs are not affected.",
      confirmLabel: "Stop simulation",
    });
    if (ok) await exec("Stop simulation", () => sumoApi.stop(), "Simulation stopped.");
  };

  return (
    <div className="page">
      <PageHeader
        title="SUMO simulation"
        description="Every junction of the SUMO model runs the same controller code as the camera junction. Pick a network, traffic level and controller, then inspect each junction's signals, virtual cameras and decisions."
        actions={
          status && (
            <Badge tone={STATE_TONE[status.state] ?? "neutral"} lg dot pulse={status.state === "starting"}>
              Simulation {status.state}
            </Badge>
          )
        }
      />

      {status && !status.available && (
        <Banner tone="warn" title="SUMO is not available on this backend">
          {status.reason}. Install SUMO (set SUMO_HOME or <code>pip install eclipse-sumo</code>), or run the backend in WSL with{" "}
          <code>backend/run_wsl.sh</code>.
        </Banner>
      )}
      {status?.state === "error" && status.error && <Banner tone="crit" title="The simulation stopped with an error">{status.error}</Banner>}
      {link === "offline" && <Banner tone="crit" title="Simulation stream offline">Reconnecting to the backend…</Banner>}

      <Card title="Run configuration" icon={Network} sub={netInfo?.description}>
        <div className="stack">
          {!canOperate && <ReadOnlyNote />}
          {netsError && <p className="error">Could not load the network list: {netsError}</p>}
          <div className="toolbar">
            <label className="field">
              <span>Network</span>
              <select className="select" value={form.network} onChange={(e) => update({ network: e.target.value })} disabled={!canOperate}>
                {nets.length === 0 && <option value={form.network}>{form.network}</option>}
                {nets.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Traffic demand</span>
              <select className="select" value={form.scenario} onChange={(e) => update({ scenario: e.target.value as Scenario })} disabled={!canOperate}>
                {(netInfo?.scenarios ?? (["low", "medium", "high", "asymmetric"] as Scenario[])).map((s) => (
                  <option key={s} value={s}>
                    {SCEN_LABEL[s]}
                  </option>
                ))}
              </select>
            </label>
            <Segmented
              legend="Signal controller"
              value={form.choice}
              options={CONTROLLERS.map((c) => ({ value: c.id, label: c.label, title: c.hint }))}
              onChange={(v) => update({ choice: v })}
              disabled={!canOperate}
            />
            <div className="spacer" />
            <button type="button" className="btn primary" disabled={busy || !status?.available || !canOperate} onClick={start}>
              {running ? <RotateCcw size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
              {running ? "Restart with these settings" : "Start simulation"}
            </button>
          </div>
          <div className="toolbar" style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            <Segmented
              legend="Speed (simulated seconds per real second)"
              value={run?.speed}
              options={SPEEDS.map((s) => ({ value: s, label: `${s}×` }))}
              onChange={(s) => exec(`Set speed ${s}×`, () => sumoApi.speed(s), `Speed set to ${s}×.`)}
              disabled={!running || !canOperate || busy}
            />
            <div className="spacer" />
            <button
              type="button"
              className="btn"
              disabled={!running || !canOperate || busy}
              onClick={() => exec(status?.state === "paused" ? "Resume" : "Pause", () => sumoApi.pause(status?.state !== "paused"))}
            >
              {status?.state === "paused" ? <Play size={16} aria-hidden="true" /> : <Pause size={16} aria-hidden="true" />}
              {status?.state === "paused" ? "Resume" : "Pause"}
            </button>
            <button
              type="button"
              className="btn emg"
              disabled={!running || !canOperate || busy}
              onClick={async () => {
                const ok = await confirm({
                  tone: "emg",
                  title: "Dispatch an ambulance?",
                  body: "Adds a simulated ambulance on a random route. It is a simulation event, not a real detection.",
                  confirmLabel: "Dispatch",
                });
                if (ok) await exec("Dispatch ambulance", () => sumoApi.ambulance(), "Ambulance added to the simulation.");
              }}
            >
              <Siren size={16} aria-hidden="true" /> Send an ambulance
            </button>
            <button type="button" className="btn" disabled={!running || !canOperate || busy} onClick={stop}>
              <Square size={15} aria-hidden="true" /> Stop
            </button>
          </div>
        </div>
      </Card>

      <section className="grid g-kpi" aria-label="Simulation metrics">
        <Kpi label="Simulation time" icon={Timer} value={frame ? simClock(frame.t) : "–"} na={frame ? null : "Not running"} meta={run ? `${run.speed}× speed · seed ${run.seed}` : undefined} />
        <Kpi label="Vehicles on the road" icon={Activity} tone="info" value={num(m?.in_network)} na={m ? null : "–"} meta={m ? `${m.halting} stopped now` : undefined} />
        <Kpi label="Trips completed" icon={Gauge} value={num(m?.arrived)} na={m ? null : "–"} />
        <Kpi label="Average wait, cars" icon={Timer} value={num(car?.mean_waiting_s, 1)} unit="s" na={car?.mean_waiting_s == null ? "No completed trips" : null} />
        <Kpi label="Average wait, ambulances" icon={Siren} tone="emg" value={num(amb?.mean_waiting_s, 1)} unit="s" na={amb?.mean_waiting_s == null ? "No completed trips" : null} meta={m ? `${m.ambulances_in_network} in network now` : undefined} />
        {equiflow && (
          <Kpi
            label="Detection to green"
            icon={Siren}
            tone="emg"
            value={num(m?.latency_avg_s, 1)}
            unit="s avg"
            na={m?.latency_avg_s == null ? "No priority run yet" : null}
            meta={m ? `${m.preemptions} priority runs` : undefined}
          />
        )}
      </section>

      {!geometry ? (
        <Card>
          <Empty icon={Network} title={status?.available === false ? "Simulation unavailable" : link === "offline" ? "Backend offline" : "No simulation loaded"}>
            {status?.available === false
              ? "Install SUMO on the backend host to use the live simulation."
              : "Choose a network and press Start simulation. The map, junction panel and virtual cameras appear here."}
          </Empty>
        </Card>
      ) : (
        <>
          <div className="grid g-main-side">
            <Card title="Network map" icon={Network} sub="Scroll to zoom, drag to pan, double-click to reset. Click a junction to inspect it.">
              <NetworkCanvas geometry={geometry} frame={frame} selected={selected?.id ?? null} onSelect={setPicked} cameraRange={CAMERA_RANGE} />
              <ul className="legend" aria-label="Legend">
                {VTYPES.map((v) => (
                  <li key={v}>
                    <i style={{ background: VCOLOR[v], outline: v === "ambulance" ? "2px solid #ef4b4b" : undefined }} />
                    {v}
                  </li>
                ))}
                <li><i className="lg-bar" style={{ background: "#22c55e" }} />green</li>
                <li><i className="lg-bar" style={{ background: "#ef4444" }} />red</li>
                <li><i className="lg-zone" />camera range ({CAMERA_RANGE} m)</li>
              </ul>
              {tls.length === 0 && <p className="muted" style={{ marginTop: 8 }}>This network has no traffic signals (give-way junction or roundabout), so there is nothing to control.</p>}
            </Card>
            <Card
              title={selected ? `Junction ${selected.id}` : "Junction"}
              actions={
                tls.length > 1 && (
                  <div className="chips" role="group" aria-label="Junction">
                    {tls.map((t) => {
                      const j = frame?.junctions.find((x) => x.id === t.id);
                      return (
                        <button key={t.id} type="button" aria-pressed={t.id === selected?.id} onClick={() => setPicked(t.id)} className={j?.mode === "PREEMPT" ? "is-emg" : undefined}>
                          {j?.mode === "PREEMPT" && <Siren size={12} aria-label="priority" />}
                          {t.id}
                        </button>
                      );
                    })}
                  </div>
                )
              }
            >
              {selected ? <JunctionPanel geo={selected} snap={snap} equiflow={equiflow} simTime={frame?.t ?? 0} running={running} /> : <Empty compact title="No signalised junction" />}
            </Card>
          </div>

          {selected && (
            <Card
              title={`Virtual cameras at junction ${selected.id}`}
              icon={Cctv}
              sub={`What the detector sees on each approach (last ${CAMERA_RANGE} m). Red box: confirmed ambulance (5 of the last ${VOTE_M} frames voted ambulance). Yellow: some votes. Green: other vehicle.`}
            >
              <div className="camgrid">
                {selected.approaches.map((a) => (
                  <CameraView
                    key={a.id}
                    geometry={geometry}
                    approach={a}
                    vehicles={vehicles}
                    dets={snap?.cameras[a.id] ?? []}
                    lamp={snap?.lamps[a.id] ?? "red"}
                    ambulance={!!snap?.ambulance[a.id]}
                    range={CAMERA_RANGE}
                    m={VOTE_M}
                  />
                ))}
              </div>
            </Card>
          )}

          <Card title="What the simulation did" icon={Activity} sub={`${sumoEvents} events received this session`} flush>
            <ActivityFeed origin="simulation" limit={40} maxHeight={380} />
          </Card>
        </>
      )}
      {dialog}
    </div>
  );
}
