"""Make the vision pipeline run on machines where parts of the GPU stack cannot be loaded.

Windows Smart App Control (and similar application-control policies) can block unsigned native extensions. On
the development laptop it blocks two of them:

  * torchvision's CUDA extension (`_C_stable.pyd`), so torch is the CUDA build but torchvision the CPU build,
    which has no CUDA kernel for `torchvision::nms`. Ultralytics calls that op on GPU tensors.
  * the `lap` package's `_lapjv` extension, which ByteTrack uses for track/detection matching.

`apply()` fixes only what is actually broken here, and changes nothing on a normal installation:

  * lap cannot be imported   -> ByteTrack uses Ultralytics' own SciPy assignment (`use_lap=False`); a stand-in
                                module stops Ultralytics from trying to pip-install lap again.
  * no CUDA kernel for nms   -> Ultralytics' pure-PyTorch NMS (`TorchNMS.nms`, documented to give the same
                                result as torchvision) is registered as that kernel.

It is process-local (no site-packages hooks) and idempotent. Call it before the first `ultralytics` import that
tracks or predicts; `vision/live.py` and the scripts in `Projects/` do.
"""
from __future__ import annotations

import logging
import sys
import types

log = logging.getLogger("equiflow.gpu_compat")

_applied: dict | None = None
_keep: list = []            # keeps a torch.library registration alive for the life of the process


def _lap_ok() -> bool:
    try:
        import lap  # noqa: F401
        return bool(getattr(lap, "__version__", None))
    except Exception:  # noqa: BLE001 - ImportError, or OSError when a policy blocks the DLL
        sys.modules.pop("lap", None)
        return False


def _fix_lap() -> str:
    if "lap" in sys.modules and getattr(sys.modules["lap"], "__equiflow_stub__", False):
        return "scipy fallback"
    if _lap_ok():
        return "lap"
    # the stand-in must be in place BEFORE Ultralytics' matching module is imported: that module imports lap at
    # load time and, if it fails, tries to pip-install it
    stub = types.ModuleType("lap")
    stub.__version__ = "0.0 (stand-in: scipy fallback)"
    stub.__equiflow_stub__ = True

    def lapjv(*_a, **_k):        # never called: linear_assignment is switched to use_lap=False below
        raise RuntimeError("lap is not available; ByteTrack uses the SciPy fallback")

    stub.lapjv = lapjv
    sys.modules["lap"] = stub
    try:
        from ultralytics.trackers.utils import matching
    except ImportError:          # no (real) ultralytics: nothing will track
        sys.modules.pop("lap", None)
        return "unchanged (no ultralytics)"
    matching.linear_assignment.__defaults__ = (False,)
    return "scipy fallback"


def _fix_nms() -> str:
    try:
        import torch
    except Exception:  # noqa: BLE001
        return "no torch"
    if not torch.cuda.is_available():
        return "cpu"
    try:
        import torchvision
        boxes = torch.tensor([[0.0, 0.0, 10.0, 10.0], [1.0, 1.0, 11.0, 11.0]], device="cuda")
        torchvision.ops.nms(boxes, torch.tensor([0.9, 0.8], device="cuda"), 0.5)
        return "torchvision"
    except NotImplementedError:
        pass                     # CPU torchvision under CUDA torch: register a CUDA kernel below
    except Exception as e:  # noqa: BLE001 - torchvision unusable for another reason: leave it to Ultralytics
        log.warning("torchvision NMS check failed (%s); leaving NMS unchanged", e)
        return f"unchanged ({type(e).__name__})"
    try:
        from ultralytics.utils.nms import TorchNMS
    except ImportError:          # no (real) ultralytics, e.g. the stand-in models in the tests
        return "unchanged (no ultralytics)"
    lib = torch.library.Library("torchvision", "IMPL")
    lib.impl("nms", lambda b, s, iou: TorchNMS.nms(b, s, iou), "CUDA")
    _keep.append(lib)
    return "ultralytics TorchNMS (CUDA)"


def apply() -> dict:
    """Apply the fixes this machine needs; returns what was used, e.g. {"tracker": "lap", "nms": "torchvision"}."""
    global _applied
    if _applied is not None:
        return _applied
    _applied = {"tracker": _fix_lap(), "nms": _fix_nms()}
    if _applied["tracker"] != "lap" or not _applied["nms"].startswith(("torchvision", "cpu")):
        log.info("GPU compatibility: tracker matching=%s, NMS=%s", _applied["tracker"], _applied["nms"])
    return _applied
