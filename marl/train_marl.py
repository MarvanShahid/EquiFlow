"""
train_marl.py - train the fairness-aware multi-agent RL signal controller in SUMO.

One agent per signalised junction, all sharing one Q-network (backend/app/controllers/marl.py).
Episodes cycle through the training networks and demand levels; each episode is a headless SUMO
run in which every junction is driven by IntersectionController with the learning MARL base
controller under it, so ambulance priority and safety timing are active during training too.

  python marl/train_marl.py --episodes 40            # continues from the saved weights if present
  python marl/train_marl.py --episodes 40 --fresh    # start over

Weights: marl/weights/marl_policy.npz   Log: marl/training_log.csv
Evaluate afterwards with:  python sumo/run_equiflow.py --all --base marl
"""
import argparse
import csv
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EQ = ROOT.parent
sys.path.insert(0, str(EQ / "backend"))

from app.bus import EventBus  # noqa: E402
from app.config import load_config  # noqa: E402
from app.controllers.marl import Learner, QNet  # noqa: E402
from app.sumo_live import SUMO_DIR, SumoLive, build_geometry  # noqa: E402

TRAIN = [("cross_signal", "high"), ("sector_grid", "high"), ("five_way_signal", "medium"), ("t_signal", "high"),
         ("diamond", "high"), ("six_way", "medium"), ("cross_signal", "asymmetric"), ("sector_grid", "medium")]
WEIGHTS = ROOT / "weights" / "marl_policy.npz"
LOG = ROOT / "training_log.csv"


def episode(cfg, learner, net_name, scen, seed, end_s):
    sim = SumoLive(cfg, EventBus(history=20))
    if not sim.available:
        sys.exit(sim.reason)
    net = SUMO_DIR / "networks" / f"{net_name}_fixed.net.xml"
    rou = SUMO_DIR / "routes" / f"{net_name}_{scen}.rou.xml"
    trip = ROOT / "weights" / "_train_tripinfo.xml"
    sim.headless, sim.tripinfo, sim.step_override, sim.end_s = True, trip, 1.0, end_s
    sim.marl_extra = {"learner": learner, "seed": seed}
    sim.run = {"network": net_name, "scenario": scen, "controller": "equiflow", "seed": seed, "speed": 1.0,
               "base": "marl"}
    sim._worker(net, rou, build_geometry(net), dict(sim.run), sim._stop)
    if sim.state == "error":
        raise RuntimeError(sim.error)
    waits = {"all": [], "ambulance": []}
    for t in ET.parse(trip).getroot().findall("tripinfo"):
        w = float(t.get("waitingTime"))
        waits["all"].append(w)
        if t.get("vType") == "ambulance":
            waits["ambulance"].append(w)
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else ""  # noqa: E731
    return mean(waits["all"]), mean(waits["ambulance"]), len(waits["all"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--end", type=float, default=1800, help="simulated seconds per episode")
    ap.add_argument("--eps-start", type=float, default=0.3)
    ap.add_argument("--eps-end", type=float, default=0.03)
    ap.add_argument("--eps-decay", type=int, default=60, help="episodes over which exploration decays")
    a = ap.parse_args()

    cfg = load_config()
    done = 0
    if WEIGHTS.is_file() and not a.fresh:
        net, meta = QNet.load(WEIGHTS)
        done = int(meta.get("episodes", 0))
        print(f"continuing from {WEIGHTS.name} after {done} episodes")
    else:
        net = QNet(seed=0)
    learner = Learner(net, seed=done)
    new_log = done == 0 or not LOG.exists()
    with LOG.open("w" if new_log else "a", newline="") as fh:   # a fresh start overwrites the old log
        w = csv.writer(fh)
        if new_log:
            w.writerow(["episode", "network", "scenario", "epsilon", "mean_wait_s", "ambulance_wait_s",
                        "trips", "updates", "loss", "seconds"])
        for k in range(a.episodes):
            ep = done + k
            frac = min(1.0, ep / max(1, a.eps_decay))
            learner.epsilon = a.eps_start + (a.eps_end - a.eps_start) * frac
            net_name, scen = TRAIN[ep % len(TRAIN)]
            t0 = time.time()
            mw, aw, n = episode(cfg, learner, net_name, scen, seed=1 + ep % 5, end_s=a.end)
            loss = round(sum(learner.losses) / len(learner.losses), 4) if learner.losses else ""
            row = [ep + 1, net_name, scen, round(learner.epsilon, 3), mw, aw, n, learner.updates, loss,
                   round(time.time() - t0, 1)]
            w.writerow(row)
            fh.flush()
            net.save(WEIGHTS, episodes=ep + 1)
            print(f"ep {ep + 1:3d} {net_name:15s} {scen:10s} eps={learner.epsilon:.2f} wait={mw} amb={aw} "
                  f"updates={learner.updates} loss={loss}")
    print("saved", WEIGHTS)


if __name__ == "__main__":
    main()
