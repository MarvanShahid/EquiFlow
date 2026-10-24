from pathlib import Path
import cv2

IMG_DIR = Path(r"C:\Smester7\Projects\Dataset\Pakistani_Ambulance\images")
PRE_DIR = Path(r"C:\Smester7\Projects\prelabels\pk\labels")
OUT_DIR = Path(r"C:\Smester7\Projects\Dataset\Pakistani_Ambulance\labels")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_W, FONT = 1100, cv2.FONT_HERSHEY_SIMPLEX

def load_boxes(txt):
    boxes = []
    if txt.exists():
        for ln in txt.read_text().splitlines():
            p = ln.split()
            if len(p) >= 5 and p[0] == "0":
                boxes.append(list(map(float, p[1:5])))
    return boxes

def save(path, boxes):
    path.write_text("\n".join(f"0 {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for x, y, w, h in boxes))

imgs = sorted(p for p in IMG_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
i = next((k for k, p in enumerate(imgs) if not (OUT_DIR / (p.stem + ".txt")).exists()), 0)

while 0 <= i < len(imgs):
    p = imgs[i]
    out = OUT_DIR / (p.stem + ".txt")
    boxes = load_boxes(out if out.exists() else PRE_DIR / (p.stem + ".txt"))
    im = cv2.imread(str(p))
    if im is None:
        i += 1; continue
    s = min(1.0, MAX_W / im.shape[1])
    im = cv2.resize(im, None, fx=s, fy=s)
    H, W = im.shape[:2]
    action = None
    while action is None:
        view = im.copy()
        for k, (x, y, w, h) in enumerate(boxes):
            x1, y1, x2, y2 = int((x - w/2) * W), int((y - h/2) * H), int((x + w/2) * W), int((y + h/2) * H)
            cv2.rectangle(view, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(view, str(k), (x1, max(y1 - 6, 15)), FONT, 0.7, (0, 0, 255), 2)
        cv2.putText(view, f"{i+1}/{len(imgs)} boxes:{len(boxes)} | a=add 0-9=delete box c=clear n=next b=back q=quit",
                    (10, 25), FONT, 0.55, (0, 255, 255), 2)
        cv2.imshow("review", view)
        key = cv2.waitKey(0) & 0xFF
        if key == ord("a"):
            x, y, w, h = cv2.selectROI("review", im, showCrosshair=False)   # drag, then press ENTER
            if w > 0 and h > 0:
                boxes.append([(x + w/2) / W, (y + h/2) / H, w / W, h / H])
        elif ord("0") <= key <= ord("9"):
            if key - ord("0") < len(boxes):
                boxes.pop(key - ord("0"))
        elif key == ord("c"):
            boxes.clear()
        elif key in (ord("n"), ord("b"), ord("q")):
            action = chr(key)
    save(out, boxes)
    if action == "q": break
    i += 1 if action == "n" else -1

cv2.destroyAllWindows()