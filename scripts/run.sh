#!/usr/bin/env bash
# Launch the FinLit Streamlit app.  Usage: bash scripts/run.sh [port]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -x .venv/bin/finlit ]; then
  echo "FinLit is not installed yet. Run: bash scripts/install.sh" >&2
  exit 1
fi
PORT="${1:-8501}"
echo "Starting FinLit on http://localhost:$PORT (Ctrl+C to stop)"
exec .venv/bin/finlit ui --port "$PORT"
