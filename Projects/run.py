from pathlib import Path
from collections import defaultdict
import cv2, random

def check(root, suspects, n=12):
    areas, files = defaultdict(list), defaultdict(list)
    for f in Path(root).glob("*/labels/*.txt"):
        for ln in f.read_text().splitlines():
            p = ln.split()
            if len(p) != 5: continue
            c = int(p[0]); areas[c].append(float(p[3]) * float(p[4]))
            if c in suspects: files[c].append(f)
    for c in sorted(areas):
        a = sorted(areas[c]); print(root, "class", c, "boxes", len(a), "median area", round(a[len(a)//2], 4))
    for c in suspects:
        out = Path("check") / Path(root).name / str(c); out.mkdir(parents=True, exist_ok=True)
        for f in random.sample(files[c], min(n, len(files[c]))):
            img = next((f.parent.parent / "images" / (f.stem + e) for e in (".jpg", ".jpeg", ".png")
                        if (f.parent.parent / "images" / (f.stem + e)).exists()), None)
            if img is None: continue
            im = cv2.imread(str(img)); H, W = im.shape[:2]
            for ln in f.read_text().splitlines():
                p = ln.split()
                if len(p) != 5: continue
                k, x, y, w, h = int(p[0]), *map(float, p[1:])
                x1, y1, x2, y2 = int((x-w/2)*W), int((y-h/2)*H), int((x+w/2)*W), int((y+h/2)*H)
                col = (0, 0, 255) if k == c else (0, 255, 0)
                cv2.rectangle(im, (x1, y1), (x2, y2), col, 2)
                cv2.putText(im, str(k), (x1, max(y1-5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            cv2.imwrite(str(out / img.name), im)

check("Dataset/Ambulance_Detection_v3iyolo26", suspects=[0, 3, 5, 6])
check("Dataset/Ambulance.v20-final_dataset", suspects=[0, 5])
