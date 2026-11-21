from pathlib import Path
from ultralytics import YOLO

HERE = Path(__file__).resolve().parent  # the Projects folder

if __name__ == "__main__":
    model = YOLO(
        str(HERE / "runs" / "v0" / "weights" / "best.pt")
    )

    model.predict(
        source=str(HERE / "Dataset" / "Pakistani_Ambulance" / "pakistani_ambulances"),
        conf=0.20,
        imgsz=640,
        device=0,
        save=True,
        save_txt=True,
        project=str(HERE / "prelabels"),
        name="pk",
    )

    print("DONE! Predictions have been saved.")
