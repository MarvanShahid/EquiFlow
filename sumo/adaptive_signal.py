"""
Adaptive traffic-signal controller for a SUMO junction (via TraCI).

Rules (same as the YOLO/video version):
  * One approach is green at a time, max MAX_GREEN seconds.
  * Green approach empty for EMPTY_SECONDS -> switch early.
  * Next approach = first one (North -> South -> East -> West cycle) that has vehicles.
  * Ambulance on any approach -> that approach gets green and keeps it until it is gone.
  * A YELLOW_TIME yellow phase is shown before every change.

All times are SIMULATION seconds (traci.simulation.getTime()).
"""

import os
import sys

if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

import sumolib
import traci

# ============================================================
# 1. SETTINGS  (edit these)
# ============================================================

_HERE = os.path.dirname(os.path.abspath(__file__))
SUMO_CFG = os.path.join(_HERE, "configs", "cross_signal_fixed_medium.sumocfg")
USE_GUI = True
STEP_DELAY_MS = 50           # GUI delay per step so you can watch it

TLS_ID = None                # e.g. "J0". None = auto (works if the net has ONE traffic light)

# Optional manual mapping edge -> direction, if the automatic (geometry) guess is wrong.
# Example: {"N2C": "North", "S2C": "South", "E2C": "East", "W2C": "West"}
EDGE_TO_DIR = {}

DIRECTIONS = ["North", "South", "East", "West"]   # cycle order

# Ambulance = vType id contains one of these words OR vClass is "emergency"
AMBULANCE_WORDS = ("ambulance",)

DETECT_DISTANCE = 120.0      # m from the stop line: vehicles closer than this count as "on the road"
AMB_DETECT_DISTANCE = 150.0  # m from the stop line: ambulance this close triggers priority

MAX_GREEN = 10.0             # max green per approach (s)
EMPTY_SECONDS = 3.0          # empty this long while green -> switch early (s)
YELLOW_TIME = 3.0            # yellow before every change (s)
PRESENCE_HOLD = 1.0          # approach counts as "has cars" if a car was seen in the last N s


# ============================================================
# 2. CONTROLLER
# ============================================================

class SignalController:
    def __init__(self, order, now):
        self.order = list(order)
        self.idx = 0
        self.green_start = now
        self.last_seen = {d: -1e9 for d in self.order}
        self.emergency = False
        self.target = None           # not None -> currently in yellow, heading to target
        self.yellow_until = 0.0
        self._reason = ""
        print(f"[SIGNAL] {self.green} -> GREEN (initial)")

    @property
    def green(self):
        return self.order[self.idx]

    @property
    def in_yellow(self):
        return self.target is not None

    def has_cars(self, d, now):
        return now - self.last_seen[d] <= PRESENCE_HOLD

    def _next_matching(self, predicate):
        n = len(self.order)
        for step in range(1, n):
            d = self.order[(self.idx + step) % n]
            if predicate(d):
                return d
        return None

    def _begin_switch(self, target, now, reason):
        self.target = target
        self.yellow_until = now + YELLOW_TIME
        self._reason = reason
        print(f"[SIGNAL t={now:6.1f}] {self.green} -> YELLOW (next: {target}, {reason})")

    def update(self, now, counts, ambulance_dirs):
        for d, n in counts.items():
            if n > 0:
                self.last_seen[d] = now

        # ---- yellow phase running ----
        if self.in_yellow:
            if now >= self.yellow_until:
                self.idx = self.order.index(self.target)
                self.target = None
                self.green_start = now
                print(f"[SIGNAL t={now:6.1f}] {self.green} -> GREEN ({self._reason})")
            return

        cur = self.green

        # ---- 1. ambulance priority ----
        if ambulance_dirs:
            self.emergency = True
            if cur in ambulance_dirs:
                return                                   # hold green
            self._begin_switch(self._next_matching(lambda d: d in ambulance_dirs),
                               now, "AMBULANCE")
            return

        if self.emergency:                               # ambulance just cleared
            self.emergency = False
            self.green_start = now
            print(f"[SIGNAL t={now:6.1f}] Ambulance cleared on {cur}, resuming normal cycle")

        # ---- 2. normal rules ----
        elapsed = now - self.green_start
        empty_for = now - max(self.last_seen[cur], self.green_start)

        if elapsed >= MAX_GREEN or empty_for >= EMPTY_SECONDS:
            target = self._next_matching(lambda d: self.has_cars(d, now))
            if target is not None:
                reason = "time up" if elapsed >= MAX_GREEN else f"road empty {EMPTY_SECONDS:.0f}s"
                self._begin_switch(target, now, reason)
            # nobody waiting -> stay green and check again next step


