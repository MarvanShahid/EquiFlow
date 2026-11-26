"use client";

/* One shared connection layer for the whole dashboard.

   Every page reads the same state, so the app opens exactly one /ws (camera-junction runtime: snapshots at 2 Hz +
   events), one /ws/sumo (simulation geometry + frames at about 6 Hz), one /api/health poll and one
   /api/sumo/status poll, whatever pages are mounted. Pages subscribe with useLive(selector) and only re-render
   when the slice they select changes.

   It also keeps a short in-memory history of the values it has received (since this tab opened), which the trend
   charts use. Nothing here is invented: if the backend sends nothing, the history stays empty. */

import { useSyncExternalStore } from "react";
import { API_URL, apiHeaders, getEvents, getHealth, wsUrl, withToken, type Health } from "./api";
import type { Frame, Geometry, SumoEvent, SumoStatus } from "./sumo";
import type { Approach, EquiEvent, Snapshot } from "./types";

export type Link = "connecting" | "live" | "offline";

export interface EqSample {
  wall: number; // unix ms
  total: number;
  vehicles: Record<string, Record<string, number>>; // intersection -> approach -> vehicles
  queues: Record<string, Record<string, number | null>>; // intersection -> approach -> queued vehicles (null = no zone)
  waiting: Record<string, Record<string, number>>;
  lanes: Record<string, { queued: number; queue_m: number | null; vehicles: number }>; // "iid/approach/lane"
}
export interface SumoSample {
  wall: number;
  t: number; // simulation seconds
  run: number;
  in_network: number;
  halting: number;
  arrived: number;
  car_wait: number | null;
  approach_vehicles: Record<string, Record<string, number>>; // tls -> approach -> vehicles
}

export interface LiveState {
  eq: { snapshot: Snapshot | null; link: Link; receivedAt: number; events: EquiEvent[]; eventsLoaded: boolean };
  sumo: { geometry: Geometry | null; frame: Frame | null; status: SumoStatus | null; link: Link; events: SumoEvent[] };
  health: { data: Health | null; ok: boolean | null; checkedAt: number; error: string | null };
  history: { eq: EqSample[]; sumo: SumoSample[] };
}

const MAX_EVENTS = 500; // simulation events share the bus, so keep enough for the junction too
const MAX_SAMPLES = 900;

let state: LiveState = {
  eq: { snapshot: null, link: "connecting", receivedAt: 0, events: [], eventsLoaded: false },
  sumo: { geometry: null, frame: null, status: null, link: "connecting", events: [] },
  health: { data: null, ok: null, checkedAt: 0, error: null },
  history: { eq: [], sumo: [] },
};
const listeners = new Set<() => void>();
let scheduled = false;

function set(patch: (s: LiveState) => LiveState) {
  state = patch(state);
  // coalesce bursts (a snapshot plus several events in the same tick) into one notification
  if (!scheduled) {
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      listeners.forEach((l) => l());
    });
  }
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useLive<T>(selector: (s: LiveState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(state),
    () => selector(state),
  );
}
export const getLiveState = () => state;

/* ------------------------------------------------------------------ connections */
interface Conn {
  stop: () => void;
}
let conns: Conn[] = [];
let started = false;

function socket(url: () => string, onMsg: (msg: { type: string; data: unknown }) => void, onLink: (l: Link) => void): Conn {
  let ws: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let closed = false;
  let attempt = 0;
  const connect = () => {
    onLink("connecting");
    try {
      ws = new WebSocket(url());
    } catch {
      onLink("offline");
      timer = setTimeout(connect, 4000);
      return;
    }
    ws.onopen = () => {
      attempt = 0;
      onLink("live");
    };
    ws.onmessage = (m) => {
      try {
        onMsg(JSON.parse(m.data));
      } catch {
        /* a malformed message is dropped, the stream continues */
      }
    };
    ws.onclose = () => {
      if (closed) return;
      onLink("offline");
      timer = setTimeout(connect, Math.min(8000, 1000 * 2 ** attempt++));
    };
    ws.onerror = () => ws?.close();
  };
  connect();
  return {
    stop: () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    },
  };
}

/** Polls `fn` every `ms`. Always runs once at start; while the tab is hidden it pauses, and it runs again as soon as
 *  the tab becomes visible, so a background tab does not keep hitting the backend. */
function poll(fn: () => Promise<void>, ms: number): Conn {
  let alive = true;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let first = true;
  const loop = async () => {
    if (!alive) return;
    clearTimeout(timer);
    if (first || document.visibilityState !== "hidden") await fn().catch(() => {});
    first = false;
    if (alive) timer = setTimeout(loop, ms);
  };
  const onVisible = () => document.visibilityState === "visible" && loop();
  document.addEventListener("visibilitychange", onVisible);
  loop();
  return {
    stop: () => {
      alive = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    },
  };
}

let lastEqSample = 0;
function sampleEq(snap: Snapshot) {
  const now = Date.now();
  if (now - lastEqSample < 2000) return;
  lastEqSample = now;
  const s: EqSample = { wall: now, total: snap.metrics.total_vehicles, vehicles: {}, queues: {}, waiting: {}, lanes: {} };
  for (const i of snap.intersections) {
    s.vehicles[i.id] = { ...i.vehicles };
    s.waiting[i.id] = { ...i.waiting_s };
    s.queues[i.id] = { ...(i.queues ?? {}) } as Record<Approach, number | null>;
    for (const [a, lanes] of Object.entries(i.lanes ?? {})) {
      for (const [lid, q] of Object.entries(lanes ?? {})) s.lanes[`${i.id}/${a}/${lid}`] = { ...q };
    }
  }
  state.history.eq = [...state.history.eq, s].slice(-MAX_SAMPLES);
}

