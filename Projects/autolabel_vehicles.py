from pathlib import Path
import cv2
from ultralytics import YOLO

if __name__ == "__main__":
    ROOT = Path(r"C:\Smester7\Projects\Dataset\local")
    
    NAMES = sorted(d.name for d in ROOT.iterdir() if (d / "images").exists())
    model = YOLO("yolo26s.pt")                    # COCO pretrained
    for name in NAMES:
        img_dir = ROOT / name / "images"
        if not img_dir.exists():
            print("folder nahi:", name); continue
        lbl_dir = ROOT / name / "labels"; lbl_dir.mkdir(exist_ok=True)
        prev = ROOT / name / "preview"; prev.mkdir(exist_ok=True)
        for k, p in enumerate(sorted(img_dir.glob("*.jpg"))):
            r = model.predict(str(p), imgsz=1920, conf=0.35, classes=[2, 3, 5, 7],   # car, motorcycle, bus, truck
                              device=0, verbose=False)[0]
            lines = [f"1 {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for x, y, w, h in r.boxes.xywhn.cpu().tolist()]
            (lbl_dir / (p.stem + ".txt")).write_text("\n".join(lines))     # class 1 = other_vehicle
            if k % 5 == 0:
                cv2.imwrite(str(prev / p.name), r.plot(line_width=5, font_size=2))
        print(name, "labeled")