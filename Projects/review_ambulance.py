from pathlib import Path
import cv2

FOLDER = Path(r"C:\Smester7\Projects\Dataset\local\test2.mp4")     # test12 ke liye badal dena
IMG_DIR, LBL_DIR = FOLDER / "images", FOLDER / "labels"
MAX_W, FONT = 1500, cv2.FONT_HERSHEY_SIMPLEX
COLORS = {0: (0, 0, 255), 1: (0, 200, 0)}          # laal = ambulance, hara = other_vehicle

def load(txt):
    rows = []
    if txt.exists():
        for ln in txt.read_text().splitlines():
            p = ln.split()
            if len(p) >= 5:
                rows.append([int(p[0])] + list(map(float, p[1:5])))
    return rows

def save(txt, rows):
    txt.write_text("\n".join(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in rows))

def box_px(r, W, H):
    _, x, y, w, h = r
    return int((x - w/2) * W), int((y - h/2) * H), int((x + w/2) * W), int((y + h/2) * H)

def hit(rows, px, py, W, H):
    best, best_area = None, None
    for k, r in enumerate(rows):
        x1, y1, x2, y2 = box_px(r, W, H)
        if x1 <= px <= x2 and y1 <= py <= y2:
            area = (x2 - x1) * (y2 - y1)
            if best is None or area < best_area:
                best, best_area = k, area
    return best

state = {"rows": [], "W": 1, "H": 1, "dirty": True}

def on_mouse(event, px, py, flags, param):
    rows, W, H = state["rows"], state["W"], state["H"]
    if event == cv2.EVENT_LBUTTONDOWN:                 # click: class badlo
        k = hit(rows, px, py, W, H)
        if k is not None:
            rows[k][0] = 0 if rows[k][0] == 1 else 1
            state["dirty"] = True
    elif event == cv2.EVENT_RBUTTONDOWN:               # right-click: box delete
        k = hit(rows, px, py, W, H)
        if k is not None:
            rows.pop(k)
            state["dirty"] = True

imgs = sorted(IMG_DIR.glob("*.jpg"))
cv2.namedWindow("amb")
cv2.setMouseCallback("amb", on_mouse)
i = 0
while 0 <= i < len(imgs):
    p = imgs[i]
    txt = LBL_DIR / (p.stem + ".txt")
    im = cv2.imread(str(p))
    im = cv2.resize(im, None, fx=min(1.0, MAX_W / im.shape[1]), fy=min(1.0, MAX_W / im.shape[1]))
    H, W = im.shape[:2]
    state.update(rows=load(txt), W=W, H=H, dirty=True)
    action, view = None, im
    while action is None:
        if state["dirty"]:
            view = im.copy()
            for r in state["rows"]:
                x1, y1, x2, y2 = box_px(r, W, H)
                cv2.rectangle(view, (x1, y1), (x2, y2), COLORS[r[0]], 4 if r[0] == 0 else 1)
            n_amb = sum(1 for r in state["rows"] if r[0] == 0)
            cv2.putText(view, f"{i+1}/{len(imgs)} {p.name} | ambulance: {n_amb} | click=class badlo  right-click=delete  a=ambulance add  n/b/q",
                        (10, 28), FONT, 0.6, (0, 255, 255), 2)
            cv2.imshow("amb", view)
            state["dirty"] = False
        key = cv2.waitKey(30) & 0xFF
        if key == ord("a"):
            x, y, w, h = cv2.selectROI("amb", view, showCrosshair=False)    # drag, phir Enter
            cv2.setMouseCallback("amb", on_mouse)
            if w > 0 and h > 0:
                state["rows"].append([0, (x + w/2) / W, (y + h/2) / H, w / W, h / H])
            state["dirty"] = True
        elif key in (ord("n"), ord("b"), ord("q")):
            action = chr(key)
    save(txt, state["rows"])
    if action == "q":
        break
    i += 1 if action == "n" else -1
cv2.destroyAllWindows()