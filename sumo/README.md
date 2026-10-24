# Islamabad Intersection Simulation (SUMO)

A generic SUMO toolkit that builds eight kinds of intersections found in Islamabad, fills them with mixed traffic (cars, motorcycles, buses, trucks and ambulances), runs them under fixed-time or actuated signals, and reports results **per vehicle class**.

It replaces the original single 3x3 grid (`build_phase1.py`, `run_baseline.py`, `check_sumo.py`).

---

## 1. Files

| File | Purpose |
|---|---|
| `build_islamabad.py` | Generates networks, vehicle types, demand (routes) and `.sumocfg` files |
| `run_sim.py` | Runs a simulation through TraCI, optionally with ambulance signal pre-emption, and writes metrics |

Folders created automatically next to the scripts:

```
networks/   <intersection>_<fixed|actuated>.net.xml
routes/     vtypes.add.xml, <intersection>_<scenario>.rou.xml
configs/    <intersection>_<controller>_<scenario>.sumocfg   (open directly in sumo-gui)
results/    tripinfo_*.xml, summary_by_class.csv
_tmp/       intermediate node/edge/trip files (safe to delete)
```

---

## 2. Requirements

- Python 3.8+
- SUMO 1.15+ (`netconvert`, `netgenerate`, `duarouter`, `sumo`, `sumo-gui`, and `tools/randomTrips.py`)

The scripts look for SUMO in this order:
1. the `SUMO_HOME` environment variable
2. the pip package (`pip install eclipse-sumo`)
3. common Windows folders (`C:\Program Files (x86)\Eclipse\Sumo`, `C:\Program Files\Eclipse\Sumo`, `C:\Program Files (x86)\SUMO`)

If none is found the script stops and asks you to set `SUMO_HOME`.

---

## 3. Quick start

```bash
# 1. build everything (all intersections, all scenarios)
python build_islamabad.py

# or only some
python build_islamabad.py --only roundabout diamond --scenarios medium high

# 2. run one simulation
python run_sim.py --intersection roundabout --controller actuated --scenario medium

# 3. watch it in the GUI
python run_sim.py --intersection diamond --gui

# 4. with ambulance pre-emption
python run_sim.py --intersection cross_signal --preempt --gui

# 5. run every combination (8 intersections x 2 controllers x 4 scenarios)
python run_sim.py --all
```

You can also open a generated config directly:

```
sumo-gui -c configs\roundabout_fixed_medium.sumocfg
```

---

## 4. Intersection types

Islamabad drives on the **left**, so every network is built with `--lefthand`. Roundabouts therefore circulate **clockwise**.

| Name | Description | Control | Real-world analogue |
|---|---|---|---|
| `cross_signal` | 4-arm crossing, 3 lanes per arm | Traffic light | At-grade junctions on Jinnah Ave, Constitution Ave, Kashmir Hwy |
| `t_signal` | 3-arm T, 2 lanes | Traffic light | Sector service road meeting an avenue |
| `t_priority` | 3-arm T, 1 lane | Give-way | Quiet sector streets |
| `y_junction` | 3-arm Y (120 deg apart) | Priority | Merging arterials |
| `five_way_signal` | 5-arm star | Traffic light | Complex multi-road chowks |
| `roundabout` | 4-arm roundabout, ring radius 28 m | Yield on entry | Chowks |
| `sector_grid` | 3x3 grid, 300 m blocks | Traffic lights | Sector-style block grid |
| `diamond` | Grade-separated diamond interchange | Signals at ramp terminals | Zero Point / Faizabad style interchanges |

### How the star junctions work
`cross_signal`, `t_*`, `y_junction`, `five_way_signal` and `roundabout` all come from one function:

```python
build_star(arms=[0, 90, 180, 270], ctrl="signal", lanes=3, speed=16.67)
```

`arms` are compass angles (0 = north, clockwise). To add a new junction, add one line to the `NETWORKS` dict, for example a six-arm junction:

```python
"six_way": ("star", dict(arms=[0,60,120,180,240,300], ctrl="signal", lanes=2, speed=13.89)),
```

Also add its name to the `NETS` list in `run_sim.py`.

### The diamond interchange
The expressway (east-west, two separate 3-lane carriageways) and the arterial (north-south, 2 lanes) **never share a node**, so they do not interact at the crossing, which models a flyover. Vehicles move between them only through four one-lane ramps (eastbound off/on on the north side, westbound off/on on the south side, because of left-hand traffic). The ramps end at two signalised junctions on the arterial.

---

## 5. Vehicle types

Defined in `VTYPES` inside `build_islamabad.py` and written to `routes/vtypes.add.xml`.

| Type | vClass | GUI colour / shape | Share of normal traffic |
|---|---|---|---|
| `car` | passenger | yellow, passenger | 62% |
| `motorcycle` | motorcycle | cyan, motorcycle (can filter laterally) | 25% |
| `bus` | bus | green, bus | 6% |
| `truck` | truck | grey, truck | 7% |
| `ambulance` | emergency | **red**, emergency shape, wider | fixed count per hour |

Ambulances are faster (`speedFactor` 1.25), more assertive in lane changing, and drawn red and wider so they stand out in the GUI and in the results. They are generated with a minimum trip length of 300 m.

