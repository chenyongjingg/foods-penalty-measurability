#!/usr/bin/env bash
# D-128: unattended pipeline for the Foods project. Ignited with setsid so it survives
# the SSH session and the local machine being switched off.
#
# Stage 1  preflight (frozen corpus sha, required products, disk)
# Stage 2  E17 segmentation sensitivity (D-127)
# Stage 3  numbers.csv machine re-derivation (the provenance claim, checked)
# Stage 4  RECEIPT.md, then heartbeat + vLLM watchdog forever
set -uo pipefail
ROOT=/opt/foods
RUN=$ROOT/runs/autopilot
VENV=$ROOT/venv/bin/python
mkdir -p "$RUN"
LOG=$RUN/autopilot.log
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

say "autopilot start pid=$$"

# ---------------- stage 1: preflight ----------------
{
  echo "== preflight $(date -u +%FT%TZ)"
  sha256sum "$ROOT/data/silver/silver.jsonl"
  for f in data/analysis/e12_commodity_index.json data/analysis/e12_commodity_precision.json \
           data/analysis/e13_commodity_subject.json data/analysis/e15_validation.json \
           data/analysis/e16_validation.json numbers.csv DEVIATIONS.md; do
    if [ -f "$ROOT/$f" ]; then sha256sum "$ROOT/$f"; else echo "MISSING $f"; fi
  done
  df -h "$ROOT" | tail -1
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
  curl -s -m 5 http://127.0.0.1:8000/v1/models >/dev/null && echo "vllm OK" || echo "vllm DOWN"
} > "$RUN/01_preflight.txt" 2>&1
if grep -q '^a1deda2c' <(grep 'silver.jsonl' "$RUN/01_preflight.txt"); then
  say "stage1 preflight: frozen corpus OK"
else
  say "stage1 preflight: FROZEN CORPUS SHA BAD (continuing, receipt will show it)"
fi

# ---------------- stage 2: E17 ----------------
if [ -f "$ROOT/data/analysis/e17_segmentation.json" ]; then
  say "stage2 E17 already present; skipping"
else
  say "stage2 E17 starting"
  PYTHONPATH=$ROOT/third_party "$VENV" "$ROOT/scripts/e17_segmentation.py" \
      > "$RUN/02_e17.log" 2>&1
  say "stage2 E17 exited rc=$?"
fi

# ---------------- stage 3: provenance ----------------
say "stage3 provenance verification starting"
"$VENV" "$ROOT/scripts/verify_numbers.py" > "$RUN/03_numbers.log" 2>&1
say "stage3 exited rc=$?"

# ---------------- stage 4: receipt ----------------
{
  echo "# Autopilot receipt — $(date -u +%FT%TZ)"
  echo
  echo "## Stage 1 — preflight"
  echo '```'
  cat "$RUN/01_preflight.txt"
  echo '```'
  echo "## Stage 2 — E17 segmentation (D-127)"
  echo '```'
  tail -20 "$RUN/02_e17.log" 2>/dev/null || echo "(no log)"
  echo '```'
  echo "## Stage 3 — numbers.csv re-derivation"
  echo '```'
  cat "$RUN/03_numbers.log" 2>/dev/null || echo "(no log)"
  echo '```'
  echo "## Products produced"
  for f in data/analysis/e17_segmentation.json runs/autopilot/03_numbers_verify.json; do
    [ -f "$ROOT/$f" ] && sha256sum "$ROOT/$f"
  done
} > "$RUN/RECEIPT.md"
say "stage4 receipt written: $RUN/RECEIPT.md"

# ---------------- heartbeat + vLLM watchdog ----------------
fails=0
while true; do
  ts=$(date -u +%FT%TZ)
  if curl -sf -m 5 http://127.0.0.1:8000/v1/models >/dev/null 2>&1; then
    fails=0; state=ok
  else
    fails=$((fails+1)); state="down($fails)"
    if [ "$fails" -ge 3 ]; then
      say "vLLM failed 3 consecutive checks; restarting"
      FOODS_VLLM_EXTRA='--enable-prefix-caching' setsid bash "$ROOT/scripts/start_llm.sh" \
          >> "$RUN/vllm_restart.log" 2>&1 < /dev/null &
      fails=0
    fi
  fi
  echo "$ts $state load=$(cut -d' ' -f1 /proc/loadavg) gpu=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' ')" >> "$RUN/heartbeat.log"
  sleep 600
done
