from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO(r"C:\Smester7\Projects\runs\v0\weights\best.pt")
    model.track(source=r"C:\Smester7\Projects\videos\test1.mp4.mp4", tracker="bytetrack.yaml",
                conf=0.25, imgsz=640, device=0, save=True,
                project=r"C:\Smester7\Projects\runs", name="track_test")
    