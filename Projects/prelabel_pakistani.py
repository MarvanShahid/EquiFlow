from pathlib import Path
from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO(
        r"C:\Smester7\Projects\runs\v0\weights\best.pt"
    )

    model.predict(
        source=r"C:\Smester7\Projects\Dataset\Pakistani_Ambulance\pakistani_ambulances",
        conf=0.20,
        imgsz=640,
        device=0,
        save=True,
        save_txt=True,
        project=r"C:\Smester7\Projects\prelabels",
        name="pk",
    )

    print("DONE! Predictions have been saved.")
