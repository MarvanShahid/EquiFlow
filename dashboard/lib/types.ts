export type Approach = "North" | "East" | "South" | "West";
export const APPROACHES: Approach[] = ["North", "East", "South", "West"];
export type LampColor = "red" | "yellow" | "green";
export type Mode = "NORMAL" | "PREEMPT" | "RECOVERY";

export interface SourceInfo {
  kind: string;
  ok: boolean;
  error: string | null;
  fps: number;
}

export interface Signal {
  id: string;
  name: string;
  lat: number | null;
  lng: number | null;
  controller: string;
  mode: Mode;
  stage: "GREEN" | "YELLOW" | "ALL_RED";
  current: Approach | null;
  active_preempt: Approach | null;
  stage_elapsed_s: number;
  stage_remaining_s: number | null;
  lamps: Record<Approach, LampColor>;
  ambulance: Record<Approach, boolean>;
  vehicles: Record<Approach, number>;
  waiting_s: Record<Approach, number>;
  recovery_plan: Approach[];
  detections_total: number;
  stats: {
    preemptions: number;
    total_preempt_s: number;
    latency_last_s: number | null;
    latency_avg_s: number | null;
    latency_max_s: number | null;
  };
  sources: Record<Approach, SourceInfo>;
}

export interface Metrics {
  uptime_s: number;
  mode: "live" | "sim";
  mode_reason: string;
  controller: string;
  ambulance_detections: number;
  preemptions: number;
  active_preemptions: number;
  preempt_latency_avg_s: number | null;
  preempt_latency_last_s: number | null;
  preempt_latency_max_s: number | null;
  total_vehicles: number;
  max_wait_s: number;
}

export interface AmbulanceRec {
  id: string;
  intersection_id: string;
  approach: Approach;
  track_id: number;
  confidence: number;
  first_seen: number;
  last_seen: number;
  cx: number;
  cy: number;
  status: "active" | "cleared";
}

export interface Snapshot {
  ts: number;
  mode: "live" | "sim";
  intersections: Signal[];
  ambulances: AmbulanceRec[];
  metrics: Metrics;
}

export interface EquiEvent {
  id: number;
  ts: number;
  type: string;
  intersection_id?: string;
  approach?: Approach;
  [key: string]: unknown;
}
