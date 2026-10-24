import shutil
from pathlib import Path
import cv2
from ultralytics import YOLO

if __name__ == "__main__":
    ROOT = Path(r"C:\Smester7\Projects\crops")
    BACKUP = Path(r"C:\Smester7\Projects\web_originals"); BACKUP.mkdir(exist_ok=True)
    KNOWN = ("pub_", "pk_", "local_", "web_")
    PAD = 0.12
    det = YOLO("yolo26s.pt")
    for sp in ("train", "val", "test"):
        for f in sorted((ROOT / sp / "ambulance").iterdir()):
            if not f.is_file() or f.name.startswith(KNOWN) or ".rf." not in f.name:
                continue
            im = cv2.imread(str(f))
            if im is None:
                print("parh nahi saka:", f.name); continue
            r = det.predict(im, imgsz=960, conf=0.25, classes=[2, 3, 5, 7], device=0, verbose=False)[0]
            if len(r.boxes) == 0:
                print("koi gaari nahi mili (haath se dekho):", sp, f.name); continue
            x1, y1, x2, y2 = max(r.boxes.xyxy.cpu().numpy(), key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
            H, W = im.shape[:2]
            bw, bh, cx, cy = x2 - x1, y2 - y1, (x1 + x2) / 2, (y1 + y2) / 2
            a, b = int(max(0, cx - bw / 2 * (1 + PAD))), int(max(0, cy - bh / 2 * (1 + PAD)))
            c, d = int(min(W, cx + bw / 2 * (1 + PAD))), int(min(H, cy + bh / 2 * (1 + PAD)))
            shutil.copy(f, BACKUP / f"{sp}_{f.name}")
            cv2.imwrite(str(f.with_suffix(".jpg")), im[b:d, a:c])
            if f.suffix.lower() != ".jpg":
                f.unlink()