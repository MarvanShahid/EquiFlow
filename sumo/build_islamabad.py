"""
build_islamabad.py  -  Generic intersection generator for Islamabad (SUMO)

Intersection archetypes (Islamabad is LEFT-HAND traffic, so everything is built with --lefthand):
  cross_signal     4-arm signalised crossing      (Jinnah Ave / Constitution Ave / Kashmir Hwy at-grade junctions)
  t_signal         3-arm signalised T-junction    (sector service roads meeting an avenue)
  t_priority       3-arm unsignalised T           (priority / give-way, typical sector streets)
  y_junction       3-arm unsignalised Y           (merging arterials)
  five_way_signal  5-arm signalised star          (complex multi-road chowks)
  roundabout       4-arm roundabout (chowk)       (many Islamabad / Rawalpindi chowks)
  sector_grid      3x3 signalised grid            (sector-style block grid, e.g. G/F/I sectors)
  diamond          grade-separated diamond        (expressway over/under arterial, Zero-Point / Faizabad style)

Vehicle classes (distinguishable in the GUI by colour + shape, and in the results by vType):
  car (yellow) | motorcycle (cyan) | bus (green) | truck (grey) | ambulance (RED, emergency)

Usage:
  python build_islamabad.py                       # build everything
  python build_islamabad.py --only roundabout diamond
"""
import argparse, os, shutil, subprocess, sys, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for d in ("networks", "routes", "configs", "results", "_tmp"):
    (ROOT / d).mkdir(exist_ok=True)

# --------------------------------------------------------------------------- SUMO discovery
def sumo_home():
    h = os.environ.get("SUMO_HOME")
    if h and Path(h).is_dir():
        return Path(h)
    try:                                   # pip install eclipse-sumo
        import sumo
        return Path(sumo.SUMO_HOME)
    except Exception:
        pass
    for p in (r"C:\Program Files (x86)\Eclipse\Sumo", r"C:\Program Files\Eclipse\Sumo",
              r"C:\Program Files (x86)\SUMO"):
        if Path(p).is_dir():
            return Path(p)
    sys.exit("SUMO not found. Set SUMO_HOME.")

HOME = sumo_home()

def find_exe(name):
    exe = name + (".exe" if os.name == "nt" else "")
    return shutil.which(exe) or (str(HOME / "bin" / exe) if (HOME / "bin" / exe).is_file() else None) \
        or sys.exit(f"Cannot find {exe}")

NETCONVERT, NETGENERATE, DUAROUTER = map(find_exe, ("netconvert", "netgenerate", "duarouter"))
RANDOM_TRIPS = HOME / "tools" / "randomTrips.py"
if not RANDOM_TRIPS.is_file():
    sys.exit(f"randomTrips.py not found under {HOME}/tools")

def run(cmd):
    cmd = [str(c) for c in cmd]
    print(">", subprocess.list2cmdline(cmd))
    subprocess.run(cmd, check=True)

# --------------------------------------------------------------------------- network builders
def pt(r, compass_deg):                    # compass angle: 0 = north, clockwise
    a = math.radians(compass_deg)
    return r * math.sin(a), r * math.cos(a)

def write_plain(name, nodes, edges, extra_conn=None):
    """nodes: (id,x,y,type)   edges: (id,from,to,lanes,speed,priority,shape|None)"""
    d = ROOT / "_tmp"
    with (d / f"{name}.nod.xml").open("w") as f:
        f.write("<nodes>\n")
        for i, x, y, t in nodes:
            f.write(f'  <node id="{i}" x="{x:.2f}" y="{y:.2f}" type="{t}"/>\n')
        f.write("</nodes>\n")
    with (d / f"{name}.edg.xml").open("w") as f:
        f.write("<edges>\n")
        for i, a, b, n, v, p, shp in edges:
            s = f' shape="{shp}"' if shp else ""
            f.write(f'  <edge id="{i}" from="{a}" to="{b}" numLanes="{n}" speed="{v}" priority="{p}"{s}/>\n')
        f.write("</edges>\n")
    return d / f"{name}.nod.xml", d / f"{name}.edg.xml"

