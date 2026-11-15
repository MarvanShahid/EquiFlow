"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { VTYPES, type Approach, type CamDet, type Geometry, type Veh } from "@/lib/sumo";
import type { LampColor } from "@/lib/types";
import { AMB_BLUE, LAMP_COLOR, drawVehicle } from "./draw";

/** Virtual camera on one approach: the view from the stop line looking up the approach, with the
 *  detector output drawn the same way the live pipeline draws it (green = vehicle, yellow = some
 *  ambulance votes, red = confirmed ambulance). */
export default function CameraView({
  geometry,
  approach,
  vehicles,
  dets,
  lamp,
  ambulance,
  range,
  m,
}: {
  geometry: Geometry;
  approach: Approach;
  vehicles: Map<string, Veh>;
  dets: CamDet[];
  lamp: LampColor;
  ambulance: boolean;
  range: number;
  m: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const h = (approach.heading * Math.PI) / 180;
  const f = useMemo(() => [Math.sin(h), Math.cos(h)] as const, [h]); // direction of travel
  const r = useMemo(() => [Math.cos(h), -Math.sin(h)] as const, [h]); // driver's right

  const draw = useCallback(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    const W = c.clientWidth;
    const H = c.clientHeight;
    if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) {
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
    }
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const s = (W * 0.9) / range;
    const [sx0, sy0] = approach.stop;
    const xStop = W * 0.95;
    const P = (x: number, y: number): [number, number] => {
      const dx = x - sx0;
      const dy = y - sy0;
      return [xStop + (dx * f[0] + dy * f[1]) * s, H / 2 + (dx * r[0] + dy * r[1]) * s];
    };

    ctx.fillStyle = "#11161a";
    ctx.fillRect(0, 0, W, H);
    // road
    ctx.lineCap = "butt";
    for (const l of geometry.lanes) {
      ctx.strokeStyle = l.internal ? "#3a444e" : "#343d46";
      ctx.lineWidth = Math.max(1, l.width * s * 0.92);
      ctx.beginPath();
      l.shape.forEach(([x, y], i) => {
        const [px, py] = P(x, y);
        if (i) ctx.lineTo(px, py);
        else ctx.moveTo(px, py);
      });
      ctx.stroke();
    }
    // stop line
    ctx.strokeStyle = LAMP_COLOR[lamp];
    ctx.lineWidth = 3;
    for (const lid of approach.lanes) {
      const l = geometry.lanes.find((x) => x.id === lid);
      if (!l) continue;
      const [px, py] = P(...l.shape[l.shape.length - 1]);
      ctx.beginPath();
      ctx.moveTo(px, py - (l.width * s) / 2);
      ctx.lineTo(px, py + (l.width * s) / 2);
      ctx.stroke();
    }
    // distance ticks
    ctx.fillStyle = "rgba(236,231,214,0.45)";
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    for (let d = 25; d < range; d += 25) {
      const x = xStop - d * s;
      ctx.fillRect(x, 2, 1, 5);
      ctx.fillText(`${d} m`, x, 17);
    }

    const flash = Math.floor(Date.now() / 300) % 2 === 0;
    // every vehicle in view (also the ones the camera is not tracking, e.g. leaving the junction)
    for (const v of vehicles.values()) {
      const [px, py] = P(v[1], v[2]);
      if (px < -30 || px > W + 30 || py < -30 || py > H + 30) continue;
      drawVehicle(ctx, v, px, py, ((v[3] - approach.heading) * Math.PI) / 180, s, 2, flash);
    }
    // detector boxes + labels
    ctx.font = "700 10px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    dets.slice(0, 14).forEach(([vid, ti, p, votes, confirmed]) => {
      const v = vehicles.get(vid);
      if (!v) return;
      const [px, py] = P(v[1], v[2]);
      const type = VTYPES[ti] ?? "car";
      const len = Math.max(4, (type === "bus" ? 12 : type === "truck" ? 9 : type === "motorcycle" ? 2.2 : 5) * s);
      const color = confirmed ? "#ef4b4b" : votes > 0 ? "#f0e019" : "#2fcf8f";
      const bx = px - len - 3;
      const by = py - Math.max(6, 2.5 * s);
      const bw = len + 6;
      const bh = Math.max(12, 5 * s);
      ctx.strokeStyle = color;
      ctx.lineWidth = confirmed ? 2 : 1.2;
      ctx.strokeRect(bx, by, bw, bh);
      const label = confirmed
        ? `AMBULANCE p${p.toFixed(2)}`
        : votes > 0
          ? `? p${p.toFixed(2)} ${votes}/${m}`
          : `${type} p${p.toFixed(2)}`;
      if (confirmed || votes > 0 || dets.length <= 8) {
        const tw = ctx.measureText(label).width + 6;
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        ctx.fillRect(bx, by - 13, tw, 13);
        ctx.fillStyle = color;
        ctx.fillText(label, bx + 3, by - 1);
      }
    });
    if (ambulance) {
      ctx.strokeStyle = AMB_BLUE;
      ctx.lineWidth = 4;
      ctx.strokeRect(2, 2, W - 4, H - 4);
    }
  }, [geometry, approach, vehicles, dets, lamp, ambulance, range, m, f, r]);

  useEffect(() => {
    draw();
    const id = setInterval(draw, 300);
    return () => clearInterval(id);
  }, [draw]);

  const amb = dets.filter((d) => d[4]).length;
  return (
    <figure className={`cam vcam${ambulance ? " cam-amb" : ""}`}>
      <canvas ref={canvas} aria-label={`Virtual camera on the ${approach.id} approach`} />
      <figcaption>
        <span className={`chip chip-${lamp}`} aria-label={`signal ${lamp}`} />
        <span className="cam-name">{approach.id}</span>
        <span className="cam-tag">{dets.length} tracked</span>
        {amb > 0 && <span className="cam-badge">Ambulance confirmed</span>}
      </figcaption>
    </figure>
  );
}
