#!/usr/bin/env bash
# One-command start (NF-07): creates the virtualenv on first run, then launches the app.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt  # fast no-op when nothing changed; picks up new dependencies
if [ ! -f .env ]; then
  echo "⚠  .env not found: cp .env.example .env and fill in OPENAI_BASE_URL / OPENAI_API_KEY" >&2
  exit 1
fi
# Listen on localhost only, so nobody else on the venue Wi-Fi can spend the team's AI credit.
# To share on the LAN deliberately: HOST=0.0.0.0 ./run.sh
exec .venv/bin/streamlit run app.py --server.headless true --browser.gatherUsageStats false \
  --server.address "${HOST:-localhost}" "$@"
