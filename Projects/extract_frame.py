import cv2
from pathlib import Path

VIDEO_DIR = Path(r"C:\Smester7\Projects\videos")
ROOT = Path(r"C:\Smester7\Projects\Dataset\local")

BASE_SEC = 1.0                       # normal frames: har 1 second par ek
NAMES = sorted(p.stem for p in VIDEO_DIR.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"})
DENSE_SEC = 0.08                                   # har 2 frames par ek (25 FPS par)
AMB_WINDOWS = {"test2.mp4": (1, 7), "test12": (22, 26)}   # thora margin ke saath
OUT_W = 1920

for name in NAMES:
    paths = list(VIDEO_DIR.glob(name + ".*"))
    if not paths:
        print("VIDEO NAHI MILI:", name); continue
    cap = cv2.VideoCapture(str(paths[0]))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    s0, s1 = AMB_WINDOWS.get(name, (0, 0))
    out = ROOT / name / "images"; out.mkdir(parents=True, exist_ok=True)
    next_t, i, n = 0.0, 0, 0
    while True:
        ok, f = cap.read()
        if not ok: break
        t = i / fps
        if t >= next_t:
            h, w = f.shape[:2]
            f = cv2.resize(f, (OUT_W, int(h * OUT_W / w)), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(out / f"{name}_{i:06d}.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 95]); n += 1
            next_t = t + (DENSE_SEC if (s1 > s0 and s0 <= t <= s1) else BASE_SEC)
        i += 1
    cap.release()
    print(f"{name}: {n} frames from {i/fps:.0f}s video -> {out}")