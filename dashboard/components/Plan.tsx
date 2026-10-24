import type { Approach, Signal } from "@/lib/types";

/** Top-down plan of the junction. Each approach has a four-lamp signal head:
 *  ambulance (blue) + the three conventional lamps (red, yellow, green). */

const HEAD_W = 26;
const HEAD_H = 94;
const LAMPS = ["amb", "red", "yellow", "green"] as const;

// Head position (top-left) and where its text block goes. Heads sit beside the stop line of their arm.
const LAYOUT: Record<Approach, { x: number; y: number; tx: number; anchor: "start" | "end" }> = {
  North: { x: 126, y: 42, tx: 116, anchor: "end" },
  East: { x: 252, y: 42, tx: 288, anchor: "start" },
  West: { x: 126, y: 246, tx: 116, anchor: "end" },
  South: { x: 252, y: 246, tx: 288, anchor: "start" },
};

// The road arm each approach drives in on
const ARM: Record<Approach, { x: number; y: number; w: number; h: number }> = {
  North: { x: 160, y: 0, w: 80, h: 160 },
  South: { x: 160, y: 240, w: 80, h: 160 },
  West: { x: 0, y: 160, w: 160, h: 80 },
  East: { x: 240, y: 160, w: 160, h: 80 },
};

function Head({ s, a, remaining }: { s: Signal; a: Approach; remaining: number | null }) {
  const { x, y, tx, anchor } = LAYOUT[a];
  const lamp = s.lamps[a];
  const amb = s.ambulance[a];
  const lit = { amb, red: lamp === "red", yellow: lamp === "yellow", green: lamp === "green" };
  const isCurrent = s.current === a && s.stage !== "ALL_RED";
  const labelClass = amb ? "plan-name is-amb" : "plan-name";

  return (
    <g>
      <rect x={x} y={y} width={HEAD_W} height={HEAD_H} rx={6} className="head" />
      {LAMPS.map((k, i) => (
        <circle
          key={k}
          cx={x + HEAD_W / 2}
          cy={y + 14 + i * 22}
          r={8}
          className={`lamp lamp-${k}${lit[k] ? " on" : ""}`}
        />
      ))}
      <text x={tx} y={y + 16} textAnchor={anchor} className={labelClass}>
        {a}
      </text>
      <text x={tx} y={y + 34} textAnchor={anchor} className="plan-sub">
        {s.vehicles[a]} {s.vehicles[a] === 1 ? "vehicle" : "vehicles"}
      </text>
      <text x={tx} y={y + 50} textAnchor={anchor} className="plan-sub">
        {isCurrent && remaining !== null
          ? `${lamp} · ${Math.ceil(remaining)} s left`
          : isCurrent
            ? `${lamp} · held`
            : `waiting ${Math.round(s.waiting_s[a])} s`}
      </text>
      {amb && (
        <text x={tx} y={y + 68} textAnchor={anchor} className="plan-amb">
          ambulance
        </text>
      )}
    </g>
  );
}

export default function Plan({ signal, remaining }: { signal: Signal; remaining: number | null }) {
  const centre =
    signal.mode === "PREEMPT"
      ? ["Ambulance", signal.active_preempt ?? ""]
      : signal.mode === "RECOVERY"
        ? ["Recovering", ""]
        : ["Normal", "cycle"];

  return (
    <svg
      viewBox="0 0 400 400"
      className="plan"
      role="img"
      aria-label={`Junction ${signal.name}: ${signal.current ?? "no"} approach is ${signal.current ? signal.lamps[signal.current] : "red"}`}
    >
      <rect x={160} y={0} width={80} height={400} className="road" />
      <rect x={0} y={160} width={400} height={80} className="road" />
      {/* lane paint */}
      <line x1={200} y1={0} x2={200} y2={160} className="paint" />
      <line x1={200} y1={240} x2={200} y2={400} className="paint" />
      <line x1={0} y1={200} x2={160} y2={200} className="paint" />
      <line x1={240} y1={200} x2={400} y2={200} className="paint" />
      {/* stop lines */}
      <line x1={160} y1={158} x2={240} y2={158} className="stop" />
      <line x1={160} y1={242} x2={240} y2={242} className="stop" />
      <line x1={158} y1={160} x2={158} y2={240} className="stop" />
      <line x1={242} y1={160} x2={242} y2={240} className="stop" />

      {(Object.keys(ARM) as Approach[]).map(
        (a) => signal.ambulance[a] && <rect key={a} {...ARM[a]} className="arm-amb" />,
      )}

      <text x={200} y={196} textAnchor="middle" className="centre-main">
        {centre[0]}
      </text>
      <text x={200} y={214} textAnchor="middle" className="centre-sub">
        {centre[1]}
      </text>

      {(Object.keys(LAYOUT) as Approach[]).map((a) => (
        <Head key={a} s={signal} a={a} remaining={remaining} />
      ))}
    </svg>
  );
}
