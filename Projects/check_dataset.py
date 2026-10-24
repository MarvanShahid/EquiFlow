
from pathlib import Path
import random
import cv2
import numpy as np

ROOT = Path(r"C:\Smester7\Projects\equiflow_det")
random.seed(42)

for src in ["d1", "d2", "d3", "d4", "d5", "d6"]:
    label_files = sorted(
        (ROOT / "labels" / "train").glob(f"{src}_*.txt")
    )

    if not label_files:
        print(f"{src}: no training labels found")
        continue

    tiles = []

    for label_file in random.sample(
        label_files, min(6, len(label_files))
    ):
        matches = list(
            (ROOT / "images" / "train").glob(label_file.stem + ".*")
        )

        if not matches:
            print("Missing image:", label_file.name)
            continue

        img = cv2.imread(str(matches[0]))
        if img is None:
            print("Unreadable image:", matches[0])
            continue

        H, W = img.shape[:2]

        for line in label_file.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                print("Invalid label:", label_file.name, line)
                continue

            c = int(parts[0])
            x, y, w, h = map(float, parts[1:])

            color = (0, 0, 255) if c == 0 else (0, 255, 0)

            x1 = int((x - w / 2) * W)
            y1 = int((y - h / 2) * H)
            x2 = int((x + w / 2) * W)
            y2 = int((y + h / 2) * H)

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

        tiles.append(cv2.resize(img, (320, 240)))

    if not tiles:
        continue

    while len(tiles) % 3:
        tiles.append(np.zeros((240, 320, 3), dtype=np.uint8))

    rows = [
        np.hstack(tiles[i:i+3])
        for i in range(0, len(tiles), 3)
    ]

    out = Path(f"final_check_{src}.jpg")
    cv2.imwrite(str(out), np.vstack(rows))

    print(f"Saved: {out.resolve()}")
    print(f"{src}: {len(label_files)} labeled training images")