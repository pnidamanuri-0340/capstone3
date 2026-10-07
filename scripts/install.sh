#!/usr/bin/env bash
# FinLit installer for macOS / Linux.  Usage: bash scripts/install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY=""
for cand in python3.12 python3.11 python3.13 python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    PY="$cand"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11+ not found. Install it (https://www.python.org/downloads/ or your package manager) and re-run." >&2
  exit 1
fi
echo "==> Using $($PY --version)"

[ -x .venv/bin/python ] || "$PY" -m venv .venv
echo "==> Installing FinLit and dependencies"
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -e ".[dev]"

if [ ! -f .env ]; then
  cp .env.example .env
  read -r -p "Paste your OPENAI_API_KEY (Enter to skip): " OAI || true
  GOOG=""; ANTH=""
  if [ -z "${OAI:-}" ]; then read -r -p "Or paste a free GOOGLE_API_KEY from aistudio.google.com/apikey (Enter to skip): " GOOG || true; fi
  if [ -z "${OAI:-}" ] && [ -z "${GOOG:-}" ]; then read -r -p "Or paste an ANTHROPIC_API_KEY (Enter to add later): " ANTH || true; fi
  read -r -p "Paste your ALPHA_VANTAGE_API_KEY (Enter for sample data): " AV || true
  python_edit='import re,sys
p=".env"; t=open(p,encoding="utf-8").read()
for k,v in (("OPENAI_API_KEY",sys.argv[1]),("GOOGLE_API_KEY",sys.argv[2]),("ANTHROPIC_API_KEY",sys.argv[3]),("ALPHA_VANTAGE_API_KEY",sys.argv[4])):
    if v: t=re.sub(rf"(?m)^{k}=.*$", f"{k}={v}", t)
open(p,"w",encoding="utf-8").write(t)'
  .venv/bin/python -c "$python_edit" "${OAI:-}" "${GOOG:-}" "${ANTH:-}" "${AV:-}"
fi

echo "==> Building the knowledge base"
.venv/bin/finlit ingest
echo "==> Smoke test"
.venv/bin/finlit smoke || true
echo
echo "Install complete. Start the app with: bash scripts/run.sh"
