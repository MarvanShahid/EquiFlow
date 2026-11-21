"""Configuration, loaded from YAML. Set EQUIFLOW_CONFIG to use another file
(e.g. config.live.yaml for real cameras + your two models)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent.parent


class TimingCfg(BaseModel):
    green_s: float = 15
    yellow_s: float = 3
    all_red_s: float = 2


class PreemptCfg(BaseModel):
    min_green_s: float = 3
    clear_hold_s: float = 4
    max_preempt_s: float = 60
    recovery_factor: float = 0.5
    recovery_max_s: float = 15
    recovery: bool = True
    recovery_queue_weight: float = 0.5
    recovery_mode: str = "queue"
    recovery_headway_s: float = 2.0
    gap_out: bool = True
    gap_out_min_green_s: float = 5
    stale_s: float = 2.0


class VisionCfg(BaseModel):
    # Model 1: COCO vehicle detector + ByteTrack. Model 2: your ambulance classifier.
    det_weights: str = "yolo26s.pt"
    cls_weights: str = ""
    device: int | str = 0
    imgsz: int = 1280
    det_conf: float = 0.35
    vehicle_classes: list[int] = [2, 3, 5, 7]   # COCO: car, motorcycle, bus, truck
    cls_imgsz: int = 96
    # voting rule (same as your tracking script)
    th_frame: float = 0.6
    m: int = 8
    k: int = 5
    mean_min: float = 0.65
    release: int = 1
    min_move: float = 0.0          # fraction of frame width; raise to ignore stationary objects
    pad: float = 0.12
    min_side: int = 20
    process_every: int = 1         # run models on every Nth frame (raise if the GPU can't keep up)
    queue_max_move: float = 0.004  # a vehicle in the zone that moved less than this (fraction of frame width)
                                   # per frame over the last queue_frames frames counts as queued
    queue_frames: int = 5
    stream_width: int = 640
    jpeg_quality: int = 70


class SimCfg(BaseModel):
    auto_ambulance: bool = True
    min_gap_s: float = 35
    max_gap_s: float = 80
    ambulance_s: float = 9


class MqttCfg(BaseModel):
    enabled: bool = False
    host: str = "localhost"
    port: int = 1883
    username: str | None = None
    password: str | None = None
    prefix: str = "equiflow"


class SumoCfg(BaseModel):
    """Live SUMO view (sumo/ networks driven through TraCI, see app/sumo_live.py)."""
    autostart: bool = False
    network: str = "sector_grid"
    scenario: str = "medium"
    controller: Literal["equiflow", "fixed", "actuated"] = "equiflow"
    speed: float = 2.0                 # simulated seconds per real second
    step_s: float = 0.5
    camera_range_m: float = 120.0      # how far up an approach the virtual camera sees
    camera_fps: float = 10.0
    # phases = switch between the junction's signal-plan phases (opposite approaches move together);
    # approach = one approach at a time, like the four-camera junction
    phasing: Literal["phases", "approach"] = "phases"
    base_controller: str = ""          # adaptive | marl | fixed_time; empty = the top-level `controller`
    controller_params: dict = Field(default_factory=dict)
    marl_params: dict = Field(default_factory=lambda: {"weights": "../marl/weights/marl_policy.npz"})
    # green corridor: once a camera confirms an ambulance, signals further along its route that it will
    # reach within corridor_eta_s (and corridor_range_m) start clearing for it before it gets there
    corridor: bool = True
    corridor_eta_s: float = 25.0
    corridor_range_m: float = 450.0
    # robustness tests: per-frame chance the detector misses a vehicle / scores a non-ambulance as one
    camera_miss_prob: float = 0.0
    camera_fp_prob: float = 0.0


class LogCfg(BaseModel):
    """CSV event log for evaluation (app/eventlog.py). One file per backend run."""
    enabled: bool = True
    dir: str = "logs"                       # relative to the config file's folder
    exclude: list[str] = ["ambulance_position"]


class ServerCfg(BaseModel):
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    api_key: str | None = None     # set (or EQUIFLOW_API_KEY) to require X-API-Key on every write (app/security.py)


class IntersectionCfg(BaseModel):
    id: str
    name: str = ""
    lat: float | None = None
    lng: float | None = None
    # approach -> "sim" | video file | rtsp:// URL | webcam index. Missing approach => "sim".
    sources: dict[str, str] = Field(default_factory=dict)
    # FR-04: approach -> polygon [[x, y], ...] in 0..1 image coordinates covering the lanes that queue for
    # this signal. Only vehicles whose bottom-centre is inside count, and the ones standing still are the
    # queue. No zone => every tracked vehicle in the frame counts (the old behaviour).
    zones: dict[str, list[list[float]]] = Field(default_factory=dict)


class AppConfig(BaseModel):
    mode: Literal["auto", "sim"] = "auto"
    controller: str = "adaptive"
    controller_params: dict = Field(default_factory=dict)
    timing: TimingCfg = TimingCfg()
    preempt: PreemptCfg = PreemptCfg()
    vision: VisionCfg = VisionCfg()
    sim: SimCfg = SimCfg()
    mqtt: MqttCfg = MqttCfg()
    sumo: SumoCfg = SumoCfg()
    server: ServerCfg = ServerCfg()
    log: LogCfg = LogCfg()
    intersections: list[IntersectionCfg] = [IntersectionCfg(id="J1", name="Intersection 1")]


def load_config(path: str | os.PathLike | None = None) -> AppConfig:
    p = Path(path or os.environ.get("EQUIFLOW_CONFIG") or BACKEND_DIR / "config.yaml")
    if not p.is_absolute():
        p = (Path.cwd() / p) if (Path.cwd() / p).exists() else BACKEND_DIR / p
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg = AppConfig.model_validate(raw)
    _resolve_paths(cfg, p.parent)
    return cfg


def _resolve_paths(cfg: AppConfig, base: Path) -> None:
    """Relative weight / video paths in the YAML are relative to the YAML file, not to the folder
    uvicorn happens to be started from. Names that don't exist there (e.g. 'yolo26s.pt', which
    ultralytics downloads) are left as they are."""
    def fix(value: str) -> str:
        if not value or value == "sim" or value.isdigit() or "://" in value:
            return value
        q = Path(value)
        if q.is_absolute():
            return value
        cand = (base / q).resolve()
        return str(cand) if cand.exists() else value

    if not Path(cfg.log.dir).is_absolute():
        cfg.log.dir = str((base / cfg.log.dir).resolve())
    cfg.vision.det_weights = fix(cfg.vision.det_weights)
    w = cfg.sumo.marl_params.get("weights")
    if w and not Path(w).is_absolute():          # may not exist yet (training writes it)
        cfg.sumo.marl_params["weights"] = str((base / w).resolve())
    cfg.vision.cls_weights = fix(cfg.vision.cls_weights)
    for i in cfg.intersections:
        i.sources = {a: fix(s) for a, s in i.sources.items()}
