import shutil
from pathlib import Path
d = Path(r"C:\Smester7\Projects\crops\train\ambulance")
for f in list(d.glob("local_amb_*.jpg")):
    if "_r1" in f.stem or "_r2" in f.stem: continue
    for k in (1, 2):
        shutil.copy(f, d / f"{f.stem}_r{k}.jpg")