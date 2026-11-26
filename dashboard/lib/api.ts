import type { Approach } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// Authentication (backend/app/security.py). The dashboard asks for a key once (LoginGate), exchanges it for a
// short-lived token at POST /api/auth/login and keeps only the token, for this browser tab's session.
// NEXT_PUBLIC_API_KEY still works for a local demo, but it is built into the page: never use it on the Internet.
const BUILD_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const TOKEN_KEY = "equiflow_token";
const ROLE_KEY = "equiflow_role";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(TOKEN_KEY) ?? "";
}

/** "operator" | "viewer" while signed in, "" otherwise. */
export function getRole(): string {
  if (typeof window === "undefined") return "";
  return getToken() ? window.sessionStorage.getItem(ROLE_KEY) ?? "" : "";
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(ROLE_KEY);
}

export function signOut() {
  clearToken();
  window.location.reload();
}

export async function login(key: string): Promise<{ role: string }> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  if (res.status === 429) throw new Error("Too many attempts. Wait a minute and try again.");
  if (!res.ok) throw new Error("Wrong key.");
  const data = await res.json();
  if (data.token) {
    window.sessionStorage.setItem(TOKEN_KEY, data.token);
    window.sessionStorage.setItem(ROLE_KEY, data.role ?? "");
  }
  return data;
}

export function apiHeaders(json: boolean): Record<string, string> | undefined {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const token = getToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  else if (BUILD_KEY) h["X-API-Key"] = BUILD_KEY;
  return Object.keys(h).length ? h : undefined;
}

/** WebSocket and <img> URLs cannot carry headers: the short-lived token goes in the query (never the key). */
export function withToken(url: string): string {
  const token = getToken();
  return token ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}` : url;
}

export const wsUrl = (path = "/ws") => withToken(API_URL.replace(/^http/, "ws") + path);

export const videoUrl = (intersectionId: string, approach: Approach) =>
  withToken(`${API_URL}/api/video/${encodeURIComponent(intersectionId)}/${approach}`);

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

export const resetSignalOutput = (intersectionId: string) =>
  send("POST", `/api/signals/${encodeURIComponent(intersectionId)}/output/reset`);
