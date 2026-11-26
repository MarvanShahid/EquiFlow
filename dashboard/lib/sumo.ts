"use client";

import { request } from "./api";
import { setSumoStatus, useLive } from "./live";
import type { LampColor, Mode } from "./types";

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

export type { Link } from "./live";

/** Live SUMO state from the shared connection in lib/live.ts (geometry once per run, frames at about 6 Hz). */
export function useSumo() {
  const sumo = useLive((s) => s.sumo);
  return { geometry: sumo.geometry, frame: sumo.frame, status: sumo.status, setStatus: setSumoStatus, link: sumo.link, events: sumo.events };
}

const call = (method: "GET" | "POST", path: string, body?: unknown) => request(method, `/api/sumo${path}`, body);

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
  trips?: number | null;
  updates?: number | null;
  loss?: number | null;
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
