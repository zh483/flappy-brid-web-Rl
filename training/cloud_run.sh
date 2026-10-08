#!/usr/bin/env bash
# Linux cloud entry point. Invoke from anywhere: bash training/cloud_run.sh setup|run
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

MODE="${1:-help}"
if [[ "$MODE" == "setup" ]]; then
    BASE_PYTHON="${FLAPPY_BASE_PYTHON:-python}"
    command -v "$BASE_PYTHON" >/dev/null || { echo "Python not found: $BASE_PYTHON"; exit 1; }
    command -v c++ >/dev/null || { echo "Install a C++ compiler first: apt-get update && apt-get install -y build-essential python3-dev python3-venv"; exit 1; }
    # Reuse PyTorch from the cloud image if present, otherwise install the CPU build.
    if [[ ! -x .venv/bin/python ]]; then
        "$BASE_PYTHON" -m venv --system-site-packages .venv
    fi
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
    if ! "$PYTHON" -c 'import torch; print(torch.__version__)'; then
        "$PYTHON" -m pip install 'torch>=2.3,<3' --index-url https://download.pytorch.org/whl/cpu
    fi
    "$PYTHON" -m pip install -r training/requirements.txt
    "$PYTHON" -m training.build_engine
    "$PYTHON" -m unittest discover -s training/tests -v
    echo "Setup passed. Run: nohup bash training/cloud_run.sh run > cloud.log 2>&1 < /dev/null &"
elif [[ "$MODE" == "run" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
    [[ -x "$PYTHON" ]] || { echo "Run setup first."; exit 1; }
    command -v timeout >/dev/null || { echo "Install coreutils (timeout command)."; exit 1; }
    RUN_ID="${FLAPPY_RUN_ID:-cloud-$(date +%Y%m%d-%H%M%S)-$$}"
    [[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo "Invalid FLAPPY_RUN_ID"; exit 1; }
    OUTPUT="training/runs/$RUN_ID"
    echo "Run directory: $OUTPUT"
    echo "Time limit: ${FLAPPY_HOURS:-7}h; device: cpu; environments: ${FLAPPY_N_ENVS:-2}"
    # SIGINT requests a graceful model save; workers ignore it and close with the parent.
    timeout --preserve-status --signal=INT --kill-after=120s "${FLAPPY_HOURS:-7}h" \
        "$PYTHON" -m training.train --device cpu \
        --n-envs "${FLAPPY_N_ENVS:-2}" --timesteps "${FLAPPY_TIMESTEPS:-10000000}" \
        --eval-freq 100000 --eval-episodes 3 --checkpoint-freq 50000 --output "$OUTPUT"
    MODEL="$OUTPUT/final.zip"
    if [[ ! -f "$MODEL" ]]; then MODEL="$OUTPUT/interrupted.zip"; fi
    "$PYTHON" -m training.evaluate "$MODEL" --episodes 10
    echo "Training and evaluation completed. Download the whole directory: $OUTPUT"
    echo "The cloud instance is still running. Stop it from your platform console when finished."
else
    echo "Usage: bash training/cloud_run.sh setup|run"
    echo "Options: FLAPPY_HOURS=7 FLAPPY_N_ENVS=2 FLAPPY_TIMESTEPS=10000000 FLAPPY_RUN_ID=my-run"
fi
