"""Import this before using Ultralytics on the GPU:  `import gpu_compat` (Projects scripts do it already).

It applies backend/app/vision/gpu_compat.py: on a machine where an application-control policy (e.g. Windows Smart
App Control) blocks torchvision's CUDA extension or the `lap` package, NMS falls back to Ultralytics' own
pure-PyTorch NMS on CUDA tensors and ByteTrack to its SciPy assignment. On a normal installation it changes
nothing. Run `python gpu_compat.py` to see what it applied on this machine.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.vision.gpu_compat import apply  # noqa: E402

APPLIED = apply()

if __name__ == "__main__":
    print(APPLIED)
