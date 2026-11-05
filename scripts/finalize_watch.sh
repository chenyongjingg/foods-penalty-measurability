#!/bin/bash
# Freeze the corpus at a pre-announced cut point and build the final release
# bundle (D-71). Started once with setsid; safe to restart -- it re-reads the
# daemon's kv, so a restart after the cycle does not wait for another day.
#
# It does NOT hold the cycle lock itself: finalize_release.py runs the stages
# through scripts/chain_locked.py, which does.
#
# Usage: finalize_watch.sh [TARGET_DATE] [DEADLINE_UTC]
#   TARGET_DATE  the daemon cycle date whose completion defines the freeze
#                (default 2026-11-05). The cut point is announced before the
#                data arrive.)
#   DEADLINE_UTC build on whatever corpus exists if the cycle never lands
#                (default 2026-11-06T06:00:00Z); the receipt records that.
set -u
ROOT=/opt/foods
PY="$ROOT/venv/bin/python"
TARGET_DATE="${1:-2026-11-05}"
DEADLINE_UTC="${2:-2026-11-06T06:00:00Z}"
LOG="$ROOT/logs/finalize.out"

log() { printf '[watch] %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

kv() {
  "$PY" - "$1" <<'EOF'
import sys
sys.path.insert(0, "/opt/foods")
from foods_pipeline.manifest import Manifest
print(Manifest().kv_get(sys.argv[1]) or "")
EOF
}

log "waiting for cycle $TARGET_DATE (deadline $DEADLINE_UTC)"
while :; do
  last="$(kv daemon:last_run_date 2>/dev/null)"
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ "$last" = "$TARGET_DATE" ]; then
    log "cycle $TARGET_DATE complete"
    break
  fi
  if [ "$now" \> "$DEADLINE_UTC" ]; then
    log "deadline reached with last_run_date='$last'; building on the current corpus anyway"
    break
  fi
  sleep 60
done

# The daemon writes the kv only after its cycle returns, so reaching here means
# no cycle of its own is in flight. Stop it before the manual chain so the two
# writers cannot interleave on the next collection.
if [ -f "$ROOT/state/daemon.pid" ]; then
  pid="$(cat "$ROOT/state/daemon.pid" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "stopping daemon pid $pid (collection frozen at $TARGET_DATE)"
    kill "$pid" 2>>"$LOG" || true
    sleep 5
    kill -9 "$pid" 2>/dev/null || true
  fi
fi

log "running finalize_release.py --stamp ${TARGET_DATE//-/}"
"$PY" "$ROOT/scripts/finalize_release.py" --stamp "${TARGET_DATE//-/}" >> "$LOG" 2>&1
rc=$?
log "finalize rc=$rc"
exit "$rc"
