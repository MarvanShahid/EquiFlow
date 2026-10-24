import shutil, hashlib
from pathlib import Path
from PIL import Image
import imagehash

OUT = Path("equiflow_det")
D = Path("Dataset")

SOURCES = {
    "d1": {"root": D / "Ambulance_Detection_v3iyolo26", "map": {5: 0, 0: 1, 1: 1, 2: 1, 6: 1}},
    "d3": {"root": D / "Ambulance.v20-final_dataset",   "map": {0: 0, 1: 1, 2: 1, 3: 1, 4: 1}},
    "d5": {"root": D / "Pakistan_Vehicle_Detection",    "map": {1: 0, 0: 1, 2: 1, 3: 1, 4: 1}},
    "d6": {"root": D / "Vehicle_OpenImages",           "map": {0: 0, 1: 1, 2: 1, 3: 1, 4: 1}},
    "d2": {"root": D / "Detecting_the_ambulancev4",     "map": {0: 0}},
    "d4": {"root": D / "ambulance_v5yolo26",     "map": {0: 0}},
}

def split_for(key):
    r = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
    return "train" if r < 80 else "val" if r < 90 else "test"

if OUT.exists():
    shutil.rmtree(OUT)            # fresh start, no stale files

seen, boxes, imgs = set(), {}, {}
for src, cfg in SOURCES.items():
    root = cfg["root"]
    if not root.exists():
        print("MISSING FOLDER:", root); continue
    for sp in ("train", "valid", "test", ""):
        img_dir, lbl_dir = root / sp / "images", root / sp / "labels"
        if not img_dir.exists(): continue
        for img in img_dir.iterdir():
            if img.suffix.lower() not in {".jpg", ".jpeg", ".png"}: continue
            lbl = lbl_dir / (img.stem + ".txt")
            if not lbl.exists(): continue
            lines = []
            for ln in lbl.read_text().splitlines():
                p = ln.split()
                if len(p) != 5: continue
                new = cfg["map"].get(int(p[0]))
                if new is None: continue
                lines.append(" ".join([str(new)] + p[1:]))
            if not lines: continue
            try:
                with Image.open(img) as im:
                    h = str(imagehash.dhash(im, hash_size=12))
            except Exception:
                print("Skipping unreadable image:", img, e)
                continue          
            if h in seen: continue
            seen.add(h)
            key = f"{src}:{img.stem.split('.rf.')[0]}"
            out_sp = cfg.get("force_split") or split_for(key)
            name = f"{src}_{img.stem}"
            for sub in ("images", "labels"):
                (OUT / sub / out_sp).mkdir(parents=True, exist_ok=True)
            shutil.copy(img, OUT / "images" / out_sp / f"{name}{img.suffix}")
            (OUT / "labels" / out_sp / f"{name}.txt").write_text("\n".join(lines))
            imgs[out_sp] = imgs.get(out_sp, 0) + 1
            for ln in lines:
                k = (out_sp, ln[0]); boxes[k] = boxes.get(k, 0) + 1

print("images per split:", imgs)
for k in sorted(boxes): print("split", k[0], "class", k[1], "boxes", boxes[k])