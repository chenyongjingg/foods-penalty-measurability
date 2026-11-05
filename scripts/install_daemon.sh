#!/usr/bin/env bash
# Launch the always-on background daemon (no systemd/cron in this pod: PID 1 is tini).
set -euo pipefail
ROOT="${FOODS_ROOT:-/opt/foods}"
PIDF="$ROOT/state/daemon.pid"
HOUR="${FOODS_CYCLE_HOUR:-2}"
mkdir -p "$ROOT/state" "$ROOT/logs"

if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "daemon already running (pid $(cat "$PIDF"))"
  exit 0
fi

cd "$ROOT"
export FOODS_ROOT="$ROOT" PYTHONPATH="$ROOT" PYTHONIOENCODING=utf-8
setsid nohup "$ROOT/venv/bin/python" -m foods_pipeline.cli daemon --hour "$HOUR" \
  >> "$ROOT/logs/daemon.out" 2>&1 < /dev/null &
echo $! > "$PIDF"
echo "daemon started pid $(cat "$PIDF"), daily cycle at ${HOUR}:00 UTC"

# watchdog: keep vLLM alive; it is only needed for the label stage, so a
# lightweight check every 10 minutes is enough.
setsid nohup bash -c '
while true; do
  if ! curl -sf -m 3 http://127.0.0.1:8000/v1/models >/dev/null 2>&1; then
    bash /opt/foods/scripts/start_llm.sh >> /opt/foods/logs/watchdog.log 2>&1 || true
  fi
  sleep 600
done' >> "$ROOT/logs/watchdog.out" 2>&1 < /dev/null &
echo "llm watchdog started"
