#!/usr/bin/env bash
# Start the backend inside WSL (Ubuntu), where SUMO runs (Windows Smart App Control blocks SUMO's DLLs).
# From PowerShell:  wsl -d Ubuntu -- bash /mnt/c/Smester7/FYP_Equiflow/EquiFlow/backend/run_wsl.sh
# Uses the virtual environment ~/equiflow-venv (pip install -r requirements.lock.txt). The dashboard on Windows
# reaches it at http://localhost:8000. Extra arguments go to uvicorn, e.g. --port 8001.
set -e
VENV="${EQUIFLOW_VENV:-$HOME/equiflow-venv}"
if [ ! -x "$VENV/bin/python" ]; then
    echo "No virtual environment at $VENV. Create it with:"
    echo "  python3 -m venv $VENV && $VENV/bin/pip install -r $(dirname "$0")/requirements.lock.txt"
    exit 1
fi
cd "$(dirname "$0")"
export SUMO_HOME="$("$VENV/bin/python" -c 'import sumo; print(sumo.SUMO_HOME)')"
export PATH="$VENV/bin:$PATH"
echo "SUMO_HOME=$SUMO_HOME"
exec "$VENV/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
