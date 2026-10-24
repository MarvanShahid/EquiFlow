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


class ServerCfg(BaseModel):
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


class IntersectionCfg(BaseModel):
    id: str
    name: str = ""
    lat: float | None = None
    lng: float | None = None
    # approach -> "sim" | video file | rtsp:// URL | webcam index. Missing approach => "sim".
    sources: dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    mode: Literal["auto", "sim"] = "auto"
    controller: str = "adaptive"
    controller_params: dict = Field(default_factory=dict)
    timing: TimingCfg = TimingCfg()
    preempt: PreemptCfg = PreemptCfg()
    vision: VisionCfg = VisionCfg()
    sim: SimCfg = SimCfg()
    mqtt: MqttCfg = MqttCfg()
    server: ServerCfg = ServerCfg()
    intersections: list[IntersectionCfg] = [IntersectionCfg(id="J1", name="Intersection 1")]


def load_config(path: str | os.PathLike | None = None) -> AppConfig:
    p = Path(path or os.environ.get("EQUIFLOW_CONFIG") or BACKEND_DIR / "config.yaml")
    if not p.is_absolute():
        p = (Path.cwd() / p) if (Path.cwd() / p).exists() else BACKEND_DIR / p
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
