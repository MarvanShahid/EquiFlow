"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL, apiHeaders, withToken } from "./api";
import type { LampColor, Mode } from "./types";

export const SUMO_WS_URL = API_URL.replace(/^http/, "ws") + "/ws/sumo";
export const VTYPES = ["car", "motorcycle", "bus", "truck", "ambulance"] as const;
export type VType = (typeof VTYPES)[number];
/** Colours match the SUMO GUI colours set in sumo/build_islamabad.py. */
export const VCOLOR: Record<VType, string> = {
  car: "#f0c419",
  motorcycle: "#22c7f2",
  bus: "#2fcf8f",
  truck: "#9aa3ab",
  ambulance: "#ffffff",
};
export const VSIZE: Record<VType, [number, number]> = {
  car: [4.5, 1.8],
  motorcycle: [2.2, 0.8],
  bus: [12, 2.5],
  truck: [9, 2.5],
  ambulance: [5.8, 2.1],
};

export type Controller = "equiflow" | "fixed" | "actuated";
export type Base = "adaptive" | "marl" | "fixed_time";
export type Scenario = "low" | "medium" | "high" | "asymmetric";

export interface NetworkInfo {
  id: string;
  title: string;
  description: string;
  scenarios: Scenario[];
  actuated: boolean;
}

export interface SumoStatus {
  available: boolean;
  reason: string;
  state: "idle" | "starting" | "running" | "paused" | "finished" | "error";
  error: string | null;
  run: null | { network: string; scenario: Scenario; controller: Controller; seed: number; speed: number; title: string; base?: Base };
  run_id: number;
  sumo_home: string | null;
}

export interface Approach {
  id: string;
  edge: string;
  from_deg: number;
  heading: number;
  links: number[];
  lanes: string[];
  length: number;
  stop: [number, number];
}

export interface TlsGeo {
  id: string;
  x: number;
  y: number;
  n_links: number;
  approaches: Approach[];
}

export interface Geometry {
  run_id: number;
  boundary: [number, number, number, number];
  lanes: { id: string; edge: string; internal: boolean; width: number; shape: [number, number][] }[];
  junctions: { id: string; type: string; shape: [number, number][]; x: number; y: number }[];
  tls: TlsGeo[];
}

/** [vehicle id, vtype index, p(ambulance) this frame, votes in last M frames, confirmed, metres to stop line] */
export type CamDet = [string, number, number, number, boolean, number];
/** [id, x, y, angle, vtype index, speed] */
export type Veh = [string, number, number, number, number, number];

export interface Decision {
  t: number;
  approach: string;
  source: string;
  green_s?: number;
  vehicles?: number;
  waited_s?: number;
}

export interface JunctionSnap {
  id: string;
  controller: string;
  mode: Mode;
  stage: "GREEN" | "YELLOW" | "ALL_RED";
  current: string | null;
  active_preempt: string | null;
  stage_remaining_s: number | null;
  lamps: Record<string, LampColor>;
  ambulance: Record<string, boolean>;
  vehicles: Record<string, number>;
  waiting_s: Record<string, number>;
  recovery_plan: string[];
  stats: {
    preemptions: number;
    total_preempt_s: number;
    latency_last_s: number | null;
    latency_avg_s: number | null;
    latency_max_s: number | null;
  };
  cameras: Record<string, CamDet[]>;
  decisions: Decision[];
  /** EquiFlow only: the signal phases the controller switches between, and the approaches each one serves */
  phases: { id: string; approaches: string[] }[];
  signal_state: string;
}

export interface ClassStats {
  completed: number;
  mean_travel_time_s: number | null;
  mean_waiting_s: number | null;
  mean_time_loss_s: number | null;
}

export interface SumoEvent {
  id: number;
  ts: number;
  type: string;
  tls: string | null;
  sim_time: number;
  approach?: string;
  [key: string]: unknown;
}

