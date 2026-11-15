import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent  # the Projects folder

ROOT = HERE / "crops"
OUT = HERE / "crops_misplaced"
KNOWN = ("pub_", "pk_", "local_", "web_")
DRY = False            # pehle True, theek lage to False

n = 0
for sp in ("train", "val", "test"):
    for f in sorted((ROOT / sp / "ambulance").iterdir()):
        if not f.is_file() or f.name.startswith(KNOWN) or ".rf." in f.name:
            continue
        n += 1
        print(("DRY " if DRY else "") + f"{sp}/{f.name}")
        if not DRY:
            d = OUT / sp; d.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(d / f.name))
print("kul files:", n)