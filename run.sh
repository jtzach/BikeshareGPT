#!/usr/bin/env bash
set -euo pipefail

# BikeShareGPT / BikeshareGPT - one-command runner
#
# Requirements:
#   - Python 3.10+
#   - An Ollama Cloud API key in .env for the default model suite
#   - Optional: an OpenAI API key in .env to also run GPT-5 in the same suite
#
# Usage:
#   1) cp .env.example .env  (and set OLLAMA_API_KEY)
#   2) ./run.sh              (defaults to configs/mv_rad_gemma_ministral_gpt5_suite.yaml)
#   3) python scripts/audit_release.py  (offline audit, no model calls)
#      ./run.sh configs/toy.yaml uses local data but still calls a model API
#   4) ./run.sh configs/mv_rad_gem_v1.yaml  (single-model OpenAI-compatible run)
#   5) ./run.sh configs/default.yaml  (live download mode)

CONFIG_PATH=${1:-configs/mv_rad_gemma_ministral_gpt5_suite.yaml}

if [ ! -f .env ]; then
  echo "[ERROR] .env not found. Create one from .env.example and set OLLAMA_API_KEY (and OPENAI_API_KEY if you want GPT-5 in the full suite)." >&2
  exit 1
fi

# Export variables from .env for the Python process.
set -a
. ./.env
set +a

# Create venv if needed
if [ ! -d .venv ]; then
  python -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Upgrade pip quietly
python -m pip install --upgrade pip >/dev/null

# Install deps if missing (cheap check). This must be inside the `if` test so
# `set -e` does not abort before we can install the requirements.
if ! python - <<'PY'
import importlib.util, sys
missing=[]
for pkg in ["openai","dotenv","pydantic","yaml","pandas","numpy","typer","rich","requests","rapidfuzz","matplotlib"]:
    if importlib.util.find_spec(pkg) is None:
        missing.append(pkg)
if missing:
    print("Missing:", ", ".join(missing), file=sys.stderr)
    sys.exit(1)
PY
then
  echo "[INFO] Installing dependencies..."
  pip install -r requirements.txt
fi

echo "[INFO] Running benchmark: ${CONFIG_PATH}"
python -m bikesharegpt.cli --config "${CONFIG_PATH}"

