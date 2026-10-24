import shutil
from pathlib import Path

ROOT = Path(r"C:\Smester7\Projects\crops")
KNOWN = ("pub_", "pk_", "local_", "web_")
DRY = False            # pehle True, theek lage to False
REPEAT = 2            # har nayi image train mein kitni martaba (copies ke saath)

counts = {"train": 0, "val": 0, "test": 0}
dst = ROOT / "train" / "ambulance"
for sp in ("train", "val", "test"):
    for f in sorted((ROOT / sp / "ambulance").iterdir()):
        if not f.is_file() or f.name.startswith(KNOWN) or ".rf." not in f.name:
            continue                      # Kaggle ki poori tasveerein (bina .rf.) ko nahi chhoota
        counts[sp] += 1
        ext = f.suffix.lower()
        first = dst / ("web_" + f.stem + ext)
        extras = [dst / f"web_{f.stem}_r{k}{ext}" for k in range(1, REPEAT)]
        print(("DRY " if DRY else "") + f"{sp}/{f.name[:40]}... -> train (x{REPEAT})")
        if not DRY:
            shutil.move(str(f), str(first))
            for o in extras:
                shutil.copy(str(first), str(o))
print("Roboflow images, jahan se aayin:", counts, "| kul:", sum(counts.values()))