**Blue-light device (optional).** SUMO's blue-light device adds a flashing light and makes nearby vehicles pull aside. It is **off by default** because at high demand it caused junction collisions (vehicles teleported, emergency braking), mostly on the roundabout but also on some signalised junctions. With it off, all eight junctions ran with zero collisions at high demand. To enable it anyway, rebuild with `python build_islamabad.py --bluelight`.

The traffic shares are estimates of a motorcycle-heavy urban mix. Edit the `MIX` dict to match real counts.

---

## 6. Demand scenarios

Defined in `SCENARIOS` as `(seconds between normal vehicles, seed, ambulances per hour)`.

| Scenario | Normal-vehicle period | Ambulances/hour | Notes |
|---|---|---|---|
| `low` | 10 s | 6 | Light traffic |
| `medium` | 6 s | 10 | Default |
| `high` | 3.5 s | 14 | Near capacity on small junctions |
| `asymmetric` | 5 s | 10 | Most trips start and end at the network fringe (`--fringe-factor 10`) |

The simulated hour is 0 to 3600 s, with vehicles inserted until 3500 s. The same route file is used for the fixed and actuated networks, so the controller comparison is fair.

If too few vehicles finish within the hour, the junction is oversaturated: increase the period values.

---

## 7. Controllers

- **fixed**: static signal plans generated by netconvert (`--tls.default-type static`).
- **actuated**: detector-based signals (`--tls.default-type actuated`).

Unsignalised junctions (`t_priority`, `y_junction`, `roundabout`) are identical under both options.

---

## 8. Ambulance pre-emption (`--preempt`)

Every simulation step, `run_sim.py` finds each ambulance whose next traffic light is closer than `--preempt-dist` metres (default 80). For that light it:

1. remembers the current signal program,
2. sets the ambulance's own movement to green and **every other movement to red**,
3. hands control back by restoring the program once the ambulance has passed.

The number of pre-emption events is printed. Results are saved under the controller name `fixed+preempt` or `actuated+preempt`, so they sit beside the normal results for comparison.

---

## 9. Output

`results/summary_by_class.csv` has one row per intersection, controller, scenario, seed and vehicle type:

| Column | Meaning |
|---|---|
| `completed` | Vehicles that finished their trip |
| `mean_travel_time_s` | Mean trip duration |
| `mean_waiting_s` | Mean time spent stopped (speed below 0.1 m/s) |
| `mean_time_loss_s` | Mean time lost versus driving at the speed limit |
| `mean_stopped_vehicles` | Average number of stopped vehicles of that type per step |

Re-running the same combination overwrites its previous rows. Full per-vehicle detail is in `results/tripinfo_*.xml`.

Typical use: compare the `ambulance` row against the `car` row at the same junction, or compare `actuated` against `actuated+preempt` to measure the benefit of pre-emption.

---

## 10. Command-line options

**`build_islamabad.py`**

| Option | Meaning |
|---|---|
| `--only NAME...` | Build only the named intersections |
| `--scenarios NAME...` | Build only the named scenarios |
| `--bluelight` | Give ambulances SUMO's blue-light device (may cause collisions on tight junctions) |

**`run_sim.py`**

| Option | Default | Meaning |
|---|---|---|
| `--intersection` | `cross_signal` | Which network |
| `--controller` | `fixed` | `fixed` or `actuated` |
| `--scenario` | `medium` | `low`, `medium`, `high`, `asymmetric` |
| `--seed` | 1 | SUMO random seed |
| `--preempt` | off | Ambulance signal pre-emption |
| `--preempt-dist` | 80 | Trigger distance in metres |
| `--gui` | off | Use `sumo-gui` |
| `--all` | off | Run all combinations |

---

## 11. Known limitations

- Geometry is idealised (textbook shapes), not surveyed. For a real junction, export it from OpenStreetMap with SUMO's `osmWebWizard.py` and reuse `vtypes.add.xml` and `run_sim.py`.
- `five_way_signal` with the actuated controller produces SUMO warnings that some phases have no detector. Use the fixed controller there, or edit the signal plan by hand.
- Traffic mix and demand levels are estimates, not measured Islamabad counts.
- Pedestrians, rickshaws, on-street parking and lane-discipline behaviour are not modelled.
- Pre-emption is a simple rule (one green movement, all others red), not a full emergency-vehicle signal plan.
- Results from a single seed are noisy; run several seeds (`--seed 1`, `--seed 2`, ...) before drawing conclusions.

---

## 12. Troubleshooting

| Message | Fix |
|---|---|
| `SUMO not found` | Set `SUMO_HOME` to your SUMO folder, or `pip install eclipse-sumo` |
| `randomTrips.py not found` | SUMO install is missing its `tools` folder; check `SUMO_HOME` |
| `Missing network/routes` | Run `python build_islamabad.py` first |
| `Another vehicle type ... exists` | Rebuild; the config must not also load `vtypes.add.xml` (the route files already contain the types) |
| `Teleporting vehicle ... junction collision` | Usually caused by `--bluelight`. Rebuild without it |
| `SUMO_HOME is not set properly, disabling XML validation` | Harmless. Set `SUMO_HOME` to the SUMO install folder (the one containing `bin` and `tools`) to silence it |
| Few vehicles complete | Demand too high: raise the period values in `SCENARIOS` and rebuild |
| Many "no valid route" warnings while building | Normal; random trips that would need a U-turn are discarded during validation |
