import type { Approach, EquiEvent } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// Authentication (backend/app/security.py). The dashboard asks for a key, exchanges it for a short-lived token at
// POST /api/auth/login and keeps only the token (and its expiry) for this browser tab's session. The backend stays
// the authority: every write is checked there, whatever the UI shows.
// NEXT_PUBLIC_API_KEY still works for a local demo, but it is built into the page: never use it on the Internet.
const BUILD_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const TOKEN_KEY = "equiflow_token";
const ROLE_KEY = "equiflow_role";
const EXP_KEY = "equiflow_token_exp";

export type Role = "operator" | "viewer";

/** Fired on window when the backend rejects our token (401) or the token's lifetime has run out. */
export const SESSION_EXPIRED_EVENT = "equiflow:session-expired";
/** Fired on window after a successful sign-in or sign-out, so the live streams reconnect with the new token. */
export const SESSION_CHANGED_EVENT = "equiflow:session-changed";

const ss = () => (typeof window === "undefined" ? null : window.sessionStorage);

export function getToken(): string {
  const s = ss();
  if (!s) return "";
  const exp = Number(s.getItem(EXP_KEY) ?? 0);
  if (exp && Date.now() >= exp) return ""; // expired: treat as signed out (the session hook clears it)
  return s.getItem(TOKEN_KEY) ?? "";
}

/** "operator" | "viewer" while signed in, "" otherwise. */
export function getRole(): Role | "" {
  const r = getToken() ? ss()?.getItem(ROLE_KEY) ?? "" : "";
  return r === "operator" || r === "viewer" ? r : "";
}

/** Unix ms when the current token expires, or null. */
export function getTokenExpiry(): number | null {
  const v = Number(ss()?.getItem(EXP_KEY) ?? 0);
  return v > 0 ? v : null;
}

/** True when this tab holds a token whose lifetime has run out (so the UI can say "session expired"). */
export function tokenExpired(): boolean {
  const s = ss();
  const exp = Number(s?.getItem(EXP_KEY) ?? 0);
  return !!s?.getItem(TOKEN_KEY) && exp > 0 && Date.now() >= exp;
}

export function clearToken() {
  const s = ss();
  if (!s) return;
  s.removeItem(TOKEN_KEY);
  s.removeItem(ROLE_KEY);
  s.removeItem(EXP_KEY);
}

export function signOut() {
  clearToken();
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
}

export async function login(key: string): Promise<{ role: Role | ""; expires_in: number; auth?: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
  } catch {
    throw new Error(`Cannot reach the backend at ${API_URL}.`);
  }
  if (res.status === 429) throw new Error("Too many failed attempts. Wait a minute and try again.");
  if (res.status === 401) throw new Error("That key was not accepted.");
  if (!res.ok) throw new Error(`Sign-in failed (HTTP ${res.status}).`);
  const data = await res.json();
  const s = ss();
  if (data.token && s) {
    s.setItem(TOKEN_KEY, data.token);
    s.setItem(ROLE_KEY, data.role ?? "");
    if (data.expires_in > 0) s.setItem(EXP_KEY, String(Date.now() + data.expires_in * 1000));
    else s.removeItem(EXP_KEY);
  }
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
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

/** An HTTP error from the backend, with the status code and the backend's own explanation (FastAPI `detail`). */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function explain(status: number, detail: string): string {
  if (status === 401) return "Not signed in, or the session has expired. Sign in again.";
  if (status === 403) return "This action needs the operator role.";
  if (status === 429) return detail || "Too many requests. Wait a moment and try again.";
  return detail || `Request failed (HTTP ${status}).`;
}

/** The one place the dashboard talks HTTP to the backend. */
export async function request<T = unknown>(method: "GET" | "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: apiHeaders(body !== undefined),
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}.`);
  }
  const text = await res.text();
  if (!res.ok) {
    let detail = text;
    try {
      const d = JSON.parse(text).detail;
      detail = typeof d === "string" ? d : JSON.stringify(d);
    } catch {}
    if (res.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    throw new ApiError(res.status, explain(res.status, detail));
  }
  return (text ? JSON.parse(text) : null) as T;
}

/* ------------------------------------------------------------------ read endpoints */
export interface Health {
  status: string;
  mode: "live" | "sim";
  mode_reason: string;
  time: number;
}
export interface WhoAmI {
  auth: "enabled" | "disabled";
  protect_reads: boolean;
  public: boolean;
}
export interface AppConfigInfo {
  mode: "live" | "sim";
  controller: string;
  approaches: Approach[];
  intersections: { id: string; name: string; lat: number | null; lng: number | null }[];
}

export const getHealth = () => request<Health>("GET", "/api/health");
export const getWhoAmI = () => request<WhoAmI>("GET", "/api/auth/whoami");
export const getConfig = () => request<AppConfigInfo>("GET", "/api/config");
export const getEvents = (limit = 200) => request<EquiEvent[]>("GET", `/api/events?limit=${limit}`);

/* ------------------------------------------------------------------ operator commands */
export const requestPriority = (intersectionId: string, approach: Approach, durationS = 20) =>
  request("POST", `/api/signals/${encodeURIComponent(intersectionId)}/preempt`, { approach, duration_s: durationS });

export const cancelPriority = (intersectionId: string, approach: Approach) =>
  request("DELETE", `/api/signals/${encodeURIComponent(intersectionId)}/preempt/${approach}`);

export const resetSignalOutput = (intersectionId: string) =>
  request<{ ok: boolean; message: string }>("POST", `/api/signals/${encodeURIComponent(intersectionId)}/output/reset`);
