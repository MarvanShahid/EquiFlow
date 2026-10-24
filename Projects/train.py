from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolo26s.pt")
    model.train(
        data=r"C:\Smester7\Projects\data.yaml",
        epochs=60, patience=15, imgsz=640,
        batch=16, workers=4, device=0,
        project=r"C:\Smester7\Projects\runs", name="v0",
    )
    model.val(data=r"C:\Smester7\Projects\data.yaml", split="test")   