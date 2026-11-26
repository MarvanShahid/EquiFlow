"use client";

/* Small dependency-free SVG charts. They only draw the points they are given: no smoothing, no interpolation
   beyond straight segments between real samples, no invented values. */

import { useId } from "react";

export const SERIES_COLORS = ["#4f8ff7", "#14b8a6", "#f59e0b", "#ec4899", "#a78bfa", "#94a3b8", "#84cc16", "#f97316"];

export interface Series {
  label: string;
  color?: string;
  points: [number, number | null][]; // [x, y]; null = gap
}

function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

export function LineChart({
  series, height = 220, yLabel, xFormat, yFormat = (v) => String(Math.round(v * 10) / 10), ariaLabel, xLabel,
}: {
  series: Series[];
  height?: number;
  yLabel?: string;
  xLabel?: string;
  xFormat: (x: number) => string;
  yFormat?: (y: number) => string;
  ariaLabel: string;
}) {
  const id = useId();
  const W = 720;
  const H = height;
  const L = 48;
  const R = 12;
  const T = yLabel ? 26 : 12;
  const B = 30;
  const xs = series.flatMap((s) => s.points.map((p) => p[0]));
  const ys = series.flatMap((s) => s.points.map((p) => p[1]).filter((y): y is number => y !== null));
  if (!xs.length || !ys.length) return null;
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const yMax = niceMax(Math.max(...ys));
  const X = (x: number) => L + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - L - R);
  const Y = (y: number) => T + (1 - y / yMax) * (H - T - B);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
  const xt = x1 > x0 ? [x0, x0 + (x1 - x0) / 2, x1] : [x0];

  return (
    <figure>
      {series.length > 1 && (
        <ul className="chart-legend" aria-hidden="true">
          {series.map((s, i) => (
            <li key={s.label}>
              <i style={{ background: s.color ?? SERIES_COLORS[i % SERIES_COLORS.length] }} />
              {s.label}
            </li>
          ))}
        </ul>
      )}
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-labelledby={`${id}-t`}>
        <title id={`${id}-t`}>{ariaLabel}</title>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} className="gridline" />
            <text x={L - 6} y={Y(t) + 4} textAnchor="end">
              {yFormat(t)}
            </text>
          </g>
        ))}
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} className="axis" />
        {xt.map((x, i) => (
          <text key={i} x={X(x)} y={H - B + 18} textAnchor={i === 0 ? "start" : i === xt.length - 1 ? "end" : "middle"}>
            {xFormat(x)}
          </text>
        ))}
        {yLabel && (
          <text x={L - 40} y={12} className="label-strong" style={{ fontSize: 11 }}>
            {yLabel}
          </text>
        )}
        {series.map((s, i) => {
          const color = s.color ?? SERIES_COLORS[i % SERIES_COLORS.length];
          // split on gaps so a missing value is not drawn as a line
          const segs: string[] = [];
          let cur: string[] = [];
          for (const [x, y] of s.points) {
            if (y === null) {
              if (cur.length) segs.push(cur.join(" "));
              cur = [];
            } else cur.push(`${X(x).toFixed(1)},${Y(y).toFixed(1)}`);
          }
          if (cur.length) segs.push(cur.join(" "));
          return (
            <g key={s.label}>
              {segs.map((pts, j) =>
                pts.includes(" ") ? (
                  <polyline key={j} points={pts} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
                ) : (
                  <circle key={j} cx={pts.split(",")[0]} cy={pts.split(",")[1]} r={2.5} fill={color} />
                ),
              )}
            </g>
          );
        })}
      </svg>
      {xLabel && <figcaption className="chart-note">{xLabel}</figcaption>}
    </figure>
  );
}

export interface HBarRow {
  label: string;
  value: number | null;
  display?: string;
  color?: string;
  title?: string;
}

/** Horizontal bars, one per row; rows with no value show "–" and no bar. */
export function HBars({ rows, max, ariaLabel }: { rows: HBarRow[]; max?: number; ariaLabel: string }) {
  const m = max ?? Math.max(1, ...rows.map((r) => r.value ?? 0));
  return (
    <div role="list" aria-label={ariaLabel}>
      {rows.map((r, i) => (
        <div key={`${r.label}-${i}`} className="hbar" role="listitem" title={r.title}>
          <span className="hbar-label">{r.label}</span>
          <span className="hbar-track" aria-hidden="true">
            {r.value !== null && <i style={{ width: `${Math.min(100, (100 * r.value) / m)}%`, background: r.color ?? SERIES_COLORS[0] }} />}
          </span>
          <span className="hbar-val">{r.display ?? (r.value === null ? "–" : r.value)}</span>
        </div>
      ))}
    </div>
  );
}

/** Seconds-ago axis label for in-session history. */
export const sinceLabel = (now: number) => (ms: number) => {
  const s = Math.round((now - ms) / 1000);
  return s <= 1 ? "now" : s < 60 ? `-${s}s` : `-${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}`;
};
