from pathlib import Path
import cv2
from ultralytics import YOLO

HERE = Path(__file__).resolve().parent  # the Projects folder

if __name__ == "__main__":
    VIDEO = str(HERE / "videos" / "test7.mp4")
    FRAME = 294
    out = HERE / "diag"; out.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(VIDEO); cap.set(cv2.CAP_PROP_POS_FRAMES, FRAME)
    ok, frame = cap.read(); cap.release()
    assert ok, "frame nahi mili"
    model = YOLO(str(HERE / "runs" / "v0" / "weights" / "best.pt"))
    for sz in (640, 1280, 1920):
        r = model.predict(frame, imgsz=sz, conf=0.10, device=0, verbose=False)[0]
        names = [r.names[int(c)] for c in r.boxes.cls]
        print(f"imgsz {sz}: {len(names)} detections | ambulance: {names.count('ambulance')}, "
              f"other_vehicle: {names.count('other_vehicle')}")
        cv2.imwrite(str(out / f"frame{FRAME}_imgsz{sz}.jpg"), r.plot(line_width=6, font_size=2))