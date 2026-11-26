import type { Approach, Signal } from "@/lib/types";

/** Top-down plan of the camera junction, drawn from the live snapshot. Each approach has a four-lamp head
 *  (emergency + red, yellow, green). Bars on each arm show the vehicles the camera counts on that approach and,
 *  when a queue zone is configured, how many of them are standing still. Bar length is a count, not a distance. */

const HEAD_W = 26;
const HEAD_H = 94;
const LAMPS = ["emg", "red", "yellow", "green"] as const;
const BAR_MAX = 30; // vehicles that fill an arm

const LAYOUT: Record<Approach, { x: number; y: number; tx: number; anchor: "start" | "end" }> = {
  North: { x: 126, y: 42, tx: 116, anchor: "end" },
  East: { x: 252, y: 42, tx: 288, anchor: "start" },
  West: { x: 126, y: 264, tx: 116, anchor: "end" },
  South: { x: 252, y: 264, tx: 288, anchor: "start" },
};

const ARM: Record<Approach, { x: number; y: number; w: number; h: number }> = {
  North: { x: 160, y: 0, w: 80, h: 160 },
  South: { x: 160, y: 240, w: 80, h: 160 },
  West: { x: 0, y: 160, w: 160, h: 80 },
  East: { x: 240, y: 160, w: 160, h: 80 },
};

/** Bar inside the inbound half of each arm (left-hand traffic), growing away from the stop line. */
function bar(a: Approach, n: number, lane: 0 | 1) {
  const len = Math.min(1, n / BAR_MAX) * 150;
  const w = 12;
  switch (a) {
    case "North":
      return { x: 168 + lane * 16, y: 156 - len, width: w, height: len };
    case "South":
      return { x: 220 - lane * 16, y: 244, width: w, height: len };
    case "West":
      return { x: 156 - len, y: 220 - lane * 16, width: len, height: w };
    case "East":
      return { x: 244, y: 168 + lane * 16, width: len, height: w };
  }
}

function Head({ s, a, remaining }: { s: Signal; a: Approach; remaining: number | null }) {
  const { x, y, tx, anchor } = LAYOUT[a];
  const flashing = !!s.output?.flashing;
  const lamp = flashing ? "red" : s.lamps[a];
  const amb = s.ambulance[a];
  const lit = { emg: amb, red: lamp === "red", yellow: lamp === "yellow", green: lamp === "green" };
  const isCurrent = !flashing && s.current === a && s.stage !== "ALL_RED";
  const q = s.queues?.[a];

  return (
    <g>
      <rect x={x} y={y} width={HEAD_W} height={HEAD_H} rx={6} className="head" />
      {LAMPS.map((k, i) => (
        <circle key={k} cx={x + HEAD_W / 2} cy={y + 14 + i * 22} r={8} className={`lamp-c ${k}${lit[k] ? " on" : ""}${flashing && k === "red" ? " flash" : ""}`} />
      ))}
      <text x={tx} y={y + 16} textAnchor={anchor} className={amb ? "p-name is-emg" : "p-name"}>
        {a}
      </text>
      <text x={tx} y={y + 33} textAnchor={anchor} className="p-sub">
        {flashing ? "FLASHING RED" : lamp.toUpperCase()}
        {isCurrent && remaining !== null ? ` · ${Math.ceil(remaining)} s` : isCurrent ? " · held" : ""}
      </text>
      <text x={tx} y={y + 49} textAnchor={anchor} className="p-sub">
        {s.vehicles[a]} {s.vehicles[a] === 1 ? "vehicle" : "vehicles"}
        {q !== null && q !== undefined ? `, ${q} queued` : ""}
      </text>
      {!isCurrent && !flashing && (
        <text x={tx} y={y + 65} textAnchor={anchor} className="p-sub">
          waiting {Math.round(s.waiting_s[a])} s
        </text>
      )}
      {amb && (
        <text x={tx} y={y + 81} textAnchor={anchor} className="p-emg">
          EMERGENCY VEHICLE
        </text>
      )}
    </g>
  );
}

export default function Plan({ signal, remaining }: { signal: Signal; remaining: number | null }) {
  const approaches = Object.keys(ARM) as Approach[];
  const centre = signal.output?.flashing
    ? ["FAIL-SAFE", "flashing red"]
    : signal.mode === "PREEMPT"
      ? ["EMERGENCY", `priority ${signal.active_preempt ?? ""}`]
      : signal.mode === "RECOVERY"
        ? ["RECOVERY", "fair catch-up"]
        : ["NORMAL", signal.stage === "ALL_RED" ? "all-red" : signal.stage.toLowerCase()];
  const label = approaches
    .map((a) => `${a} ${signal.output?.flashing ? "flashing red" : signal.lamps[a]}, ${signal.vehicles[a]} vehicles${signal.ambulance[a] ? ", emergency vehicle" : ""}`)
    .join("; ");

  return (
    <div>
      <svg viewBox="0 0 400 400" className="plan" role="img" aria-label={`${signal.name}: ${label}`}>
        <rect x={0} y={0} width={400} height={400} className="ground" />
        <rect x={160} y={0} width={80} height={400} className="road" />
        <rect x={0} y={160} width={400} height={80} className="road" />
        <line x1={200} y1={0} x2={200} y2={160} className="paint" />
        <line x1={200} y1={240} x2={200} y2={400} className="paint" />
        <line x1={0} y1={200} x2={160} y2={200} className="paint" />
        <line x1={240} y1={200} x2={400} y2={200} className="paint" />
        <line x1={160} y1={158} x2={240} y2={158} className="stop" />
        <line x1={160} y1={242} x2={240} y2={242} className="stop" />
        <line x1={158} y1={160} x2={158} y2={240} className="stop" />
        <line x1={242} y1={160} x2={242} y2={240} className="stop" />

        {approaches.map((a) => signal.ambulance[a] && <rect key={`amb-${a}`} {...ARM[a]} className="arm-amb" />)}
        {approaches.map((a) => (
          <g key={`bars-${a}`}>
            <rect {...bar(a, signal.vehicles[a] ?? 0, 0)} className="vbar" rx={2} />
            {signal.queues?.[a] !== null && signal.queues?.[a] !== undefined && <rect {...bar(a, signal.queues[a] as number, 1)} className="qbar" rx={2} />}
          </g>
        ))}

        <text x={200} y={197} textAnchor="middle" className="c-main">
          {centre[0]}
        </text>
        <text x={200} y={214} textAnchor="middle" className="c-sub">
          {centre[1]}
        </text>
        {approaches.map((a) => (
          <Head key={a} s={signal} a={a} remaining={remaining} />
        ))}
      </svg>
      <div className="plan-legend" aria-hidden="true">
        <span>
          <i style={{ background: "#8ab6ff", opacity: 0.6 }} />
          vehicles counted (bar = count, max {BAR_MAX})
        </span>
        <span>
          <i style={{ background: "#f5b50b", opacity: 0.7 }} />
          queued (queue zone configured)
        </span>
        <span>
          <i style={{ background: "#c084fc", opacity: 0.5 }} />
          emergency vehicle on approach
        </span>
      </div>
    </div>
  );
}
