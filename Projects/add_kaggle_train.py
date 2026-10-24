import hashlib, shutil
from pathlib import Path

ROOT = Path(r"C:\Smester7\Projects\crops")
src, dst = ROOT / "test" / "ambulance", ROOT / "train" / "ambulance"
n_img, n_crops = set(), 0
for f in sorted(src.glob("pk_*.jpg")):
    image_key = f.stem.rsplit("_", 1)[0]                   # pk_<image name> (crop number hata kar)
    if int(hashlib.md5(image_key.encode()).hexdigest(), 16) % 2 == 0:
        for rep in range(3):                               # 3 guna oversample
            (shutil.move if rep == 0 else shutil.copy)(str(f if rep == 0 else dst / f.name),
                                                       str(dst / (f.stem + f"_r{rep}.jpg")))
        n_img.add(image_key); n_crops += 1
print("images:", len(n_img), "| crops moved to train:", n_crops, "(x3 copies in train)")