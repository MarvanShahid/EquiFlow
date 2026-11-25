"""vision/gpu_compat.py: the fallbacks used when an application-control policy blocks lap or torchvision's CUDA ops."""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("ultralytics")


@pytest.fixture(autouse=True)
def _real_ultralytics():
    # test_live_pipeline.py swaps in a stand-in `ultralytics` module while the tests are collected
    if not hasattr(sys.modules.get("ultralytics"), "__version__"):
        pytest.skip("real ultralytics not loaded in this process (stand-in module from another test)")


def _fresh():
    from app.vision import gpu_compat
    return importlib.reload(gpu_compat)


def test_blocked_lap_switches_bytetrack_to_the_scipy_fallback(monkeypatch):
    from ultralytics.trackers.utils import matching
    old_defaults, old_lap = matching.linear_assignment.__defaults__, sys.modules.get("lap")
    monkeypatch.setitem(sys.modules, "lap", None)    # makes `import lap` raise ImportError, like a blocked DLL
    try:
        gc = _fresh()
        assert gc._fix_lap() == "scipy fallback"
        assert getattr(sys.modules["lap"], "__equiflow_stub__", False)
        assert matching.linear_assignment.__defaults__ == (False,)
        cost = [[0.1, 0.9], [0.8, 0.2]]
        import numpy as np
        m, ua, ub = matching.linear_assignment(np.array(cost), thresh=0.5)
        assert sorted(map(tuple, np.asarray(m).tolist())) == [(0, 0), (1, 1)] and not ua and not ub
    finally:
        matching.linear_assignment.__defaults__ = old_defaults
        if old_lap is not None:
            sys.modules["lap"] = old_lap
        else:
            sys.modules.pop("lap", None)


def test_working_lap_is_left_alone():
    pytest.importorskip("lap")
    gc = _fresh()
    assert gc._fix_lap() == "lap"


def test_apply_is_idempotent_and_reports_what_it_used():
    gc = _fresh()
    a = gc.apply()
    assert set(a) == {"tracker", "nms"} and gc.apply() is a


def test_cuda_nms_fallback_matches_cpu_nms():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("no CUDA GPU")
    import torchvision
    _fresh().apply()
    g = torch.Generator().manual_seed(0)
    b = torch.rand(300, 4, generator=g) * 100
    b[:, 2:] += b[:, :2]
    s = torch.rand(300, generator=g)
    keep_gpu = torchvision.ops.nms(b.cuda(), s.cuda(), 0.5).cpu()
    assert torch.equal(keep_gpu, torchvision.ops.nms(b, s, 0.5))
