#!/usr/bin/env bash
# Start the local vLLM server (Qwen2.5-7B-Instruct, read-only model mount).
set -euo pipefail
ROOT="${FOODS_ROOT:-/opt/foods}"
VENV="$ROOT/venv"
MODEL="${FOODS_MODEL:-/model/ModelScope/Qwen/Qwen2.5-7B-Instruct}"
NAME="${FOODS_MODEL_NAME:-qwen2.5-7b-instruct}"
PORT="${FOODS_LLM_PORT:-8000}"
LOG="$ROOT/logs/vllm.log"
PID="$ROOT/state/vllm.pid"

if curl -sf -m 3 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
  echo "vLLM already serving on $PORT"
  exit 0
fi

if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  echo "vLLM process $(cat "$PID") alive but not ready yet"
  exit 0
fi

# --- E9 VRAM window guard (D-96) ---------------------------------------------
# The watchdog calls this script every 10 min. During an E9 window a vLLM start
# reserves 0.85 x 24 GB and OOMs against the trainer (observed 2026-11-05T05:57Z:
# pid 237145 held 6.99 GiB, vLLM asked for 15.07 GiB with 1.47 GiB free).
# Refuse only while the marker is <12 h old AND a trainer is actually running, so
# the E9 wrapper's own restart (which runs after the trainer exits) still works.
E9_MARK="$ROOT/state/e9_window.json"
if [ -f "$E9_MARK" ] && pgrep -f 'e9_selftrain[.]py' >/dev/null 2>&1; then
  AT=$(grep -oE '"(at_utc|started_utc)":"[^"]+"' "$E9_MARK" 2>/dev/null \
       | head -1 | sed 's/.*:"//; s/"$//' || true)
  AGE=999999
  if [ -n "${AT:-}" ]; then
    EPOCH=$(date -u -d "$AT" +%s 2>/dev/null || echo 0)
    [ "$EPOCH" -gt 0 ] && AGE=$(( $(date -u +%s) - EPOCH ))
  fi
  if [ "$AGE" -lt 43200 ]; then
    echo "E9 VRAM window active (marker $AT, age ${AGE}s) and e9_selftrain is running; refusing to start vLLM"
    exit 0
  fi
fi

mkdir -p "$ROOT/logs" "$ROOT/state"
cd "$ROOT"
setsid nohup "$VENV/bin/vllm" serve "$MODEL" \
  --served-model-name "$NAME" \
  --host 127.0.0.1 --port "$PORT" \
  --max-model-len 23040 \
  --gpu-memory-utilization 0.85 \
  --dtype bfloat16 \
  --disable-log-requests ${FOODS_VLLM_EXTRA:-} \
  > "$LOG" 2>&1 < /dev/null &
echo $! > "$PID"
echo "vLLM starting (pid $(cat "$PID")), log: $LOG"

for i in $(seq 1 60); do
  if curl -sf -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
    echo "vLLM ready after ${i}0s"
    exit 0
  fi
  sleep 10
done
echo "WARN: vLLM not ready after 600s; check $LOG" >&2
exit 1
