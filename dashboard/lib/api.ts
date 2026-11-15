import type { Approach } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws") + "/ws";
// Only needed when the backend has server.api_key set (see backend/app/security.py)
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export function apiHeaders(json: boolean): Record<string, string> | undefined {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return Object.keys(h).length ? h : undefined;
}

export const videoUrl = (intersectionId: string, approach: Approach) =>
  `${API_URL}/api/video/${encodeURIComponent(intersectionId)}/${approach}`;

async function send(method: "POST" | "DELETE", path: string, body?: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: apiHeaders(!!body),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const requestPriority = (intersectionId: string, approach: Approach, durationS = 20) =>
  send("POST", `/api/signals/${encodeURIComponent(intersectionId)}/preempt`, { approach, duration_s: durationS });

export const cancelPriority = (intersectionId: string, approach: Approach) =>
  send("DELETE", `/api/signals/${encodeURIComponent(intersectionId)}/preempt/${approach}`);