def netconvert(name, nod, edg, controller, extra=()):
    out = ROOT / "networks" / f"{name}_{controller}.net.xml"
    tls = "static" if controller == "fixed" else "actuated"
    run([NETCONVERT, "-n", nod, "-e", edg, "-o", out, "--lefthand", "true",
         "--no-turnarounds", "true", "--tls.default-type", tls,
         "--junctions.corner-detail", "5", "--default.junctions.radius", "6", *extra])
    return out

def build_star(name, arms, ctrl, lanes, speed, radius=300, roundabout=False):
    """Generic N-arm junction. arms = compass angles in degrees. Used for cross/T/Y/5-way/roundabout."""
    nodes, edges = [], []
    node_type = {"signal": "traffic_light", "priority": "priority", "roundabout": "priority"}[ctrl]
    ring_r = 28
    if roundabout:
        # LHT roundabouts circulate CLOCKWISE (increasing compass angle)
        ring = sorted(arms)
        for a in ring:
            x, y = pt(ring_r, a)
            nodes.append((f"R{a}", x, y, "priority"))
        for k, a in enumerate(ring):
            b = ring[(k + 1) % len(ring)]
            span = (b - a) % 360 or 360
            shp = " ".join("%.2f,%.2f" % pt(ring_r, a + span * t / 4) for t in (1, 2, 3))
            edges.append((f"ring{a}", f"R{a}", f"R{b}", 1, 8.33, 5, shp))
        hub = lambda a: f"R{a}"
    else:
        nodes.append(("C", 0.0, 0.0, node_type))
        hub = lambda a: "C"
    for a in arms:
        x, y = pt(radius, a)
        nodes.append((f"A{a}", x, y, "priority"))
        edges.append((f"in{a}", f"A{a}", hub(a), lanes, speed, 9, None))
        edges.append((f"out{a}", hub(a), f"A{a}", lanes, speed, 9, None))
    return nodes, edges

def build_diamond():
    """Grade-separated diamond: expressway (E-W, separate carriageways) crossing an arterial (N-S) with NO shared
    node; arterial joined to expressway only through ramps that end in signalised ramp-terminals JN / JS."""
    N = [("XWi", -600, 8, "priority"), ("DE1", -250, 8, "priority"), ("DE2", 250, 8, "priority"), ("XEo", 600, 8, "priority"),
         ("XEi", 600, -8, "priority"), ("DW1", 250, -8, "priority"), ("DW2", -250, -8, "priority"), ("XWo", -600, -8, "priority"),
         ("AS", 0, -450, "priority"), ("JS", 0, -80, "traffic_light"),
         ("JN", 0, 80, "traffic_light"), ("AN", 0, 450, "priority")]
    ex = lambda i, a, b: (i, a, b, 3, 22.22, 10, None)
    ar = lambda i, a, b: (i, a, b, 2, 16.67, 8, None)
    rp = lambda i, a, b: (i, a, b, 1, 13.89, 6, None)
    E = [ex("exE0", "XWi", "DE1"), ex("exE1", "DE1", "DE2"), ex("exE2", "DE2", "XEo"),
         ex("exW0", "XEi", "DW1"), ex("exW1", "DW1", "DW2"), ex("exW2", "DW2", "XWo"),
         ar("arS_in", "AS", "JS"), ar("arS_out", "JS", "AS"),
         ar("arC_n", "JS", "JN"), ar("arC_s", "JN", "JS"),          # passes OVER expressway, no junction
         ar("arN_in", "AN", "JN"), ar("arN_out", "JN", "AN"),
         rp("rampE_off", "DE1", "JN"), rp("rampE_on", "JN", "DE2"),  # eastbound = left/north side (LHT)
         rp("rampW_off", "DW1", "JS"), rp("rampW_on", "JS", "DW2")]
    return N, E

