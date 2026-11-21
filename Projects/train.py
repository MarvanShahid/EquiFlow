from ultralytics import YOLO
from pathlib import Path

HERE = Path(__file__).resolve().parent  # the Projects folder

if __name__ == "__main__":
    model = YOLO("yolo26s.pt")
    model.train(
        data=str(HERE / "data.yaml"),
        epochs=60, patience=15, imgsz=640,
        batch=16, workers=4, device=0,
        project=str(HERE / "runs"), name="v0",
    )
    model.val(data=str(HERE / "data.yaml"), split="test")   