# ============================================================
# 3. SUMO HELPERS
# ============================================================

def heading_dir(lane_id):
    """Which side of the junction does traffic on this incoming lane come FROM?"""
    (x1, y1), (x2, y2) = traci.lane.getShape(lane_id)[-2:]
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) > abs(dy):
        return "East" if dx < 0 else "West"      # moving west  -> arrives from the East
    return "North" if dy < 0 else "South"        # moving south -> arrives from the North


def discover(tls):
    """Return (n_links, {dir: [signal indices]}, {dir: set(incoming edges)})."""
    links = traci.trafficlight.getControlledLinks(tls)
    idx = {d: [] for d in DIRECTIONS}
    edges = {d: set() for d in DIRECTIONS}
    for i, group in enumerate(links):
        if not group:
            continue
        in_lane = group[0][0]
        edge = traci.lane.getEdgeID(in_lane)
        d = EDGE_TO_DIR.get(edge) or heading_dir(in_lane)
        idx[d].append(i)
        edges[d].add(edge)
    return len(links), idx, edges


def is_ambulance(veh):
    if any(w in traci.vehicle.getTypeID(veh).lower() for w in AMBULANCE_WORDS):
        return True
    return traci.vehicle.getVehicleClass(veh) == "emergency"


_lane_len = {}


def dist_to_stopline(veh):
    lane = traci.vehicle.getLaneID(veh)
    if lane not in _lane_len:
        _lane_len[lane] = traci.lane.getLength(lane)
    return _lane_len[lane] - traci.vehicle.getLanePosition(veh)


def observe(edges):
    """Vehicle count and ambulance presence for every approach."""
    counts, amb_dirs = {}, set()
    for d, es in edges.items():
        n = 0
        for e in es:
            for veh in traci.edge.getLastStepVehicleIDs(e):
                dist = dist_to_stopline(veh)
                if dist <= DETECT_DISTANCE:
                    n += 1
                if dist <= AMB_DETECT_DISTANCE and is_ambulance(veh):
                    amb_dirs.add(d)
        counts[d] = n
    return counts, amb_dirs


def make_state(n_links, idx, green_dir, yellow=False):
    s = ["r"] * n_links
    for i in idx[green_dir]:
        s[i] = "y" if yellow else "G"
    return "".join(s)


# ============================================================
# 4. MAIN
# ============================================================

def main():
    binary = sumolib.checkBinary("sumo-gui" if USE_GUI else "sumo")
    traci.start([binary, "-c", SUMO_CFG, "--start", "--quit-on-end",
                 "--delay", str(STEP_DELAY_MS)])

    try:
        tls_list = traci.trafficlight.getIDList()
        print("Traffic lights in network:", list(tls_list))
        tls = TLS_ID or (tls_list[0] if len(tls_list) == 1 else None)
        if tls is None:
            raise SystemExit("Several traffic lights found - set TLS_ID at the top of the file.")

        n_links, idx, edges = discover(tls)
        order = [d for d in DIRECTIONS if idx[d]]
        print(f"Controlling '{tls}' with {n_links} signal links")
        for d in order:
            print(f"  {d:5s}: edges={sorted(edges[d])}  signal indices={idx[d]}")
        print("  vehicle types in routes:", list(traci.vehicletype.getIDList()))
        if len(order) < 2:
            raise SystemExit("Could not map approaches to directions - fill EDGE_TO_DIR.")

        # switch off SUMO's own program; we set the state every step
        traci.trafficlight.setProgram(tls, "off")

        controller = SignalController(order, traci.simulation.getTime())

        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            now = traci.simulation.getTime()

            counts, amb_dirs = observe(edges)
            controller.update(now, counts, amb_dirs)

            state = make_state(n_links, idx, controller.green, yellow=controller.in_yellow)
            traci.trafficlight.setRedYellowGreenState(tls, state)

            if int(now) % 10 == 0 and abs(now - round(now)) < 1e-6:
                print(f"[t={now:6.1f}] green={controller.green:5s} counts={counts} "
                      f"ambulance={sorted(amb_dirs) or '-'}")
    finally:
        traci.close()
        print("Simulation closed.")


if __name__ == "__main__":
    main()
