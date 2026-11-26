"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { VTYPES, sumoApi, type ResultRow, type RobustRow, type TrainRow, type VType } from "@/lib/sumo";
import { BarChart3, FlaskConical, Loader2, Route, ShieldQuestion, Table2, TrendingDown } from "lucide-react";
import { Card, Empty, Kpi } from "./ui";

const METRICS = {
  mean_waiting_s: "Average waiting time",
  mean_time_loss_s: "Average time lost (vs free flow)",
  mean_travel_time_s: "Average trip time",
} as const;
type Metric = keyof typeof METRICS;

const CTRL_LABEL: Record<string, string> = {
  fixed: "Fixed-time",
  actuated: "Actuated",
  equiflow: "EquiFlow (adaptive)",
  "equiflow-marl": "EquiFlow (MARL)",
  "equiflow-nocorridor": "EquiFlow without green corridor",
  "equiflow-norecovery": "EquiFlow without fair recovery",
  "equiflow-nogapout": "EquiFlow without gap-out",
  "fixed+preempt": "Fixed-time + simple preemption",
  "actuated+preempt": "Actuated + simple preemption",
};
const CTRL_COLOR: Record<string, string> = {
  fixed: "#7d8790",
  actuated: "#f6a623",
  equiflow: "#14b8a6",
  "equiflow-marl": "#4f8ff7",
  "equiflow-nocorridor": "#8e7dff",
  "equiflow-norecovery": "#b8b2a6",
  "equiflow-nogapout": "#9fa7ae",
  "fixed+preempt": "#c06bd6",
  "actuated+preempt": "#e07b5f",
};
const MAIN = ["fixed", "actuated", "equiflow", "equiflow-marl"];
const NET_LABEL: Record<string, string> = {
  cross_signal: "4-arm crossing",
  t_signal: "Signalised T",
  five_way_signal: "5-arm chowk",
  six_way: "6-arm chowk",
  sector_grid: "Sector grid",
  diamond: "Diamond interchange",
  t_priority: "Give-way T",
  y_junction: "Y-junction",
  roundabout: "Roundabout",
};
const SIGNALISED = ["cross_signal", "t_signal", "five_way_signal", "six_way", "sector_grid", "diamond"];
const SCEN = ["low", "medium", "high", "asymmetric"];
const SCEN_LABEL: Record<string, string> = { low: "Light", medium: "Medium", high: "Heavy", asymmetric: "Asymmetric" };
const TRAIN_COLORS = ["#2fcf8f", "#4aa3ff", "#f6a623", "#ef4b4b", "#c06bd6", "#9aa3ab", "#22c7f2", "#f0e019"];

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const f1 = (v: number | null | undefined) => (v === null || v === undefined ? "–" : v.toFixed(1));

