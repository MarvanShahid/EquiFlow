"""
run_sim.py - run any intersection built by build_islamabad.py and report metrics PER VEHICLE CLASS
(car / motorcycle / bus / truck / ambulance).

  python run_sim.py --intersection roundabout --controller actuated --scenario high
  python run_sim.py --intersection diamond --preempt --gui          # ambulance signal pre-emption, watch in GUI
  python run_sim.py --all                                           # every intersection x controller x scenario
"""
import argparse, csv, itertools, os, shutil, sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NETS = ["cross_signal", "t_signal", "t_priority", "y_junction", "five_way_signal", "roundabout", "sector_grid", "diamond"]
SCENS = ["low", "medium", "high", "asymmetric"]
ap = argparse.ArgumentParser()
ap.add_argument("--intersection", choices=NETS, default="cross_signal")
ap.add_argument("--controller", choices=["fixed", "actuated"], default="fixed")
ap.add_argument("--scenario", choices=SCENS, default="medium")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--preempt", action="store_true", help="give ambulances a green wave at signals (TraCI)")
ap.add_argument("--preempt-dist", type=float, default=80.0, help="metres before stop line to trigger pre-emption")
ap.add_argument("--gui", action="store_true")
ap.add_argument("--all", action="store_true")
args = ap.parse_args()

# --------------------------------------------------------------------------- SUMO discovery
def sumo_home():
    h = os.environ.get("SUMO_HOME")
    if h and Path(h).is_dir():
        return Path(h)
    try:
        import sumo
        return Path(sumo.SUMO_HOME)
    except Exception:
        pass
    for p in (r"C:\Program Files (x86)\Eclipse\Sumo", r"C:\Program Files\Eclipse\Sumo", r"C:\Program Files (x86)\SUMO"):
        if Path(p).is_dir():
            return Path(p)
    sys.exit("SUMO not found. Set SUMO_HOME.")

HOME = sumo_home()
sys.path.insert(0, str(HOME / "tools"))
import traci  # noqa: E402

def exe(n):
    e = n + (".exe" if os.name == "nt" else "")
    return shutil.which(e) or str(HOME / "bin" / e)

# --------------------------------------------------------------------------- one simulation
def simulate(inter, ctrl, scen, seed, preempt, gui, pdist):
    net = ROOT / "networks" / f"{inter}_{ctrl}.net.xml"
    rou = ROOT / "routes" / f"{inter}_{scen}.rou.xml"
    vt = ROOT / "routes" / "vtypes.add.xml"
    if not (net.is_file() and rou.is_file()):
        sys.exit("Missing network/routes - run: python build_islamabad.py")
    tag = f"{inter}_{ctrl}{'+preempt' if preempt else ''}_{scen}"
    out = ROOT / "results"
    tripinfo = out / f"tripinfo_{tag}.xml"
    cmd = [exe("sumo-gui" if gui else "sumo"), "-n", net, "-r", rou, "--begin", "0", "--end", "3600",
           "--seed", seed, "--no-step-log", "true", "--waiting-time-memory", "10000",
           "--tripinfo-output", tripinfo, "--time-to-teleport", "-1"]
    cmd = [str(c) for c in cmd]
    if gui:
        cmd += ["--start", "true", "--delay", "40"]
    traci.start(cmd)

    stopped_by_class = defaultdict(int)       # sum of stopped-vehicle counts per class
    steps = 0
    held = {}                                 # tlsID -> (original program, ambulance id)
    amb_preempts = 0
    try:
        while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < 3600:
            traci.simulationStep()
            steps += 1
            ids = traci.vehicle.getIDList()
            for v in ids:
                if traci.vehicle.getSpeed(v) < 0.1:
                    stopped_by_class[traci.vehicle.getTypeID(v)] += 1

            if preempt:
                active = {}
                for v in ids:
                    if traci.vehicle.getTypeID(v) != "ambulance":
                        continue
                    nxt = traci.vehicle.getNextTLS(v)
                    if nxt and nxt[0][2] < pdist:
                        tls, link_idx, _, state = nxt[0]
                        active[tls] = (v, link_idx)
                for tls, (v, idx) in active.items():
                    if tls not in held:
                        held[tls] = (traci.trafficlight.getProgram(tls), v)
                        amb_preempts += 1
                    n = len(traci.trafficlight.getRedYellowGreenState(tls))
                    st = ["r"] * n
                    st[idx] = "G"                      # only the ambulance's own movement is green; all others red
                    traci.trafficlight.setRedYellowGreenState(tls, "".join(st))
                for tls in [t for t in held if t not in active]:
                    traci.trafficlight.setProgram(tls, held.pop(tls)[0])   # hand control back to the controller
    finally:
        traci.close()

    # ---- per-class metrics from tripinfo
    per = defaultdict(list)
    for t in ET.parse(tripinfo).getroot().findall("tripinfo"):
        per[t.get("vType")].append((float(t.get("duration")), float(t.get("waitingTime")),
                                    float(t.get("timeLoss")), float(t.get("routeLength"))))
    rows = []
    for vtype in ["car", "motorcycle", "bus", "truck", "ambulance"]:
        d = per.get(vtype, [])
        n = len(d)
        avg = lambda i: round(sum(x[i] for x in d) / n, 2) if n else ""
        rows.append({"intersection": inter, "controller": ctrl + ("+preempt" if preempt else ""), "scenario": scen,
                     "seed": seed, "vehicle_type": vtype, "completed": n, "mean_travel_time_s": avg(0),
                     "mean_waiting_s": avg(1), "mean_time_loss_s": avg(2),
                     "mean_stopped_vehicles": round(stopped_by_class[vtype] / max(steps, 1), 2)})
    if preempt:
        print(f"  ambulance pre-emption events: {amb_preempts}")
    return rows

def save(rows):
    f = ROOT / "results" / "summary_by_class.csv"
    old = list(csv.DictReader(f.open(newline=""))) if f.exists() else []
    key = lambda r: (r["intersection"], r["controller"], r["scenario"], str(r["seed"]), r["vehicle_type"])
    new = {key(r) for r in rows}
    allrows = [r for r in old if key(r) not in new] + rows
    with f.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(allrows)
    return f

if __name__ == "__main__":
    jobs = list(itertools.product(NETS, ["fixed", "actuated"], SCENS)) if args.all else \
        [(args.intersection, args.controller, args.scenario)]
    for inter, ctrl, scen in jobs:
        print(f"Running {inter} / {ctrl} / {scen}{' / preempt' if args.preempt else ''} ...")
        rows = simulate(inter, ctrl, scen, args.seed, args.preempt, args.gui, args.preempt_dist)
        f = save(rows)
        for r in rows:
            print(f"  {r['vehicle_type']:<11} n={r['completed']:<5} travel={r['mean_travel_time_s']:<7} "
                  f"wait={r['mean_waiting_s']:<6} loss={r['mean_time_loss_s']}")
    print("Saved:", f)
