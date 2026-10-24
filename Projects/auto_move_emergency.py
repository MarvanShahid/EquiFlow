import csv, shutil
from pathlib import Path
import cv2, numpy as np
import torch, open_clip
from PIL import Image

ROOT = Path(r"C:\Smester7\Projects\crops")
SPLITS = ["train", "val", "test"]
DEST = "other_vehicle"     # jahan move karna hai (alag folder chahiye to "other_emergency")
APPLY = False              # pehle False: sirf report. Check ke baad True karo
T_MOVE = 0.60              # police+fire ka probability is se zyada ho
T_AMB_MAX = 0.30           # aur ambulance ka probability is se kam ho => move
T_REVIEW = 0.35            # T_REVIEW se T_MOVE ke beech: review list

PROMPTS = {
    "ambulance": ["an ambulance", "an ambulance van", "an emergency medical vehicle"],
    "police":    ["a police car", "a police van", "a police pickup truck", "a police patrol vehicle"],
    "fire":      ["a fire truck", "a fire brigade vehicle", "a fire engine"],
    "other":     ["a passenger car", "a taxi", "a minibus", "a van", "a bus", "a truck",
                  "a pickup truck", "an auto rickshaw", "a motorcycle"],
}

device = "cuda" if torch.cuda.is_available() else "cpu"
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
model = model.to(device).eval()
tok = open_clip.get_tokenizer("ViT-B-32")
texts, groups = [], []
for g, (name, ps) in enumerate(PROMPTS.items()):
    for p in ps:
        texts.append("a photo of " + p); groups.append(g)
with torch.no_grad():
    t = model.encode_text(tok(texts).to(device)).float()
    t = t / t.norm(dim=-1, keepdim=True)
gid = torch.tensor(groups, device=device)

rows = []      # (split, file, p_amb, p_police, p_fire, p_other)
for sp in SPLITS:
    files = sorted((ROOT / sp / "ambulance").glob("pub_*.jpg"))      # Kaggle (pk_) ko nahi chhedte
    print(sp, len(files), "ambulance crops scan ho rahe hain")
    for i in range(0, len(files), 128):
        batch, ims = files[i:i + 128], []
        for f in batch:
            try:
                ims.append(preprocess(Image.open(f).convert("RGB")))
            except Exception:
                ims.append(torch.zeros(3, 224, 224))
        x = torch.stack(ims).to(device)
        with torch.no_grad():
            v = model.encode_image(x).float()
            v = v / v.norm(dim=-1, keepdim=True)
            probs = (100.0 * v @ t.T).softmax(dim=-1)
            gp = torch.zeros(len(batch), len(PROMPTS), device=device).index_add_(1, gid, probs)
        for f, p in zip(batch, gp.cpu().tolist()):
            rows.append((sp, f, *p))

move, review = [], []
for r in rows:
    sp, f, pa, pp, pf, po = r
    pe = pp + pf
    if pe >= T_MOVE and pa <= T_AMB_MAX:
        move.append(r)
    elif pe >= T_REVIEW and pa <= 0.5:
        review.append(r)
move.sort(key=lambda r: r[3] + r[4])          # sab se kam yaqeen wale pehle (jin ko check karna hai)
review.sort(key=lambda r: -(r[3] + r[4]))

with open("emergency_scan.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["split", "name", "p_amb", "p_police", "p_fire", "p_other"])
    for sp, f, pa, pp, pf, po in rows:
        w.writerow([sp, f.name, f"{pa:.3f}", f"{pp:.3f}", f"{pf:.3f}", f"{po:.3f}"])

def make_sheets(items, prefix, tile=120, cols=10, nrows=8):
    per = cols * nrows
    for n in range(0, len(items), per):
        grid = np.full((nrows * tile, cols * tile, 3), 30, np.uint8)
        for k, (sp, f, pa, pp, pf, po) in enumerate(items[n:n + per]):
            im = cv2.imread(str(f))
            if im is None: continue
            h, w = im.shape[:2]; s = tile / max(h, w)
            im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))))
            r_, c_ = divmod(k, cols)
            grid[r_ * tile:r_ * tile + im.shape[0], c_ * tile:c_ * tile + im.shape[1]] = im
            cv2.putText(grid, f"P{pp:.1f} F{pf:.1f}", (c_ * tile + 3, r_ * tile + tile - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.imwrite(f"{prefix}_{n // per + 1:02d}.jpg", grid)

make_sheets(move, "sheet_move")
make_sheets(review, "sheet_review")
print(f"move hone wale: {len(move)} | review wale: {len(review)} | baqi ambulance rehne wale: {len(rows) - len(move)}")

if APPLY:
    with open(ROOT / "auto_moved_log.csv", "a", newline="") as fh:
        w = csv.writer(fh)
        for sp, f, *_ in move:
            dst = ROOT / sp / DEST; dst.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dst / f.name))
            w.writerow([sp, f.name, "ambulance", DEST])
    print("moved:", len(move))
else:
    print("DRY RUN: kuch move nahi hua. sheet_move_*.jpg aur sheet_review_*.jpg dekho, phir APPLY = True karo.")