let lastSumoSample = 0;
function sampleSumo(f: Frame) {
  const now = Date.now();
  if (now - lastSumoSample < 1000) return;
  lastSumoSample = now;
  const approach_vehicles: SumoSample["approach_vehicles"] = {};
  for (const j of f.junctions) approach_vehicles[j.id] = { ...j.vehicles };
  const s: SumoSample = {
    wall: now,
    t: f.t,
    run: f.run_id,
    in_network: f.metrics.in_network,
    halting: f.metrics.halting,
    arrived: f.metrics.arrived,
    car_wait: f.metrics.per_class?.car?.mean_waiting_s ?? null,
    approach_vehicles,
  };
  // a new run starts a new history
  const prev = state.history.sumo;
  const keep = prev.length && prev[prev.length - 1].run !== f.run_id ? [] : prev;
  state.history.sumo = [...keep, s].slice(-MAX_SAMPLES);
}

function mergeEvents<E extends { id: number; ts: number }>(prev: E[], incoming: E[]): E[] {
  const seen = new Set(prev.map((e) => e.id));
  const fresh = incoming.filter((e) => !seen.has(e.id));
  if (!fresh.length) return prev;
  return [...fresh, ...prev].sort((a, b) => b.ts - a.ts || b.id - a.id).slice(0, MAX_EVENTS);
}

function startAll() {
  // initial event history (newest first)
  getEvents(200)
    .then((list) =>
      set((s) => ({ ...s, eq: { ...s.eq, events: mergeEvents(s.eq.events, list), eventsLoaded: true } })),
    )
    .catch(() => set((s) => ({ ...s, eq: { ...s.eq, eventsLoaded: true } })));

  conns.push(
    socket(
      () => wsUrl("/ws"),
      (msg) => {
        if (msg.type === "snapshot") {
          const snap = msg.data as Snapshot;
          sampleEq(snap);
          set((s) => ({ ...s, eq: { ...s.eq, snapshot: snap, receivedAt: performance.now() }, history: { ...s.history } }));
        } else if (msg.type === "event") {
          const e = msg.data as EquiEvent;
          if (e.type === "ambulance_position") return;
          set((s) => ({ ...s, eq: { ...s.eq, events: mergeEvents(s.eq.events, [e]) } }));
        }
      },
      (link) => set((s) => ({ ...s, eq: { ...s.eq, link } })),
    ),
  );

  conns.push(
    socket(
      () => withToken(API_URL.replace(/^http/, "ws") + "/ws/sumo"),
      (msg) => {
        if (msg.type === "geometry") {
          set((s) => ({ ...s, sumo: { ...s.sumo, geometry: msg.data as Geometry, frame: null } }));
        } else if (msg.type === "frame") {
          const f = msg.data as Frame;
          if (state.sumo.geometry && f.run_id !== state.sumo.geometry.run_id) return;
          sampleSumo(f);
          set((s) => ({
            ...s,
            sumo: { ...s.sumo, frame: f, events: mergeEvents(s.sumo.events, f.events ?? []) },
            history: { ...s.history },
          }));
        } else if (msg.type === "status") {
          applyStatus(msg.data as SumoStatus);
        }
      },
      (link) => set((s) => ({ ...s, sumo: { ...s.sumo, link } })),
    ),
  );

  conns.push(
    poll(async () => {
      try {
        const h = await getHealth();
        set((s) => ({ ...s, health: { data: h, ok: h.status === "ok", checkedAt: Date.now(), error: null } }));
      } catch (e) {
        set((s) => ({ ...s, health: { ...s.health, ok: false, checkedAt: Date.now(), error: (e as Error).message } }));
      }
    }, 10_000),
  );

  // keep the SUMO status fresh (state changes such as "finished" or a new speed are not always streamed)
  conns.push(
    poll(async () => {
      const r = await fetch(`${API_URL}/api/sumo/status`, { headers: apiHeaders(false), cache: "no-store" });
      if (r.ok) {
        applyStatus((await r.json()) as SumoStatus);
      }
    }, 3000),
  );
}

/** Opens the shared connections (idempotent). */
export function startLive() {
  if (started || typeof window === "undefined") return;
  started = true;
  startAll();
}

/** Reconnects everything, e.g. after a sign-in so the sockets carry the new token. */
export function restartLive() {
  conns.forEach((c) => c.stop());
  conns = [];
  started = false;
  startLive();
}

/** A stopped simulation (idle) has no live view: drop its map and last frame so nothing stale is shown. */
function applyStatus(st: SumoStatus) {
  set((s) => ({
    ...s,
    sumo: st.state === "idle" ? { ...s.sumo, status: st, geometry: null, frame: null } : { ...s.sumo, status: st },
  }));
}

/** Lets a command response update the SUMO status immediately (instead of waiting for the next poll). */
export function setSumoStatus(st: SumoStatus) {
  applyStatus(st);
}
