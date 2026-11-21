from pathlib import Path
from ultralytics import YOLO

HERE = Path(__file__).resolve().parent  # the Projects folder

if __name__ == "__main__":
    root = HERE / "Dataset" / "Pakistani_Ambulance"

    # kitni ambulances label hui (report ke liye)
    n_amb = sum(1 for f in (root / "labels").glob("*.txt")
                for ln in f.read_text().splitlines() if ln.startswith("0 "))
    print("images:", len(list((root / "images").iterdir())), "| ambulance boxes:", n_amb)

    (HERE / "pk.yaml").write_text(
        f"path: {root.as_posix()}\ntrain: images\nval: images\ntest: images\n"
        "names:\n  0: ambulance\n  1: other_vehicle\n")

    m = YOLO(str(HERE / "runs" / "v0" / "weights" / "best.pt"))
    r = m.val(data=str(HERE / "pk.yaml"), name="pk_eval")
    print("ambulance  P %.3f  R %.3f  mAP50 %.3f  mAP50-95 %.3f" %
          (r.box.p[0], r.box.r[0], r.box.ap50[0], r.box.ap[0]))