NETWORKS = {   # name -> (builder kind, kwargs)
    "cross_signal":    ("star", dict(arms=[0, 90, 180, 270], ctrl="signal", lanes=3, speed=16.67)),
    "t_signal":        ("star", dict(arms=[0, 90, 270], ctrl="signal", lanes=2, speed=13.89)),
    "t_priority":      ("star", dict(arms=[0, 90, 270], ctrl="priority", lanes=1, speed=11.11)),
    "y_junction":      ("star", dict(arms=[0, 120, 240], ctrl="priority", lanes=2, speed=13.89)),
    "five_way_signal": ("star", dict(arms=[0, 72, 144, 216, 288], ctrl="signal", lanes=2, speed=13.89)),
    "roundabout":      ("star", dict(arms=[0, 90, 180, 270], ctrl="roundabout", lanes=2, speed=13.89, roundabout=True)),
    "sector_grid":     ("grid", {}),
    "diamond":         ("diamond", {}),
    "six_way": ("star", dict(arms=[0, 60, 120, 180, 240, 300], ctrl="signal", lanes=2, speed=13.89))
}

def build_network(name, controller):
    kind, kw = NETWORKS[name]
    out = ROOT / "networks" / f"{name}_{controller}.net.xml"
    if kind == "grid":
        run([NETGENERATE, "--grid", "--grid.number", "3", "--grid.length", "300", "--default.lanenumber", "2",
             "--default.speed", "13.89", "--tls.guess", "true", "--lefthand", "true",
             "--tls.default-type", "static" if controller == "fixed" else "actuated", "--output-file", out])
        return out
    if kind == "star":
        nodes, edges = build_star(name, **kw)
    else:
        nodes, edges = build_diamond()
    nod, edg = write_plain(f"{name}_{controller}", nodes, edges)
    extra = ["--roundabouts.guess", "true"] if kw.get("roundabout") else []
    return netconvert(name, nod, edg, controller, extra)

# --------------------------------------------------------------------------- vehicle types
VTYPES = """<additional>
  <vType id="car"        vClass="passenger"  length="4.5" width="1.8" maxSpeed="38" accel="2.6" decel="4.5" sigma="0.5" color="255,220,0"   guiShape="passenger"/>
  <vType id="motorcycle" vClass="motorcycle" length="2.2" width="0.8" maxSpeed="30" accel="3.5" decel="4.5" sigma="0.6" color="0,200,255"   guiShape="motorcycle" latAlignment="arbitrary" minGapLat="0.3"/>
  <vType id="bus"        vClass="bus"        length="12"  width="2.5" maxSpeed="22" accel="1.2" decel="4.0" sigma="0.4" color="0,170,0"     guiShape="bus"/>
  <vType id="truck"      vClass="truck"      length="9"   width="2.5" maxSpeed="20" accel="1.0" decel="4.0" sigma="0.4" color="130,130,130" guiShape="truck"/>
  <vType id="ambulance"  vClass="emergency"  length="5.8" width="2.1" maxSpeed="30" accel="3.0" decel="5.0" sigma="0.2" speedFactor="1.25"
         color="255,0,0" guiShape="emergency" guiWidth="2.3" laneChangeModel="LC2013" lcAssertive="3" lcSpeedGain="3">
  </vType>
</additional>
"""
# share of normal traffic: Pakistani urban mix is motorcycle-heavy
# SUMO's blue-light device makes nearby vehicles pull aside, but on tight junctions (roundabouts, small signalised
# crossings) that caused junction collisions at high demand. It is therefore OFF by default (enable: --bluelight).
BLUELIGHT = False
BLUELIGHT_PARAMS = """    <param key="has.bluelight.device" value="true"/>
    <param key="device.bluelight.reactiondist" value="50"/>
"""
MIX = {"car": 0.62, "motorcycle": 0.25, "bus": 0.06, "truck": 0.07}
VCLASS = {"car": "passenger", "motorcycle": "motorcycle", "bus": "bus", "truck": "truck", "ambulance": "emergency"}
# total normal-vehicle insertion period (s/veh) per scenario, seed, ambulances per hour
SCENARIOS = {"low": (10.0, 11, 6), "medium": (6.0, 22, 10), "high": (3.5, 33, 14), "asymmetric": (5.0, 44, 10)}

