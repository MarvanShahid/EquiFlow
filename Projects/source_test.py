from pathlib import Path
from ultralytics import YOLO

if __name__ == "__main__":
    root = Path(r"C:\Smester7\Projects\equiflow_det")
    model = YOLO(r"C:\Smester7\Projects\runs\v0\weights\best.pt")
    for src in ["d1", "d2", "d3", "d4", "d5", "d6"]:
        imgs = sorted((root / "images" / "test").glob(f"{src}_*"))
        if not imgs: continue
        n_amb = sum(1 for p in imgs
                    for ln in (root / "labels" / "test" / (p.stem + ".txt")).read_text().splitlines()
                    if ln.startswith("0 "))
        lst = root / f"test_{src}.txt"
        lst.write_text("\n".join(str(p) for p in imgs))
        yml = root / f"test_{src}.yaml"
        yml.write_text(f"path: {root.as_posix()}\ntrain: {lst.as_posix()}\nval: {lst.as_posix()}\n"
                       f"test: {lst.as_posix()}\nnames:\n  0: ambulance\n  1: other_vehicle\n")
        try:
            r = model.val(data=str(yml), split="test", plots=False, verbose=False)
            i = list(r.box.ap_class_index).index(0)
            print(f"{src}: {len(imgs)} imgs, {n_amb} ambulances | P {r.box.p[i]:.3f} "
                  f"R {r.box.r[i]:.3f} mAP50 {r.box.ap50[i]:.3f} mAP50-95 {r.box.ap[i]:.3f}")
        except Exception as e:
            print(src, "skipped:", e)