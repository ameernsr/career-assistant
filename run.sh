#!/usr/bin/env bash
# One-command start (NF-07): creates the virtualenv on first run, then launches the app.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
if [ ! -f .env ]; then
  echo "⚠  .env not found: cp .env.example .env and fill in OPENAI_BASE_URL / OPENAI_API_KEY" >&2
  exit 1
fi
exec .venv/bin/streamlit run app.py --server.headless true --browser.gatherUsageStats false "$@"
