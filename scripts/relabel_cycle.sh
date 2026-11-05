#!/bin/bash
# Wait for the running bulk label pass to end, reset the openFDA documents
# (their channel-A prompt returned empty entity lists under the old prompt),
# then re-label and run label -> extract -> analyze -> report under the cycle
# lock in one detached job.
set -u
cd /opt/foods || exit 1
echo "[relabel_cycle] start $(date -u +%FT%TZ)"

while pgrep -af "foods_pipeline.cli label" | grep -qv "pgrep"; do
  sleep 15
done
echo "[relabel_cycle] label pass ended $(date -u +%FT%TZ)"

./venv/bin/python scripts/relabel_source.py openfda >> logs/relabel.log 2>&1
echo "[relabel_cycle] reset rc=$? $(date -u +%FT%TZ)"
tail -3 logs/relabel.log

setsid -f ./venv/bin/python scripts/chain_locked.py \
  </dev/null >> logs/chain2.out 2>&1
echo "[relabel_cycle] chain launched $(date -u +%FT%TZ)"
