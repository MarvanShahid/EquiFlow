"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { Frame, Geometry } from "@/lib/sumo";
import { AMB_BLUE, LAMP_COLOR, drawVehicle } from "./draw";

const MODE_RING: Record<string, string> = { NORMAL: "#a7aeb4", PREEMPT: AMB_BLUE, RECOVERY: "#f0c419" };

/** Top-down live view of the whole SUMO network. Scroll to zoom, drag to pan, double-click to reset,
 *  click a junction to inspect it. */
export default function NetworkCanvas({
  geometry,
  frame,
  selected,
  onSelect,
  cameraRange,
}: {
  geometry: Geometry;
  frame: Frame | null;
  selected: string | null;
  onSelect: (id: string) => void;
  cameraRange: number;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const view = useRef({ k: 1, dx: 0, dy: 0 });
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);

  const laneById = useMemo(() => new Map(geometry.lanes.map((l) => [l.id, l])), [geometry]);
  const snapById = useMemo(() => new Map((frame?.junctions ?? []).map((j) => [j.id, j])), [frame]);

  // world -> screen
  const transform = useCallback(() => {
    const c = canvas.current!;
    const W = c.clientWidth;
    const H = c.clientHeight;
    const [x0, y0, x1, y1] = geometry.boundary;
    const pad = 44;
    const base = Math.min((W - 2 * pad) / Math.max(1, x1 - x0), (H - 2 * pad) / Math.max(1, y1 - y0));
    const s = base * view.current.k;
    const ox = (W - (x1 - x0) * s) / 2 + view.current.dx;
    const oy = (H - (y1 - y0) * s) / 2 + view.current.dy;
    return { s, X: (x: number) => (x - x0) * s + ox, Y: (y: number) => (y1 - y) * s + oy, W, H };
  }, [geometry]);

  const draw = useCallback(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    const cw = c.clientWidth;
    const ch = c.clientHeight;
    if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) {
      c.width = Math.round(cw * dpr);
      c.height = Math.round(ch * dpr);
    }
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const { s, X, Y } = transform();
    ctx.fillStyle = "#171c21";
    ctx.fillRect(0, 0, cw, ch);

    // junction areas
    ctx.fillStyle = "#343d46";
    for (const j of geometry.junctions) {
      if (j.shape.length < 3) continue;
      ctx.beginPath();
      j.shape.forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y))));
      ctx.closePath();
      ctx.fill();
    }
    // lanes (drawn slightly narrower than their width so lane boundaries show)
    ctx.lineCap = "butt";
    ctx.lineJoin = "round";
    for (const l of geometry.lanes) {
      ctx.strokeStyle = l.internal ? "#3a444e" : "#343d46";
      ctx.lineWidth = Math.max(1.2, l.width * s * (l.internal ? 1 : 0.9));
      ctx.beginPath();
      l.shape.forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y))));
      ctx.stroke();
    }

    // camera zones of the selected junction
    const sel = geometry.tls.find((t) => t.id === selected);
    if (sel) {
      for (const a of sel.approaches) {
        const snap = snapById.get(sel.id);
        const amb = snap?.ambulance[a.id];
        for (const lid of a.lanes) {
          const l = laneById.get(lid);
          if (!l) continue;
          ctx.strokeStyle = amb ? "rgba(74,163,255,0.35)" : "rgba(240,196,25,0.13)";
          ctx.lineWidth = Math.max(3, l.width * s * 1.15);
          ctx.beginPath();
          // walk back from the stop line along the lane shape for `cameraRange` metres
          let left = cameraRange;
          const pts = l.shape;
          let [px, py] = pts[pts.length - 1];
          ctx.moveTo(X(px), Y(py));
          for (let i = pts.length - 2; i >= 0 && left > 0; i--) {
            const [qx, qy] = pts[i];
            const d = Math.hypot(qx - px, qy - py);
            const f = Math.min(1, left / Math.max(d, 1e-6));
            const nx = px + (qx - px) * f;
            const ny = py + (qy - py) * f;
            ctx.lineTo(X(nx), Y(ny));
            left -= d;
            px = qx;
            py = qy;
          }
          ctx.stroke();
        }
      }
    }

    // stop bars coloured by each approach's signal
    for (const t of geometry.tls) {
      const snap = snapById.get(t.id);
      for (const a of t.approaches) {
        const lamp = snap?.lamps[a.id] ?? "red";
        const amb = snap?.ambulance[a.id];
        for (const lid of a.lanes) {
          const l = laneById.get(lid);
          if (!l || l.shape.length < 2) continue;
          const [x1, y1] = l.shape[l.shape.length - 2];
          const [x2, y2] = l.shape[l.shape.length - 1];
          const d = Math.hypot(x2 - x1, y2 - y1) || 1;
          const nx = -(y2 - y1) / d;
          const ny = (x2 - x1) / d;
          const hw = l.width / 2;
          ctx.strokeStyle = LAMP_COLOR[lamp] ?? "#ef4b4b";
          ctx.lineWidth = Math.max(2.5, 1.4 * s);
          ctx.beginPath();
          ctx.moveTo(X(x2 + nx * hw), Y(y2 + ny * hw));
          ctx.lineTo(X(x2 - nx * hw), Y(y2 - ny * hw));
          ctx.stroke();
          if (amb) {
            ctx.strokeStyle = AMB_BLUE;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(X(x2), Y(y2), Math.max(6, 3 * s), 0, Math.PI * 2);
            ctx.stroke();
          }
        }
      }
    }

    // vehicles
    const flash = Math.floor(Date.now() / 300) % 2 === 0;
    for (const v of frame?.vehicles ?? []) {
      drawVehicle(ctx, v, X(v[1]), Y(v[2]), ((v[3] - 90) * Math.PI) / 180, s, 3, flash);
    }

    // junction badges
    ctx.font = "700 12px var(--font-overpass), system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const t of geometry.tls) {
      const snap = snapById.get(t.id);
      const mode = snap?.mode ?? "NORMAL";
      const cx = X(t.x);
      const cy = Y(t.y);
      const isSel = t.id === selected;
      ctx.lineWidth = isSel ? 3 : 2;
      ctx.strokeStyle = MODE_RING[mode];
      ctx.setLineDash(isSel ? [] : [4, 4]);
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(18, 16 * s), 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      const label = t.id;
      const w = ctx.measureText(label).width + 12;
      ctx.fillStyle = isSel ? "#f0c419" : "rgba(17,22,26,0.85)";
      ctx.fillRect(cx - w / 2, cy - Math.max(18, 16 * s) - 22, w, 18);
      ctx.fillStyle = isSel ? "#11161a" : "#ece7d6";
      ctx.fillText(label, cx, cy - Math.max(18, 16 * s) - 13);
    }
  }, [geometry, frame, selected, snapById, laneById, transform, cameraRange]);

  useEffect(() => {
    draw();
  }, [draw]);

  // keep the ambulance light flashing and redraw on resize
  useEffect(() => {
    const id = setInterval(draw, 300);
    const ro = new ResizeObserver(() => draw());
    if (wrap.current) ro.observe(wrap.current);
    return () => {
      clearInterval(id);
      ro.disconnect();
    };
  }, [draw]);

  // new network: reset the view
  useEffect(() => {
    view.current = { k: 1, dx: 0, dy: 0 };
  }, [geometry.run_id]);

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = c.getBoundingClientRect();
      const mx = e.clientX - r.left - r.width / 2;
      const my = e.clientY - r.top - r.height / 2;
      const v = view.current;
      const f = Math.exp(-e.deltaY * 0.0015);
      const k = Math.min(30, Math.max(0.5, v.k * f));
      const g = k / v.k;
      v.dx = mx - (mx - v.dx) * g;
      v.dy = my - (my - v.dy) * g;
      v.k = k;
      draw();
    };
    c.addEventListener("wheel", onWheel, { passive: false });
    return () => c.removeEventListener("wheel", onWheel);
  }, [draw]);

  const onDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, moved: false };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const mx = e.clientX - d.x;
    const my = e.clientY - d.y;
    if (Math.abs(mx) + Math.abs(my) > 3) d.moved = true;
    if (d.moved) {
      view.current.dx += mx;
      view.current.dy += my;
      d.x = e.clientX;
      d.y = e.clientY;
      draw();
    }
  };
  const onUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved) return;
    const r = canvas.current!.getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    const { X, Y } = transform();
    let best: string | null = null;
    let bestD = 48;
    for (const t of geometry.tls) {
      const dd = Math.hypot(X(t.x) - px, Y(t.y) - py);
      if (dd < bestD) {
        bestD = dd;
        best = t.id;
      }
    }
    if (best) onSelect(best);
  };

  return (
    <div ref={wrap} className="netwrap">
      <canvas
        ref={canvas}
        className="netcanvas"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onDoubleClick={() => {
          view.current = { k: 1, dx: 0, dy: 0 };
          draw();
        }}
        role="img"
        aria-label="Live map of the simulated road network. Click a junction to inspect it."
      />
    </div>
  );
}
