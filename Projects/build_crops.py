import random
from pathlib import Path
from PIL import Image, ImageFilter

random.seed(0)
PUB   = Path(r"C:\Smester7\Projects\equiflow_det")
LOCAL = Path(r"C:\Smester7\Projects\Dataset\local")
PK    = Path(r"C:\Smester7\Projects\Dataset\Pakistani_Ambulance")      # Kaggle: sirf TEST mein
OUT   = Path(r"C:\Smester7\Projects\updated_crops")
# apni ambulance-free videos ke asli naam likho. Ambulance wali (test2.mp4, test12) yahan NAHI.
LOCAL_SPLIT = {
    "test6": "train",
    "test7": "train",
    "test8": "train",
    "test9": "val",
    "test11": "test",
    "v1": "train",
    "v2": "train",
}
PAD, MIN_SIDE, MAX_NEG_RATIO, DEGRADE_P = 0.12, 20, 3, 0.5
NAMES = {0: "ambulance", 1: "other_vehicle"}

def index(img_dir):
    return {p.stem: p for p in img_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}

entries = []   # (split, cls, img_path, (x, y, w, h), source)
def collect(img_dir, lbl_dir, split, source, only_cls=None):
    if not img_dir.exists() or not lbl_dir.exists():
        print("folder nahi mila:", img_dir); return
    imgs = index(img_dir)
    for lbl in lbl_dir.glob("*.txt"):
        if lbl.stem not in imgs: continue
        for ln in lbl.read_text().splitlines():
            p = ln.split()
            if len(p) != 5: continue
            c = int(p[0])
            if only_cls is not None and c != only_cls: continue
            entries.append((split, c, imgs[lbl.stem], tuple(map(float, p[1:])), source))

for sp in ("train", "val", "test"):
    collect(PUB / "images" / sp, PUB / "labels" / sp, sp, "pub")
for name, sp in LOCAL_SPLIT.items():
    collect(LOCAL / name / "images", LOCAL / name / "labels", sp, "local", only_cls=1)
collect(PK / "images", PK / "labels", "test", "pk", only_cls=0)

def degrade(im):
    w, h = im.size
    s = random.uniform(22, 80) / min(w, h)
    if s >= 1: return im
    small = im.resize((max(8, int(w * s)), max(8, int(h * s))),
                      random.choice([Image.BILINEAR, Image.BICUBIC, Image.BOX]))
    if random.random() < 0.5:
        small = small.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.0)))
    return small.resize((w, h), Image.BILINEAR)

selected = []
for sp in ("train", "val", "test"):
    pos = [e for e in entries if e[0] == sp and e[1] == 0]
    loc = [e for e in entries if e[0] == sp and e[1] == 1 and e[4] == "local"]
    pub = [e for e in entries if e[0] == sp and e[1] == 1 and e[4] == "pub"]
    if sp == "train":
        random.shuffle(pub)
        pub = pub[:max(0, MAX_NEG_RATIO * len(pos) - len(loc))]
    selected += pos + loc + pub

counts = {}
for k, (sp, c, path, (x, y, w, h), src) in enumerate(selected):
    im = Image.open(path).convert("RGB"); W, H = im.size
    bw, bh = w * W, h * H
    if min(bw, bh) < MIN_SIDE: continue
    cx, cy = x * W, y * H
    box = (int(max(0, cx - bw / 2 * (1 + PAD))), int(max(0, cy - bh / 2 * (1 + PAD))),
           int(min(W, cx + bw / 2 * (1 + PAD))), int(min(H, cy + bh / 2 * (1 + PAD))))
    crop = im.crop(box)
    if sp == "train" and random.random() < DEGRADE_P:
        crop = degrade(crop)
    d = OUT / sp / NAMES[c]; d.mkdir(parents=True, exist_ok=True)
    crop.save(d / f"{src}_{k:06d}.jpg", quality=92)
    counts[(sp, NAMES[c], src)] = counts.get((sp, NAMES[c], src), 0) + 1

for key in sorted(counts): print(key, counts[key])