#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the Stock Analysis pipeline.
# Creates a project virtualenv (.venv) and installs pinned dependencies.
set -euo pipefail

cd "$(dirname "$0")/.."

# The default image ships python3 but not the venv/ensurepip module.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3.12-venv
fi

# Create the virtualenv only if it does not already exist (idempotent).
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt

echo "Install complete: $(.venv/bin/python --version)"
