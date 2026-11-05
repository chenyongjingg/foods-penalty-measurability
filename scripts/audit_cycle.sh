#!/bin/bash
# One-shot corrective cycle after the scientific audit:
#   1. wait for the running re-label pass to finish
#   2. stop the queued blind chain (it would run extract/analyze on the stale
#      anchor + tier rules)
#   3. recompute anchor/tier on the stored channels (no GPU)
#   4. re-admit the documents rejected by the old proximity rule and re-clean
#      (CPU only)
#   5. run extract -> analyze -> report under the cycle lock
set -u
cd /opt/foods || exit 1
echo "[audit_cycle] start $(date -u +%FT%TZ)"

while pgrep -af "foods_pipeline.cli label" | grep -qv "pgrep"; do
  sleep 10
done
echo "[audit_cycle] relabel finished $(date -u +%FT%TZ)"

pkill -f "scripts/chain_locked.py" || true
pkill -f "foods_pipeline.cli extract" || true
pkill -f "foods_pipeline.cli analyze" || true
sleep 3
echo "[audit_cycle] stopped blind chain"

./venv/bin/python scripts/retier.py >> logs/retier.log 2>&1
echo "[audit_cycle] retier rc=$? $(tail -1 logs/retier.log)"

./venv/bin/python scripts/readmit.py cfws >> logs/readmit.log 2>&1
echo "[audit_cycle] readmit rc=$? $(tail -1 logs/readmit.log)"

./venv/bin/python -m foods_pipeline.cli clean >> logs/clean2.out 2>&1
echo "[audit_cycle] clean rc=$? $(date -u +%FT%TZ)"

setsid -f ./venv/bin/python scripts/chain_locked.py extract analyze report \
  </dev/null >> logs/chain3.out 2>&1
echo "[audit_cycle] chain3 launched $(date -u +%FT%TZ)"
