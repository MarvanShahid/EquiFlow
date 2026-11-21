"""make_split_manifest.py - dataset split manifest + leakage check (mid-report acceptance criterion
"splits documented and free of duplicate source images across train/val/test", deliverable "split manifests").

For every crop in crops/{train,val,test}/{ambulance,other_vehicle}:
  * writes one manifest row: split, class, source (file prefix pub_/pk_/local_), file, size, SHA-1, 64-bit dHash
  * finds EXACT duplicates (same SHA-1) that appear in two different splits
  * finds NEAR duplicates (dHash Hamming distance <= --max-dist, also checking the left-right mirror)
    between val/test and train, i.e. the same vehicle shot leaking into evaluation
  * checks class folder names are the two expected classes

    cd Projects
    python make_split_manifest.py                       # -> crops_manifest.csv, split_report.md, split_duplicates.csv
    python make_split_manifest.py --data C:\\Smester7\\Projects\\crops --max-dist 6

Needs Pillow and numpy only (no GPU).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
SPLITS = ("train", "val", "test")
CLASSES = ("ambulance", "other_vehicle")
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def dhash(im: Image.Image, size: int = 8) -> int:
    g = np.asarray(im.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def popcount64(x: np.ndarray) -> np.ndarray:
    return np.unpackbits(x.view(np.uint8).reshape(-1, 8), axis=1).sum(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(HERE / "crops"))
    ap.add_argument("--max-dist", type=int, default=4, help="dHash Hamming distance counted as a near duplicate")
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    root, out = Path(a.data), Path(a.out)

    problems = []
    found = {p.name for s in SPLITS if (root / s).is_dir() for p in (root / s).iterdir() if p.is_dir()}
    if not found:
        raise SystemExit(f"No split folders under {root}")
    if found - set(CLASSES):
        problems.append(f"unexpected class folders: {sorted(found - set(CLASSES))}")

    rows = []
    for s in SPLITS:
        for c in CLASSES:
            d = root / s / c
            if not d.is_dir():
                problems.append(f"missing folder {s}/{c}")
                continue
            for f in sorted(d.iterdir()):
                if f.suffix.lower() not in EXTS:
                    continue
                b = f.read_bytes()
                try:
                    with Image.open(f) as im:
                        im = im.convert("RGB")
                        w, h = im.size
                        dh, dm = dhash(im), dhash(ImageOps.mirror(im))
                except Exception as e:  # noqa: BLE001
                    problems.append(f"unreadable image {f}: {e}")
                    continue
                src = f.stem.split("_", 1)[0] if "_" in f.stem else "other"
                rows.append({"split": s, "class": c, "source": src, "file": f"{s}/{c}/{f.name}", "width": w,
                             "height": h, "bytes": len(b), "sha1": hashlib.sha1(b).hexdigest(),
                             "dhash": f"{dh:016x}", "_dm": dm})
        print(f"{s}: {sum(r['split'] == s for r in rows)} images")

    with open(out / "crops_manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[k for k in rows[0] if not k.startswith("_")], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # exact duplicates across splits
    by_sha: dict[str, list[dict]] = {}
    for r in rows:
        by_sha.setdefault(r["sha1"], []).append(r)
    exact = [g for g in by_sha.values() if len({r["split"] for r in g}) > 1]
    label_conflicts = [g for g in by_sha.values() if len({r["class"] for r in g}) > 1]

    # near duplicates: val/test vs train
    train = [r for r in rows if r["split"] == "train"]
    T = np.array([int(r["dhash"], 16) for r in train], dtype=np.uint64)
    near = []
    for r in rows:
        if r["split"] == "train" or not len(T):
            continue
        best_d, best_j = 65, -1
        for h in (int(r["dhash"], 16), r["_dm"]):
            d = popcount64(T ^ np.uint64(h))
            j = int(d.argmin())
            if d[j] < best_d:
                best_d, best_j = int(d[j]), j
        if best_d <= a.max_dist:
            near.append({"split": r["split"], "file": r["file"], "train_file": train[best_j]["file"],
                         "hamming": best_d, "same_class": r["class"] == train[best_j]["class"]})
    with open(out / "split_duplicates.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "split", "file", "train_file", "hamming", "same_class"])
        w.writeheader()
        for g in exact:
            for r in g[1:]:
                w.writerow({"kind": "exact", "split": r["split"], "file": r["file"], "train_file": g[0]["file"],
                            "hamming": 0, "same_class": r["class"] == g[0]["class"]})
        for n in near:
            w.writerow({"kind": "near", **n})

    cnt = Counter((r["split"], r["class"]) for r in rows)
    src = Counter((r["split"], r["class"], r["source"]) for r in rows)
    L = ["# Crops dataset: split manifest and leakage check", "",
         f"Folder `{root}`; {len(rows)} images. Full list with SHA-1 and dHash: `crops_manifest.csv`.", "",
         "| Split | ambulance | other_vehicle | total | ambulance share |", "|---|---|---|---|---|"]
    for s in SPLITS:
        am, ot = cnt[(s, "ambulance")], cnt[(s, "other_vehicle")]
        L.append(f"| {s} | {am} | {ot} | {am + ot} | {100 * am / max(1, am + ot):.1f}% |")
    L += ["", "| Split | class | source | images |", "|---|---|---|---|"]
    L += [f"| {s} | {c} | {so} | {n} |" for (s, c, so), n in sorted(src.items())]
    near_test = sum(n["split"] == "test" for n in near)
    near_val = sum(n["split"] == "val" for n in near)
    L += ["", "## Leakage", "",
          f"- Exact duplicate files shared between splits: **{sum(len(g) - 1 for g in exact)}**",
          f"- Identical files with different labels: **{len(label_conflicts)}**",
          f"- Near duplicates of a train image (dHash distance <= {a.max_dist}, mirror included, exact ones included): "
          f"**{near_val}** in val, **{near_test}** in test "
          f"({100 * near_test / max(1, sum(r['split'] == 'test' for r in rows)):.1f}% of test)",
          "", "Details: `split_duplicates.csv`. Near duplicates are candidates: open a few pairs to confirm they are "
          "the same vehicle and frame before removing them from val/test."]
    if problems:
        L += ["", "## Problems", ""] + [f"- {p}" for p in problems]
    (out / "split_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
