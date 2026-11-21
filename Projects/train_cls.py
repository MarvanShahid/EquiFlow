from ultralytics import YOLO
from pathlib import Path

HERE = Path(__file__).resolve().parent  # the Projects folder

if __name__ == "__main__":
    model = YOLO("yolo26n-cls.pt")       
    model.train(data=str(HERE / "crops"), imgsz=96, epochs=30, batch=128,
                device=0, project=str(HERE / "runs"), name="cls_v4")
    model.val(data=str(HERE / "crops"), split="test")