# Fairness-aware multi-agent RL controller

| File | What it is |
|---|---|
| `../backend/app/controllers/marl.py` | The controller (`MarlController`), its Q-network and the DQN learner. Pure numpy |
| `train_marl.py` | Trains it in SUMO and saves `weights/marl_policy.npz` |
| `training_log.csv` | One row per training episode (network, exploration rate, mean wait, ambulance wait, loss) |

**Agents.** Every signalised junction is one agent. All agents share one Q-network (parameter
sharing), which scores each candidate action, *serve signal group g for d seconds* (d = 8, 15 or
25 s), from features of that candidate: its queue and waiting time, the rest of the junction's
queue and longest wait, whether it just had green, and the green length. That way one network works
for junctions with 2, 3 or more phases.

**Reward** between two decisions of a junction: minus the halting vehicles x seconds on its
approaches, minus a fairness penalty that grows with the longest wait beyond 45 s. A hard guard
still serves any group that has waited 90 s.

**Safety is not learned.** The agent only chooses the next green. Ambulance priority, the green
corridor, yellow / all-red and fair recovery stay in `IntersectionController`, on top of it, also
during training.

```bash
python marl/train_marl.py --episodes 40          # continues from the saved weights
python marl/train_marl.py --episodes 60 --fresh  # start over
python sumo/run_equiflow.py --all --base marl --seeds 1 2 3   # evaluate (controller "equiflow-marl")
```

Use it: in the dashboard pick **EquiFlow MARL**, or set `sumo.base_controller: marl` (SUMO view)
or `controller: marl` (camera junction) in `backend/config.yaml`. Without trained weights it falls
back to the adaptive controller and says so.

Current state (55 episodes): ambulances wait 0.05 s at signals, cars 8.4 s, against 7.6 s for the
hand-tuned adaptive controller and 6.5 s for SUMO's actuated plan (48 matched runs). Training longer,
on full-hour episodes, is the obvious next step.