def gen_demand(net, name, scen):
    period, seed, n_amb = SCENARIOS[scen]
    vt = ROOT / "routes" / "vtypes.add.xml"
    vt.write_text(VTYPES.replace("  </vType>\n</additional>", (BLUELIGHT_PARAMS if BLUELIGHT else "") + "  </vType>\n</additional>"),
                  encoding="utf-8")
    import xml.etree.ElementTree as ET
    trips = []
    plan = [(t, period / share, 0) for t, share in MIX.items()] + [("ambulance", 3600.0 / n_amb, 1)]
    for k, (vtype, p, is_amb) in enumerate(plan):
        out = ROOT / "_tmp" / f"{name}_{scen}_{vtype}.trips.xml"
        cmd = [sys.executable, RANDOM_TRIPS, "-n", net, "-o", out, "--begin", "0", "--end", "3500",
               "--period", f"{p:.3f}", "--seed", seed + 100 * k, "--prefix", f"{vtype}_",
               "--trip-attributes", f'type="{vtype}"',
               "--additional-files", vt, "--validate"]
        if scen == "asymmetric":
            cmd += ["--fringe-factor", "10"]
        if is_amb:
            cmd += ["--min-distance", "300"]
        run(cmd)
        trips += list(ET.parse(out).getroot().findall("trip"))
    trips.sort(key=lambda e: (float(e.get("depart", "0")), e.get("id")))
    root = ET.Element("routes")
    root.extend(trips)
    merged = ROOT / "_tmp" / f"{name}_{scen}.trips.xml"
    ET.ElementTree(root).write(merged, encoding="UTF-8", xml_declaration=True)
    rou = ROOT / "routes" / f"{name}_{scen}.rou.xml"
    run([DUAROUTER, "-n", net, "--route-files", merged, "--additional-files", vt, "-o", rou,
         "--ignore-errors", "--no-warnings"])

def write_configs(name, scen):
    for ctrl in ("fixed", "actuated"):
        cfg = ROOT / "configs" / f"{name}_{ctrl}_{scen}.sumocfg"
        cfg.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<configuration>\n  <input>\n'
            f'    <net-file value="../networks/{name}_{ctrl}.net.xml"/>\n'
            f'    <route-files value="../routes/{name}_{scen}.rou.xml"/>\n'
            '  <time><begin value="0"/><end value="3600"/><step-length value="1"/></time>\n'
            '  <processing><time-to-teleport value="-1"/></processing>\n</configuration>\n', encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=list(NETWORKS), help="subset of intersections")
    ap.add_argument("--scenarios", nargs="*", choices=list(SCENARIOS), default=list(SCENARIOS))
    ap.add_argument("--bluelight", action="store_true", help="give ambulances SUMO's blue-light device (flashing light, others yield; may cause collisions on tight junctions)")
    a = ap.parse_args()
    BLUELIGHT = a.bluelight
    for name in (a.only or NETWORKS):
        print(f"\n===== {name} =====")
        nets = {c: build_network(name, c) for c in ("fixed", "actuated")}
        for scen in a.scenarios:
            gen_demand(nets["fixed"], name, scen)       # same demand file used for both controllers
            write_configs(name, scen)
    print("\nBuild complete. Try:  python run_sim.py --intersection roundabout --scenario medium --gui")
