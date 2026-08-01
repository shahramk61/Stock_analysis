#!/usr/bin/env bash
# Stub for future automation: prepare Grok decision handoff (no live trading).
# Usage: ./scripts/hooks/run_decide_stock.sh TICKER [PROFILE]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TICKER="${1:-}"
PROFILE="${2:-Balanced}"
if [[ -z "$TICKER" ]]; then
  echo "Usage: $0 TICKER [PROFILE]"
  exit 1
fi
echo "[hook-stub] Preparing handoff for $TICKER (profile=$PROFILE)"
echo "[hook-stub] Uses Grok Build subscription for decisions — no XAI_API_KEY"
python3 scripts/prepare_decision_handoff.py "$TICKER" --profile "$PROFILE" --fast
echo "[hook-stub] Handoff ready (see path printed above)"
echo "[hook-stub] Next: /decide-stock $TICKER in this Grok Build session"
