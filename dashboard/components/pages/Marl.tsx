"use client";

import { BookOpen, BrainCircuit, Eye, GitBranch, ListChecks, Network, TrendingDown } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { controllerName, num } from "@/lib/format";
import { useLive } from "@/lib/live";
import { sumoApi, type TrainRow } from "@/lib/sumo";
import { LineChart, SERIES_COLORS } from "../charts";
import { why } from "../sumo/JunctionPanel";
import { Badge, Banner, Card, Empty, KV, Kpi, PageHeader, Skeleton } from "../ui";

export default function Marl() {
  const frame = useLive((s) => s.sumo.frame);
  const status = useLive((s) => s.sumo.status);
  const snapshot = useLive((s) => s.eq.snapshot);
  const [train, setTrain] = useState<TrainRow[] | null>(null);
  const [trainErr, setTrainErr] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => {
    sumoApi
      .training()
      .then(setTrain)
      .catch((e) => setTrainErr(e.message));
  }, []);

  const junctions = frame?.junctions ?? [];
  const marlJ = junctions.filter((j) => j.controller.startsWith("marl"));
  const trained = marlJ.filter((j) => !j.controller.includes("untrained"));
  const fallback = marlJ.length - trained.length;
  const j = junctions.find((x) => x.id === picked) ?? marlJ[0] ?? junctions[0];
  const runBase = status?.run ? (status.run.controller === "equiflow" ? status.run.base ?? "adaptive" : status.run.controller) : null;
  const camController = snapshot?.intersections[0]?.controller;

  const tr = useMemo(() => {
    if (!train?.length) return null;
    const series = new Map<string, TrainRow[]>();
    for (const r of train) {
      const k = `${r.network} · ${r.scenario}`;
      if (!series.has(k)) series.set(k, []);
      series.get(k)!.push(r);
    }
    const last = train[train.length - 1];
    const first10 = train.slice(0, 10).map((r) => r.mean_wait_s).filter((v): v is number => v !== null);
    const last10 = train.slice(-10).map((r) => r.mean_wait_s).filter((v): v is number => v !== null);
    const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
    return { series, last, episodes: train.length, firstAvg: avg(first10), lastAvg: avg(last10) };
  }, [train]);

  return (
    <div className="page">
      <PageHeader
        title="MARL controller"
        description="The fairness-aware multi-agent reinforcement-learning controller: one agent per signalised junction, all sharing one Q-network. It only chooses the next green and its length; emergency priority, yellow / all-red timing and fair recovery stay in the rule-based safety layer above it."
        actions={
          <Link href="/simulation" className="btn sm">
            Run with EquiFlow MARL
          </Link>
        }
      />

      <section className="grid g-kpi" aria-label="Controller status">
        <Kpi
          label="Simulation controller"
          icon={BrainCircuit}
          tone={runBase === "marl" ? "info" : "neutral"}
          value={runBase ? controllerName(runBase) : "–"}
          na={runBase ? null : "No simulation running"}
          meta={runBase && runBase !== "marl" ? "Select EquiFlow MARL on the Simulation page to watch the agents" : undefined}
        />
        <Kpi
          label="Active agents"
          icon={GitBranch}
          value={trained.length}
          unit={`of ${junctions.length} junctions`}
          na={frame ? null : "No simulation running"}
          tone={fallback ? "warn" : trained.length ? "ok" : "neutral"}
          meta={fallback ? <Badge tone="warn">{fallback} using adaptive fallback (no trained weights)</Badge> : trained.length ? "Trained weights loaded" : undefined}
        />
        <Kpi label="Camera junction controller" icon={Eye} value={controllerName(camController)} na={camController ? null : "No data"} meta="Set by controller: in backend config" />
        <Kpi
          label="Training episodes"
          icon={TrendingDown}
          value={tr ? tr.episodes : "–"}
          na={train === null && !trainErr ? "Loading…" : tr ? null : "No training log"}
          meta={tr ? `exploration now ${Math.round(tr.last.epsilon * 100)}% · last loss ${num(tr.last.loss ?? null, 4)}` : undefined}
        />
      </section>

      {runBase && runBase !== "marl" && (
        <Banner tone="info" title="The running simulation is not using the MARL controller">
          The live decisions below come from {controllerName(runBase)}. Restart the simulation with EquiFlow MARL to see the agents choose greens.
        </Banner>
      )}

      <div className="grid g-main-side">
        <Card
          title={j ? `Decisions at junction ${j.id}` : "Live decisions"}
          icon={ListChecks}
          sub="Each green the controller chose, with the inputs recorded with it (vehicles and wait on the chosen approach)."
          actions={
            junctions.length > 1 && (
              <div className="chips" role="group" aria-label="Junction">
                {junctions.map((x) => (
                  <button key={x.id} type="button" aria-pressed={x.id === j?.id} onClick={() => setPicked(x.id)}>
                    {x.id}
                  </button>
                ))}
              </div>
            )
          }
          flush
        >
          {!j ? (
            <Empty compact icon={Network} title="No simulation running">
              Decisions are streamed from the SUMO run. <Link href="/simulation">Start one</Link>.
            </Empty>
          ) : (
            <>
              <div style={{ padding: "0 16px 12px" }}>
                <h4 className="section-title">Current observation (inputs)</h4>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">Approach</th>
                        <th scope="col" className="r">Vehicles (queue)</th>
                        <th scope="col" className="r">Waited since green</th>
                        <th scope="col">Has green</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(j.vehicles).map((a) => (
                        <tr key={a}>
                          <th scope="row">{a}</th>
                          <td className="r">{j.vehicles[a]}</td>
                          <td className="r">{Math.round(j.waiting_s[a] ?? 0)} s</td>
                          <td>{j.current === a && j.stage === "GREEN" ? <Badge tone="ok">Green</Badge> : <span className="subtle">No</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <caption className="sr-only">Recent decisions</caption>
                  <thead>
                    <tr>
                      <th scope="col">When</th>
                      <th scope="col">Action: green</th>
                      <th scope="col" className="r">Duration</th>
                      <th scope="col">Decided by</th>
                      <th scope="col">Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {j.decisions.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="subtle">No decision yet in this run.</td>
                      </tr>
                    ) : (
                      j.decisions.slice(0, 12).map((d, i) => (
                        <tr key={`${d.t}-${i}`} className={d.source === "preempt" ? "is-emg" : undefined}>
                          <td className="num">{Math.max(0, Math.round((frame?.t ?? 0) - d.t))} s ago</td>
                          <th scope="row">{d.approach}</th>
                          <td className="r">{d.green_s !== undefined ? `${Math.round(d.green_s)} s` : "held"}</td>
                          <td>
                            <Badge tone={d.source === "preempt" ? "emg" : d.source === "recovery" ? "warn" : d.source === "base" ? "info" : "neutral"} icon={false}>
                              {d.source === "base" ? (j.controller.startsWith("marl") && !j.controller.includes("untrained") ? "MARL agent" : controllerName(j.controller)) : d.source === "preempt" ? "Safety layer: priority" : d.source === "recovery" ? "Safety layer: recovery" : `SUMO ${d.source}`}
                            </Badge>
                          </td>
                          <td style={{ minWidth: 260 }}>{why(d, j.controller)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <p className="chart-note" style={{ padding: "8px 16px 14px" }}>
                Not exposed by the backend: per-action Q-values (model confidence), the per-step reward and the decision latency. They
                are not shown rather than estimated.
              </p>
            </>
          )}
        </Card>

        <Card title="Policy" icon={BookOpen} sub="How the agent is built (backend/app/controllers/marl.py). This describes the implementation; it is not a live value.">
          <KV
            left
            rows={[
              ["Agents", "One per signalised junction, sharing one Q-network (parameter sharing)"],
              ["Action", "Serve signal group g for 8, 15 or 25 s"],
              ["Features", "Queue and wait on g, rest of the junction's queue and longest wait, whether g just had green, green length"],
              ["Reward", "−(halting vehicles × s) − fairness penalty beyond 45 s longest wait − long-wait penalty (> 20 s)"],
              ["Hard guard", "An approach that has waited 90 s is served next, whatever the network says"],
              ["Learner", "DQN: 2-layer MLP, Adam, replay buffer, target network (numpy)"],
              ["Not learned", "Emergency priority, green corridor, yellow / all-red, fair recovery"],
            ]}
          />
        </Card>
      </div>

      <Card title="Training progress" icon={TrendingDown} sub="marl/training_log.csv via /api/sumo/training. Each episode is half an hour of SUMO traffic.">
        {trainErr ? (
          <p className="error">Could not load the training log: {trainErr}</p>
        ) : train === null ? (
          <Skeleton h={200} />
        ) : !tr ? (
          <Empty compact title="No training log">Train with <code>python marl/train_marl.py --episodes 40</code>.</Empty>
        ) : (
          <div className="grid g-2">
            <div>
              <h4 className="section-title">Average wait per episode (s), by training network</h4>
              <LineChart
                series={[...tr.series.entries()].map(([label, rows], i) => ({ label, color: SERIES_COLORS[i % SERIES_COLORS.length], points: rows.map((r) => [r.episode, r.mean_wait_s] as [number, number | null]) }))}
                xFormat={(x) => `ep ${Math.round(x)}`}
                yLabel="seconds"
                ariaLabel="Average wait per training episode"
              />
            </div>
            <div className="stack">
              <h4 className="section-title">Exploration rate and loss</h4>
              <LineChart
                series={[{ label: "exploration ε (%)", color: SERIES_COLORS[2], points: train.map((r) => [r.episode, r.epsilon * 100] as [number, number]) }]}
                xFormat={(x) => `ep ${Math.round(x)}`}
                yLabel="%"
                height={150}
                ariaLabel="Exploration rate per episode"
              />
              <KV
                rows={[
                  ["Mean wait, first 10 episodes", tr.firstAvg !== null ? `${num(tr.firstAvg, 2)} s` : "–"],
                  ["Mean wait, last 10 episodes", tr.lastAvg !== null ? `${num(tr.lastAvg, 2)} s` : "–"],
                  ["Last episode", `${tr.last.episode} (${tr.last.network}, ${tr.last.scenario})`],
                ]}
              />
              <p className="chart-note">
                Episodes mix networks and demand levels, so per-episode waits are not directly comparable across series. The held-out
                comparison with the baselines is on <Link href="/reports">Analytics &amp; Reports</Link>.
              </p>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
