#!/usr/bin/env bash
# Retrain the model; refreshes ml/artifacts/ and backend/src/shared/model/model.json.
# Redeploy afterwards (scripts/deploy.sh) so Lambda picks up the new model.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/Scripts/python.exe"; [ -x "$PY" ] || PY="python"
"$PY" ml/train.py
"$PY" -m pytest -q