export default function Results() {
  const [rows, setRows] = useState<ResultRow[] | null>(null);
  const [robust, setRobust] = useState<RobustRow[]>([]);
  const [train, setTrain] = useState<TrainRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [net, setNet] = useState("all");
  const [scen, setScen] = useState("all");
  const [metric, setMetric] = useState<Metric>("mean_waiting_s");
  const [robNet, setRobNet] = useState("cross_signal");

  useEffect(() => {
    sumoApi.results().then(setRows).catch((e) => setError(e.message));
    sumoApi.robustness().then(setRobust).catch(() => {});
    sumoApi.training().then(setTrain).catch(() => {});
  }, []);

  const view = useMemo(() => {
    if (!rows) return null;
    const nets = net === "all" ? SIGNALISED : [net];
    const scens = scen === "all" ? SCEN : [scen];
    const sel = rows.filter((r) => nets.includes(r.intersection) && scens.includes(r.scenario));
    const ctrls = Array.from(new Set(sel.map((r) => r.controller)))
      .filter((c) => c in CTRL_LABEL)
      .sort((a, b) => Object.keys(CTRL_LABEL).indexOf(a) - Object.keys(CTRL_LABEL).indexOf(b));
    const k = (r: ResultRow) => `${r.intersection}|${r.scenario}|${r.seed}`;
    const main = MAIN.filter((c) => ctrls.includes(c));
    const sets = main.map((c) => new Set(sel.filter((r) => r.controller === c).map(k)));
    const common = sets.length ? new Set([...sets[0]].filter((x) => sets.every((s) => s.has(x)))) : new Set<string>();
    const value = (c: string, vt: VType, m: Metric) =>
      mean(
        sel
          .filter((r) => r.controller === c && r.vehicle_type === vt && r[m] !== null)
          .filter((r) => !main.includes(c) || common.has(k(r)))
          .map((r) => r[m] as number),
      );
    const seeds = new Set([...common].map((x) => x.split("|")[2]));
    return { ctrls, common, value, seeds };
  }, [rows, net, scen]);

  if (error)
    return (
      <Card>
        <Empty icon={ShieldQuestion} title="Could not load results">
          {error}
        </Empty>
      </Card>
    );
  if (!rows || !view)
    return (
      <Card>
        <Empty icon={Loader2} title="Loading results…" />
      </Card>
    );
  if (rows.length === 0)
    return (
      <Card>
        <Empty icon={BarChart3} title="No results yet">
          Run <code>python sumo/run_matrix.py</code> then <code>python sumo/aggregate.py</code> to produce them.
        </Empty>
      </Card>
    );

  const { ctrls, common, value, seeds } = view;
  const max = Math.max(1, ...ctrls.flatMap((c) => VTYPES.map((vt) => value(c, vt, metric) ?? 0)));
  const w = (vt: VType, c: string) => value(c, vt, "mean_waiting_s");
  const pct = (a: number | null, b: number | null) => (a && b !== null ? Math.round((1 - b / a) * 100) : null);

  // per network, heavy traffic, averaged over seeds
  const cell = (n: string, c: string, vt: VType) =>
    mean(
      rows
        .filter((r) => r.intersection === n && r.controller === c && r.scenario === "high" && r.vehicle_type === vt && r.mean_waiting_s !== null)
        .map((r) => r.mean_waiting_s as number),
    );

  // green corridor ablation: multi-junction networks only
  const corr = (c: string, vt: VType, m: Metric) =>
    mean(
      rows
        .filter((r) => ["sector_grid", "diamond"].includes(r.intersection) && ["medium", "high"].includes(r.scenario))
        .filter((r) => r.controller === c && r.vehicle_type === vt && r[m] !== null)
        .map((r) => r[m] as number),
    );
  const hasCorr = rows.some((r) => r.controller === "equiflow-nocorridor");

  // robustness grid
  const rob = robust.filter((r) => r.network === robNet);
  const misses = Array.from(new Set(rob.map((r) => r.miss_prob))).sort((a, b) => a - b);
  const fps = Array.from(new Set(rob.map((r) => r.fp_prob))).sort((a, b) => a - b);
  const robNets = Array.from(new Set(robust.map((r) => r.network)));

  // training curves
  const series = new Map<string, TrainRow[]>();
  for (const r of train) {
    const key = `${r.network} ${r.scenario}`;
    if (!series.has(key)) series.set(key, []);
    series.get(key)!.push(r);
  }
  const tMaxEp = Math.max(1, ...train.map((r) => r.episode));
  const tMaxW = Math.max(1, ...train.map((r) => r.mean_wait_s ?? 0));

  const barH = 14;
  const groupH = ctrls.length * (barH + 4) + 18;
  const W = 760;
  const L = 110;

  return (
    <>
      <section className="grid g-kpi" aria-label="Headline results" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
        <Kpi
          label="Ambulance waiting at signals (EquiFlow)"
          icon={Route}
          tone="emg"
          value={f1(w("ambulance", "equiflow"))}
          unit="s"
          meta={
            <>
              vs {f1(w("ambulance", "fixed"))} s fixed-time ({pct(w("ambulance", "fixed"), w("ambulance", "equiflow")) ?? "–"}% less) and {f1(w("ambulance", "actuated"))} s actuated. MARL:{" "}
              {f1(w("ambulance", "equiflow-marl"))} s
            </>
          }
        />
        <Kpi
          label="Car waiting at signals (EquiFlow)"
          icon={TrendingDown}
          tone="info"
          value={f1(w("car", "equiflow"))}
          unit="s"
          meta={
            <>
              vs {f1(w("car", "fixed"))} s fixed-time ({pct(w("car", "fixed"), w("car", "equiflow")) ?? "–"}% less) and {f1(w("car", "actuated"))} s actuated. MARL:{" "}
              {f1(w("car", "equiflow-marl"))} s
            </>
          }
        />
        <Kpi
          label="Matched comparison runs"
          icon={FlaskConical}
          value={common.size}
          meta={`network × traffic × seed combinations run with all four controllers (${seeds.size} ${seeds.size === 1 ? "seed" : "seeds"})`}
        />
      </section>

      <Card>
      <div className="toolbar" aria-label="Filters" role="group">
        <label className="field">
          <span>Network</span>
          <select className="select" value={net} onChange={(e) => setNet(e.target.value)}>
            <option value="all">All signalised networks</option>
            {SIGNALISED.map((n) => (
              <option key={n} value={n}>
                {NET_LABEL[n]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Traffic</span>
          <select className="select" value={scen} onChange={(e) => setScen(e.target.value)}>
            <option value="all">All levels</option>
            {SCEN.map((s) => (
              <option key={s} value={s}>
                {SCEN_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="seg">
          <legend>Measure</legend>
          <div className="seg-btns">
            {(Object.keys(METRICS) as Metric[]).map((m) => (
              <button key={m} type="button" aria-pressed={metric === m} onClick={() => setMetric(m)}>
                {METRICS[m].replace("Average ", "")}
              </button>
            ))}
          </div>
        </fieldset>
      </div>
      </Card>

      <Card title={`${METRICS[metric]} by vehicle type`} icon={BarChart3} sub="Seconds, lower is better">
        <ul className="legend">
          {ctrls.map((c) => (
            <li key={c}>
              <i style={{ background: CTRL_COLOR[c] ?? "#ccc" }} />
              {CTRL_LABEL[c] ?? c}
            </li>
          ))}
        </ul>
        <svg viewBox={`0 0 ${W} ${VTYPES.length * groupH}`} className="bars" role="img" aria-label={`${METRICS[metric]} by vehicle type and controller`}>
          {VTYPES.map((vt, gi) => (
            <g key={vt} transform={`translate(0, ${gi * groupH})`}>
              <text x={0} y={16} className={vt === "ambulance" ? "bar-group is-amb" : "bar-group"}>
                {vt}
              </text>
              {ctrls.map((c, i) => {
                const v = value(c, vt, metric);
                const bw = v === null ? 0 : ((W - L - 60) * v) / max;
                const y = 4 + i * (barH + 4);
                return (
                  <g key={c}>
                    <rect x={L} y={y} width={Math.max(1, bw)} height={barH} rx={3} fill={CTRL_COLOR[c] ?? "#ccc"} />
                    <text x={L + bw + 6} y={y + barH - 3} className="bar-val">
                      {f1(v)}
                    </text>
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
        <p className="hint wide">
          Each bar averages one-hour SUMO runs for the selected networks and traffic levels, over the same demand for every
          controller. Fixed-time, actuated, EquiFlow and EquiFlow MARL are averaged over exactly the same runs. Refresh with{" "}
          <code>python sumo/run_matrix.py</code> then <code>python sumo/aggregate.py</code> (held-out seeds 6-10, every
          controller; shown when <code>sumo/results/heldout/</code> exists, otherwise the older{" "}
          <code>run_equiflow.py</code> results).
        </p>
      </Card>

      <Card title="Per network, heavy traffic" icon={Table2} sub="Average wait in seconds, averaged over seeds" flush>
        <div className="table-wrap">
        <table className="rtable">
          <thead>
            <tr>
              <th>Network</th>
              {MAIN.map((c) => (
                <th key={c} colSpan={2}>
                  {CTRL_LABEL[c]}
                </th>
              ))}
            </tr>
            <tr>
              <th />
              {MAIN.map((c) => (
                <Fragment key={c}>
                  <th>car</th>
                  <th className="is-amb">ambulance</th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {SIGNALISED.map((n) => (
              <tr key={n}>
                <th scope="row">{NET_LABEL[n]}</th>
                {MAIN.map((c) =>
                  (["car", "ambulance"] as VType[]).map((vt) => (
                    <td key={`${c}-${vt}`} className={vt === "ambulance" ? "is-amb" : undefined}>
                      {f1(cell(n, c, vt))}
                    </td>
                  )),
                )}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </Card>

      {hasCorr && (
        <Card title="Green corridor" icon={Route} sub="Sector grid and diamond interchange, medium and heavy traffic">
          <dl className="kv">
            <div>
              <dt>Ambulance time lost, with corridor</dt>
              <dd>{f1(corr("equiflow", "ambulance", "mean_time_loss_s"))} s</dd>
            </div>
            <div>
              <dt>Ambulance time lost, without corridor</dt>
              <dd>{f1(corr("equiflow-nocorridor", "ambulance", "mean_time_loss_s"))} s</dd>
            </div>
            <div>
              <dt>Car wait, with / without corridor</dt>
              <dd>
                {f1(corr("equiflow", "car", "mean_waiting_s"))} s / {f1(corr("equiflow-nocorridor", "car", "mean_waiting_s"))} s
              </dd>
            </div>
          </dl>
          <p className="hint wide">
            Once a camera confirms an ambulance, the next signals on its route start clearing when it is within 25 s of them,
            before their own cameras can see it.
          </p>
        </Card>
      )}

      {robust.length > 0 && (
        <Card title="Robustness to camera errors" icon={ShieldQuestion} sub="Heavy traffic, one hour per cell">
          <div className="toolbar" style={{ marginBottom: 12 }}>
            <label className="field">
              <span>Network</span>
              <select className="select" value={robNet} onChange={(e) => setRobNet(e.target.value)}>
                {robNets.map((n) => (
                  <option key={n} value={n}>
                    {NET_LABEL[n] ?? n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="table-wrap">
          <table className="rtable robust">
            <thead>
              <tr>
                <th>Frames missed ↓ / false-alarm frames →</th>
                {fps.map((fp) => (
                  <th key={fp}>{Math.round(fp * 100)}%</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {misses.map((ms) => (
                <tr key={ms}>
                  <th scope="row">{Math.round(ms * 100)}%</th>
                  {fps.map((fp) => {
                    const r = rob.find((x) => x.miss_prob === ms && x.fp_prob === fp);
                    const bad = (r?.false_confirmations ?? 0) > 5;
                    return (
                      <td key={fp} className={bad ? "is-bad" : undefined}>
                        {r ? (
                          <>
                            <b>{r.false_confirmations}</b> false · amb {f1(r.ambulance_wait_s)} s · car {f1(r.car_wait_s)} s
                          </>
                        ) : (
                          "–"
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <p className="hint wide">
            Per-frame chance that the detector loses a vehicle (rows) or that a non-ambulance is scored like an ambulance
            (columns), heavy traffic, one hour. &ldquo;False&rdquo; counts non-ambulances confirmed as ambulances. The 5-of-8 vote
            absorbs missed frames and occasional false scores; only very noisy classifiers (20% or more of frames) cause false
            priority. Refresh with <code>python sumo/run_robustness.py</code>.
          </p>
        </Card>
      )}

      {train.length > 0 && (
        <Card title="MARL training: average wait per episode" icon={TrendingDown} sub="Seconds per episode, by training network">
          <ul className="legend">
            {[...series.keys()].map((k, i) => (
              <li key={k}>
                <i style={{ background: TRAIN_COLORS[i % TRAIN_COLORS.length] }} />
                {k}
              </li>
            ))}
          </ul>
          <svg viewBox="0 0 760 240" className="bars" role="img" aria-label="Average wait per training episode for each training network">
            <line x1={40} y1={210} x2={750} y2={210} className="axis" />
            <line x1={40} y1={10} x2={40} y2={210} className="axis" />
            <text x={34} y={16} textAnchor="end" className="bar-val">{tMaxW.toFixed(0)}</text>
            <text x={34} y={212} textAnchor="end" className="bar-val">0</text>
            <text x={750} y={232} textAnchor="end" className="bar-val">episode {tMaxEp}</text>
            {[...series.values()].map((s, i) => (
              <polyline
                key={i}
                fill="none"
                stroke={TRAIN_COLORS[i % TRAIN_COLORS.length]}
                strokeWidth={2}
                points={s
                  .filter((r) => r.mean_wait_s !== null)
                  .map((r) => `${40 + (710 * r.episode) / tMaxEp},${210 - (200 * (r.mean_wait_s as number)) / tMaxW}`)
                  .join(" ")}
              />
            ))}
          </svg>
          <p className="hint wide">
            One agent per junction, all sharing one network. Each episode is half an hour of SUMO traffic; exploration falls
            from 30% to 3%. Train more with <code>python marl/train_marl.py --episodes 40</code>.
          </p>
        </Card>
      )}
    </>
  );
}
