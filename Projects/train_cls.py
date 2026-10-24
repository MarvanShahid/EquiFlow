from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolo26n-cls.pt")       
    model.train(data=r"C:\Smester7\Projects\crops", imgsz=96, epochs=30, batch=128,
                device=0, project=r"C:\Smester7\Projects\runs", name="cls_v4")
    model.val(data=r"C:\Smester7\Projects\crops", split="test")