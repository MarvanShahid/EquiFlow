"""calibrate_lanes.py - make the calibrated lane-level queue configuration for one camera approach.

Interactive (needs a display):
    python calibrate_lanes.py videos/test12.mp4 --approach East --time 5 --world "0,0 3.5,0 3.5,12 0,12"
  1. click the 4 calibration points on the road surface, in the same order as --world (metres on the ground;
     e.g. the corners of a lane between two dashes: lane width 3.5 m, dash period 12 m)
  2. for each lane: click its outline (at least 3 points), press Enter; click the 2 ends of its stop line,
     press Enter; type the lane id in the terminal. Press Esc instead of the outline to finish.
  -> prints the YAML for the intersection config (lanes: + calibration:) and saves lanes_<approach>.yaml

Without a display, give everything on the command line (image coordinates 0..1):
    python calibrate_lanes.py frame.jpg --approach East --image "0.3,0.2 0.7,0.2 0.95,0.95 0.05,0.95" \\
        --world "0,40 7,40 7,0 0,0" --lane "E1:0.3,0.2;0.5,0.2;0.5,0.95;0.05,0.95|0.05,0.95;0.5,0.95"

Check a calibration (draws the lanes and a 5 m ground grid on the frame; works without a display):
    python calibrate_lanes.py videos/test12.mp4 --check lanes_East.yaml --out check_East.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
from app.vision.lanes import LaneModel, homography, to_world  # noqa: E402


def read_frame(src: str, t: float) -> np.ndarray:
    img = cv2.imread(src)
    if img is not None:
        return img
    cap = cv2.VideoCapture(src)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"cannot read a frame from {src}")
    return frame


def pts(s: str) -> list[list[float]]:
    return [[float(v) for v in p.split(",")] for p in s.replace(";", " ").split()]


def build(approach: str, image: list, world: list, lanes: list[dict]) -> dict:
    LaneModel(lanes, {"image": image, "world": world})          # validates (raises on bad input)
    r = lambda p: [round(float(v), 4) for v in p]  # noqa: E731
    return {"lanes": {approach: [{"id": l["id"], "polygon": [r(p) for p in l["polygon"]],
                                  "stop_line": [r(p) for p in l["stop_line"]]} for l in lanes]},
            "calibration": {approach: {"image": [r(p) for p in image], "world": [r(p) for p in world]}}}


def draw_check(frame: np.ndarray, conf: dict, approach: str) -> np.ndarray:
    h, w = frame.shape[:2]
    out = frame.copy()
    cal = conf["calibration"][approach]
    Hiw = homography(cal["world"], cal["image"])                 # ground -> image
    wld = np.asarray(cal["world"], dtype=float)
    x0, y0 = np.floor(wld.min(0) / 5) * 5
    x1, y1 = np.ceil(wld.max(0) / 5) * 5
    for x in np.arange(x0, x1 + 0.1, 5):                         # 5 m ground grid
        a, b = to_world(Hiw, [[x, y0], [x, y1]])
        cv2.line(out, (int(a[0] * w), int(a[1] * h)), (int(b[0] * w), int(b[1] * h)), (90, 90, 90), 1)
    for y in np.arange(y0, y1 + 0.1, 5):
        a, b = to_world(Hiw, [[x0, y], [x1, y]])
        cv2.line(out, (int(a[0] * w), int(a[1] * h)), (int(b[0] * w), int(b[1] * h)), (90, 90, 90), 1)
        cv2.putText(out, f"{y:.0f} m", (int(a[0] * w) + 3, int(a[1] * h) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (200, 200, 200), 1)
    for ln in conf["lanes"][approach]:
        poly = (np.asarray(ln["polygon"]) * [w, h]).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [poly], True, (255, 220, 120), 2)
        s = (np.asarray(ln["stop_line"]) * [w, h]).astype(np.int32)
        cv2.line(out, tuple(s[0]), tuple(s[1]), (0, 0, 255), 3)
        cv2.putText(out, ln["id"], tuple(s[0] + [4, -6]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 220, 120), 2)
    for i, p in enumerate(cal["image"]):
        cv2.circle(out, (int(p[0] * w), int(p[1] * h)), 5, (0, 255, 255), -1)
        cv2.putText(out, str(cal["world"][i]), (int(p[0] * w) + 6, int(p[1] * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 255), 1)
    return out


def click_points(frame: np.ndarray, title: str, n: int | None) -> list[list[float]] | None:
    h, w = frame.shape[:2]
    got: list[list[float]] = []
    view = frame.copy()

    def on_mouse(ev, x, y, *_):
        if ev == cv2.EVENT_LBUTTONDOWN:
            got.append([x / w, y / h])
            cv2.circle(view, (x, y), 4, (0, 255, 255), -1)
            if len(got) > 1:
                a = (int(got[-2][0] * w), int(got[-2][1] * h))
                cv2.line(view, a, (x, y), (0, 255, 255), 1)

    cv2.namedWindow(title)
    cv2.setMouseCallback(title, on_mouse)
    while True:
        cv2.imshow(title, view)
        k = cv2.waitKey(30) & 0xFF
        if k == 27:
            cv2.destroyWindow(title)
            return None
        if (n is not None and len(got) == n) or (n is None and k in (13, 10) and len(got) >= 3) or \
                (n == 2 and k in (13, 10) and len(got) == 2):
            cv2.destroyWindow(title)
            return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="video file or image")
    ap.add_argument("--approach", default="North")
    ap.add_argument("--time", type=float, default=1.0, help="seconds into the video for the frame")
    ap.add_argument("--world", help='the 4+ calibration points on the ground in metres, "x,y x,y x,y x,y"')
    ap.add_argument("--image", help="the same points in the image (0..1); without it you click them")
    ap.add_argument("--lane", action="append", default=[],
                    help='"id:x,y;x,y;x,y|x,y;x,y" = outline | stop line (0..1); repeat per lane')
    ap.add_argument("--check", help="draw an existing lanes YAML on the frame instead")
    ap.add_argument("--out", help="image to write (default lanes_<approach>.jpg)")
    a = ap.parse_args()
    frame = read_frame(a.source, a.time)
    out_img = a.out or str(HERE / f"lanes_{a.approach}.jpg")

    if a.check:
        conf = yaml.safe_load(Path(a.check).read_text(encoding="utf-8"))
        cv2.imwrite(out_img, draw_check(frame, conf, a.approach))
        print("wrote", out_img)
        return

    if not a.world:
        sys.exit("--world is required: the calibration points' ground positions in metres")
    world = pts(a.world)
    image = pts(a.image) if a.image else click_points(frame, f"click the {len(world)} calibration points", len(world))
    if image is None:
        sys.exit("cancelled")
    lanes = []
    for spec in a.lane:
        lid, rest = spec.split(":", 1)
        poly, stop = rest.split("|")
        lanes.append({"id": lid, "polygon": pts(poly), "stop_line": pts(stop)})
    while not a.lane:                                            # interactive lanes
        poly = click_points(frame, "lane outline (Enter = done, Esc = no more lanes)", None)
        if poly is None:
            break
        stop = click_points(frame, "lane stop line: 2 points", 2)
        lid = input("lane id (e.g. N1): ").strip() or f"{a.approach[0]}{len(lanes) + 1}"
        lanes.append({"id": lid, "polygon": poly, "stop_line": stop})
    if not lanes:
        sys.exit("no lanes given")
    conf = build(a.approach, image, world, lanes)
    text = yaml.safe_dump(conf, sort_keys=False, default_flow_style=None)
    yml = HERE / f"lanes_{a.approach}.yaml"
    yml.write_text(text, encoding="utf-8")
    cv2.imwrite(out_img, draw_check(frame, conf, a.approach))
    print(text)
    print(f"saved {yml} and {out_img}. Paste lanes: and calibration: into the intersection in config.live.yaml.")


if __name__ == "__main__":
    main()
