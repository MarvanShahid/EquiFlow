"use client";

import { API_URL } from "@/lib/api";

import { useEffect, useMemo, useState } from "react";
import {
  VCOLOR,
  VTYPES,
  fmtTime,
  sumoApi,
  useSumo,
  type Base,
  type Controller,
  type NetworkInfo,
  type Scenario,
  type SumoEvent,
  type Veh,
} from "@/lib/sumo";
import CameraView from "./CameraView";
import JunctionPanel from "./JunctionPanel";
import NetworkCanvas from "./NetworkCanvas";

const CONTROLLERS: { id: string; controller: Controller; base?: Base; label: string; hint: string }[] = [
  { id: "equiflow", controller: "equiflow", base: "adaptive", label: "EquiFlow", hint: "Our controller: adaptive greens with gap-out and green extension, and safe ambulance priority" },
  { id: "marl", controller: "equiflow", base: "marl", label: "EquiFlow MARL", hint: "Same priority and safety layer, with the trained multi-agent RL controller choosing the greens" },
  { id: "fixed", controller: "fixed", label: "Fixed-time", hint: "Baseline: SUMO's static signal plan" },
  { id: "actuated", controller: "actuated", label: "Actuated", hint: "Baseline: SUMO's detector-actuated plan" },
];
const choiceOf = (c: Controller, b?: string) => (c === "equiflow" ? (b === "marl" ? "marl" : "equiflow") : c);
const SCEN_LABEL: Record<Scenario, string> = { low: "Light", medium: "Medium", high: "Heavy", asymmetric: "Asymmetric" };
const SPEEDS = [1, 2, 5, 10, 20];
const CAMERA_RANGE = 120;
const M = 8;

function describe(e: SumoEvent): { text: string; tone: string } | null {
  const a = e.approach;
  const at = e.tls ? `${e.tls} ${a ?? ""}`.trim() : a ?? "";
  switch (e.type) {
    case "ambulance_dispatched":
      return { text: `Ambulance sent${e.tls ? ` towards ${e.tls} from ${a}` : ""}`, tone: "dim" };
    case "ambulance_detected":
      return { text: `${at}: camera confirmed an ambulance ${e.distance_m} m out (${Math.round(Number(e.confidence) * 100)}%)`, tone: "amb" };
    case "corridor_request":
      return { text: `${at}: green corridor, ambulance ${e.distance_m} m away (about ${e.eta_s} s), clearing ahead of it`, tone: "amb" };
    case "preempt_started":
      return { text: `${at}: priority started`, tone: "amb" };
    case "preempt_green":
      return { text: `${at}: green ${e.latency_s} s after detection`, tone: "ok" };
    case "preempt_ended":
      return { text: `${e.tls}: priority ended after ${e.duration_s} s`, tone: "amb" };
    case "recovery_planned":
      return { text: `${e.tls}: fair recovery, ${(e.plan as string[]).join(", ")} served first`, tone: "warn" };
    case "green_extended":
      return { text: `${at}: green extended, still the busiest (${e.vehicles} vehicles)`, tone: "dim" };
    case "green_ended_early":
      return { text: `${at}: green ended early after ${e.after_s} s, nobody left`, tone: "dim" };
    case "preempt_timeout":
      return { text: `${at}: priority timed out (fail-safe)`, tone: "warn" };
    case "manual_preempt":
      return { text: `${at}: operator test priority`, tone: "dim" };
    case "sumo_started":
      return { text: `Simulation started (${e.network}, ${e.scenario}, ${e.controller})`, tone: "dim" };
    case "sumo_finished":
      return { text: "Simulation finished", tone: "dim" };
    default:
      return null;
  }
}

