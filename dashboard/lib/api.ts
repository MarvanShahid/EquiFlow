import type { Approach } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws") + "/ws";

export const videoUrl = (intersectionId: string, approach: Approach) =>
  `${API_URL}/api/video/${encodeURIComponent(intersectionId)}/${approach}`;

async function send(method: "POST" | "DELETE", path: string, body?: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const requestPriority = (intersectionId: string, approach: Approach, durationS = 20) =>
  send("POST", `/api/signals/${encodeURIComponent(intersectionId)}/preempt`, { approach, duration_s: durationS });

export const cancelPriority = (intersectionId: string, approach: Approach) =>
  send("DELETE", `/api/signals/${encodeURIComponent(intersectionId)}/preempt/${approach}`);
