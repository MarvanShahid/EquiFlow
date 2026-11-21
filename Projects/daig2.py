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
    model = YOLO("yolo26s.pt")                      # COCO pretrained
    for sz in (1280, 1920):
        r = model.predict(frame, imgsz=sz, conf=0.25, classes=[2, 3, 5, 7],   # car, motorcycle, bus, truck
                          device=0, verbose=False)[0]
        print(f"COCO yolo26s imgsz {sz}: {len(r.boxes)} vehicles")
        cv2.imwrite(str(out / f"coco_{sz}.jpg"), r.plot(line_width=6, font_size=2))