export interface Frame {
  run_id: number;
  t: number;
  state: SumoStatus["state"];
  vehicles: Veh[];
  junctions: JunctionSnap[];
  metrics: {
    in_network: number;
    halting: number;
    arrived: number;
    preemptions: number;
    latency_avg_s: number | null;
    latency_max_s: number | null;
    ambulances_in_network: number;
    per_class: Record<VType, ClassStats>;
  };
  events: SumoEvent[];
}

export type Link = "connecting" | "live" | "offline";

/** Live SUMO state: one WebSocket (geometry once per run, frames at about 6 Hz), reconnecting on its own. */
export function useSumo() {
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [status, setStatus] = useState<SumoStatus | null>(null);
  const [link, setLink] = useState<Link>("connecting");
  const runRef = useRef(-1);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    let attempt = 0;
    const connect = () => {
      setLink("connecting");
      ws = new WebSocket(withToken(SUMO_WS_URL));
      ws.onopen = () => {
        attempt = 0;
        setLink("live");
      };
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.type === "geometry") {
          runRef.current = msg.data.run_id;
          setGeometry(msg.data as Geometry);
          setFrame(null);
        } else if (msg.type === "frame") {
          if (msg.data.run_id === runRef.current) setFrame(msg.data as Frame);
        } else if (msg.type === "status") {
          setStatus(msg.data as SumoStatus);
        }
      };
      ws.onclose = () => {
        if (closed) return;
        setLink("offline");
        timer = setTimeout(connect, Math.min(8000, 1000 * 2 ** attempt++));
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  // keep the status fresh (state changes such as "finished" or a new speed)
  useEffect(() => {
    let alive = true;
    const poll = () =>
      fetch(`${API_URL}/api/sumo/status`, { headers: apiHeaders(false) })
        .then((r) => (r.ok ? r.json() : null))
        .then((s) => alive && s && setStatus(s))
        .catch(() => {});
    poll();
    const id = setInterval(poll, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return { geometry, frame, status, setStatus, link };
}

async function call(method: "GET" | "POST", path: string, body?: unknown) {
  const res = await fetch(`${API_URL}/api/sumo${path}`, {
    method,
    headers: apiHeaders(!!body),
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) {
    let detail = text;
    try {
      detail = JSON.parse(text).detail ?? text;
    } catch {}
    throw new Error(String(detail));
  }
  return text ? JSON.parse(text) : null;
}

export const sumoApi = {
  networks: () => call("GET", "/networks") as Promise<{ networks: NetworkInfo[]; status: SumoStatus }>,
  results: () => call("GET", "/results") as Promise<ResultRow[]>,
  robustness: () => call("GET", "/robustness") as Promise<RobustRow[]>,
  training: () => call("GET", "/training") as Promise<TrainRow[]>,
  start: (b: { network: string; scenario: Scenario; controller: Controller; base?: Base; speed?: number }) =>
    call("POST", "/start", b) as Promise<SumoStatus>,
  stop: () => call("POST", "/stop") as Promise<SumoStatus>,
  speed: (speed: number) => call("POST", "/speed", { speed }),
  pause: (paused: boolean) => call("POST", "/pause", { paused }),
  ambulance: (tls?: string, approach?: string) => call("POST", "/ambulance", { tls, approach }),
  preempt: (tls: string, approach: string, duration_s = 20) => call("POST", "/preempt", { tls, approach, duration_s }),
};

export interface RobustRow {
  network: string;
  scenario: string;
  seed: string;
  miss_prob: number;
  fp_prob: number;
  ambulance_wait_s: number | null;
  car_wait_s: number | null;
  priority_runs: number | null;
  false_confirmations: number | null;
  detection_to_green_s: number | null;
}

export interface TrainRow {
  episode: number;
  network: string;
  scenario: string;
  epsilon: number;
  mean_wait_s: number | null;
  ambulance_wait_s: number | null;
}

export interface ResultRow {
  intersection: string;
  controller: string;
  scenario: string;
  seed: string;
  vehicle_type: VType;
  completed: number | null;
  mean_travel_time_s: number | null;
  mean_waiting_s: number | null;
  mean_time_loss_s: number | null;
  mean_stopped_vehicles: number | null;
}

export const fmtTime = (s: number) => {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
};