export default function LiveNetwork() {
  const { geometry, frame, status, setStatus, link } = useSumo();
  const [nets, setNets] = useState<NetworkInfo[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [form, setForm] = useState<{ network: string; scenario: Scenario; choice: string }>({
    network: "sector_grid",
    scenario: "medium",
    choice: "equiflow",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    sumoApi
      .networks()
      .then((r) => {
        setNets(r.networks);
        setStatus(r.status);
        if (r.status.run)
          setForm({ network: r.status.run.network, scenario: r.status.run.scenario, choice: choiceOf(r.status.run.controller, r.status.run.base) });
      })
      .catch(() => {});
  }, [setStatus, link]);

  const run = status?.run ?? null;
  const tls = geometry?.tls ?? [];
  const selected = tls.find((t) => t.id === picked) ?? tls[0];
  const snap = frame?.junctions.find((j) => j.id === selected?.id);
  const vehicles = useMemo(() => new Map<string, Veh>((frame?.vehicles ?? []).map((v) => [v[0], v])), [frame]);
  const equiflow = run?.controller === "equiflow";
  const running = status?.state === "running" || status?.state === "paused";
  const netInfo = nets.find((n) => n.id === form.network);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    setBusy(true);
    try {
      const r = await fn();
      if (r && typeof r === "object" && "state" in (r as object)) setStatus(r as never);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  const m = frame?.metrics;
  const amb = m?.per_class.ambulance;
  const car = m?.per_class.car;
  const events = (frame?.events ?? []).map((e) => ({ e, d: describe(e) })).filter((x) => x.d).slice(0, 30);

  return (
    <main className="shell">
      <header className="pagehead">
        <div>
          <h1>Live network</h1>
          <p className="lede">
            Each junction of the SUMO model runs live. Click a junction to see its signals, its cameras and why it chose
            its current green.
          </p>
        </div>
        <div className="pills">
          <span className={`pill link-${link}`}>{link === "live" ? "Connected" : link === "connecting" ? "Connecting" : "Backend offline"}</span>
          {status && <span className={`pill state-${status.state}`}>{status.state === "running" ? "Simulation running" : `Simulation ${status.state}`}</span>}
        </div>
      </header>

      {status && !status.available && (
        <p className="banner warn">
          The SUMO live view is off: {status.reason}
        </p>
      )}

      <section className="controls panel" aria-label="Simulation controls">
        <label>
          <span>Network</span>
          <select value={form.network} onChange={(e) => setForm({ ...form, network: e.target.value })}>
            {nets.map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Traffic</span>
          <select value={form.scenario} onChange={(e) => setForm({ ...form, scenario: e.target.value as Scenario })}>
            {(netInfo?.scenarios ?? (["low", "medium", "high", "asymmetric"] as Scenario[])).map((s) => (
              <option key={s} value={s}>
                {SCEN_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="seg">
          <legend>Signal controller</legend>
          {CONTROLLERS.map((c) => (
            <button key={c.id} type="button" title={c.hint} aria-pressed={form.choice === c.id} onClick={() => setForm({ ...form, choice: c.id })}>
              {c.label}
            </button>
          ))}
        </fieldset>
        <button className="btn-primary" disabled={busy || !status?.available} onClick={() => {
          const c = CONTROLLERS.find((x) => x.id === form.choice) ?? CONTROLLERS[0];
          act(() => sumoApi.start({ network: form.network, scenario: form.scenario, controller: c.controller, base: c.base, speed: run?.speed }));
        }}>
          {running ? "Restart with these settings" : "Start simulation"}
        </button>
        <div className="sep" />
        <fieldset className="seg">
          <legend>Speed</legend>
          {SPEEDS.map((s) => (
            <button key={s} type="button" aria-pressed={run?.speed === s} disabled={!running} onClick={() => act(() => sumoApi.speed(s))}>
              {s}×
            </button>
          ))}
        </fieldset>
        <button className="btn-quiet" disabled={!running} onClick={() => act(() => sumoApi.pause(status?.state !== "paused"))}>
          {status?.state === "paused" ? "Resume" : "Pause"}
        </button>
        <button className="btn-amb" disabled={!running} onClick={() => act(() => sumoApi.ambulance())}>
          Send an ambulance
        </button>
        {error && <p className="error">{error}</p>}
      </section>

      {netInfo && <p className="netdesc">{netInfo.description}</p>}

      <section className="kpis" aria-label="Network metrics">
        <div><span>Simulation time</span><strong>{frame ? fmtTime(frame.t) : "–"}</strong></div>
        <div><span>Vehicles on the road</span><strong>{m?.in_network ?? "–"}</strong></div>
        <div><span>Stopped now</span><strong>{m?.halting ?? "–"}</strong></div>
        <div><span>Trips completed</span><strong>{m?.arrived ?? "–"}</strong></div>
        <div><span>Average wait, cars</span><strong>{car?.mean_waiting_s != null ? `${car.mean_waiting_s} s` : "–"}</strong></div>
        <div className="kpi-amb"><span>Average wait, ambulances</span><strong>{amb?.mean_waiting_s != null ? `${amb.mean_waiting_s} s` : "–"}</strong></div>
        {equiflow && <div className="kpi-amb"><span>Priority runs</span><strong>{m?.preemptions ?? "–"}</strong></div>}
        {equiflow && <div className="kpi-amb"><span>Detection to green</span><strong>{m?.latency_avg_s != null ? `${m.latency_avg_s} s` : "–"}</strong></div>}
      </section>

      {!geometry ? (
        <p className="waiting">
          {link === "offline"
            ? "Can't reach the backend at " + API_URL + ". Start it in the backend folder (uvicorn app.main:app --port 8000, or backend/run_wsl.sh in WSL); this page reconnects by itself."
            : status?.available === false
              ? "Install SUMO to use the live view."
              : "Pick a network and press Start simulation."}
        </p>
      ) : (
        <>
          <div className="livegrid">
            <div className="mapcol">
              <NetworkCanvas geometry={geometry} frame={frame} selected={selected?.id ?? null} onSelect={setPicked} cameraRange={CAMERA_RANGE} />
              <ul className="legend" aria-label="Legend">
                {VTYPES.map((v) => (
                  <li key={v}>
                    <i style={{ background: VCOLOR[v], outline: v === "ambulance" ? "2px solid #ef4b4b" : undefined }} />
                    {v}
                  </li>
                ))}
                <li><i className="lg-bar" style={{ background: "#2fcf8f" }} />green</li>
                <li><i className="lg-bar" style={{ background: "#ef4b4b" }} />red</li>
                <li><i className="lg-zone" />camera range</li>
                <li className="lg-hint">Scroll to zoom, drag to move, double-click to reset</li>
              </ul>
              {tls.length === 0 && <p className="hint">This network has no traffic signals (give-way junction or roundabout), so there is nothing to control. Pick a signalised network to see EquiFlow at work.</p>}
            </div>
            <div className="sidecol">
              {tls.length > 1 && (
                <nav className="tabs" aria-label="Junctions">
                  {tls.map((t) => {
                    const j = frame?.junctions.find((x) => x.id === t.id);
                    return (
                      <button key={t.id} aria-pressed={t.id === selected?.id} onClick={() => setPicked(t.id)} className={j ? `tab-${j.mode.toLowerCase()}` : undefined}>
                        {t.id}
                      </button>
                    );
                  })}
                </nav>
              )}
              {selected && <JunctionPanel geo={selected} snap={snap} equiflow={equiflow} simTime={frame?.t ?? 0} />}
            </div>
          </div>

          {selected && (
            <section className="camsec" aria-label={`Cameras at junction ${selected.id}`}>
              <h2>
                Cameras at junction {selected.id}
                <small>
                  What the detector sees on each approach. Red box: confirmed ambulance ({5} of the last {M} frames voted ambulance). Yellow: some votes. Green: other vehicle.
                </small>
              </h2>
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
                    m={M}
                  />
                ))}
              </div>
            </section>
          )}

          <section className="panel log">
            <h2>What the system did</h2>
            {events.length === 0 ? (
              <p className="hint">Events appear here when an ambulance is detected, given priority, or released.</p>
            ) : (
              <ol>
                {events.map(({ e, d }) => (
                  <li key={e.id} className={`tone-${d!.tone}`}>
                    <time>{fmtTime(e.sim_time)}</time>
                    <span>{d!.text}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </main>
  );
}
