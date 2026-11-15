import { VCOLOR, VSIZE, VTYPES, type Veh } from "@/lib/sumo";

export const LAMP_COLOR: Record<string, string> = {
  red: "#ef4b4b",
  yellow: "#f6a623",
  green: "#2fcf8f",
};
export const AMB_BLUE = "#4aa3ff";

/** Draw one vehicle with its front at (0,0) pointing along +x after the caller's transform. */
export function drawVehicle(
  ctx: CanvasRenderingContext2D,
  v: Veh,
  sx: number,
  sy: number,
  rot: number,
  scale: number,
  minPx: number,
  flash: boolean,
) {
  const type = VTYPES[v[4]] ?? "car";
  const [len, wid] = VSIZE[type];
  const L = Math.max(len * scale, minPx * 1.8);
  const W = Math.max(wid * scale, minPx);
  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(rot);
  if (type === "ambulance") {
    ctx.shadowColor = flash ? "#ff3b3b" : AMB_BLUE;
    ctx.shadowBlur = 12;
  }
  ctx.fillStyle = VCOLOR[type];
  ctx.fillRect(-L, -W / 2, L, W);
  ctx.shadowBlur = 0;
  if (type === "ambulance") {
    ctx.fillStyle = flash ? "#ff3b3b" : AMB_BLUE;
    ctx.fillRect(-L * 0.62, -W / 2, Math.max(2, L * 0.16), W);
    ctx.strokeStyle = "#ef4b4b";
    ctx.lineWidth = 1;
    ctx.strokeRect(-L, -W / 2, L, W);
  } else {
    // windscreen hint so the direction of travel reads at a glance
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.fillRect(-Math.min(L * 0.32, 6), -W / 2 + 0.6, Math.max(1, Math.min(L * 0.12, 2)), Math.max(0, W - 1.2));
  }
  ctx.restore();
}
