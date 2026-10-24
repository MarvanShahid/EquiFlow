import warnings
from pathlib import Path
import numpy as np, imagehash
from PIL import Image, ImageOps

warnings.filterwarnings("ignore")      # palette/transparency wali warning band

def h64(p):
    """Ek image ka 64-bit hash (train ke liye)."""
    try:
        with Image.open(p) as im:
            return int(str(imagehash.dhash(im.convert("RGB"), hash_size=8)), 16)
    except Exception:
        return None

def h64_both(p):
    """Original aur left-right flip dono ke hash (Kaggle ke liye)."""
    try:
        with Image.open(p) as im:
            im = im.convert("RGB")
            return [int(str(imagehash.dhash(x, hash_size=8)), 16) for x in (im, ImageOps.mirror(im))]
    except Exception:
        return None

train = [p for p in Path(r"C:\Smester7\Projects\equiflow_det\images\train").iterdir() if p.is_file()]
pk = [p for p in Path(r"C:\Smester7\Projects\Dataset\Pakistani_Ambulance\images").iterdir() if p.is_file()]

th = [(p, h64(p)) for p in train]
th = [(p, h) for p, h in th if h is not None]
T = np.array([h for _, h in th], dtype=np.uint64)

def dist(a, arr):
    x = (arr ^ np.uint64(a)).view(np.uint8).reshape(-1, 8)
    return np.unpackbits(x, axis=1).sum(1)

dups = []
for p in pk:
    hh = h64_both(p)
    if hh is None: continue
    best = None
    for h in hh:
        d = dist(h, T); j = int(d.argmin())
        if best is None or d[j] < best[0]:
            best = (int(d[j]), j)
    if best[0] <= 8:
        dups.append((p.name, th[best[1]][0].name, best[0]))

print("train images hashed:", len(th), "| Kaggle images with a near-duplicate in train:", len(dups))
for a, b, d in sorted(dups, key=lambda t: t[2]):
    print(f"dist {d:2d}  {a}  <->  {b}")
