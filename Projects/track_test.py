from ultralytics import YOLO
from pathlib import Path

HERE = Path(__file__).resolve().parent  # the Projects folder

if __name__ == "__main__":
    model = YOLO(str(HERE / "runs" / "v0" / "weights" / "best.pt"))
    model.track(source=str(HERE / "videos" / "test1.mp4.mp4"), tracker="bytetrack.yaml",
                conf=0.25, imgsz=640, device=0, save=True,
                project=str(HERE / "runs"), name="track_test")
    