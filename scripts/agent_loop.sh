#!/usr/bin/env bash
# Resident Claude Code agent for /opt/foods.
#
# Why this exists: the laptop driving the pipeline can be shut down; the pod
# keeps running. This loop makes the pod itself the operator — one review
# cycle every AGENT_INTERVAL seconds, each logged, each writing a review note.
#
# It runs as the unprivileged user `agent` (member of group `foods`, which owns
# the tree with group write): Claude Code refuses --dangerously-skip-permissions
# as root, and an unprivileged reviewer is the safer arrangement anyway.
# The pipeline itself (daemon, chain_locked, vLLM) keeps running as root.
#
# Safety properties:
#   * single instance (flock on state/agent.lock) — two agents would double-edit
#     the same files;
#   * hard timeout per cycle (AGENT_TIMEOUT, default 1800 s);
#   * credentials come from /opt/agent/.env (outside the project tree, mode 600,
#     owned by `agent`) and are never echoed;
#   * the agent runs from /opt/foods and its instructions (CLAUDE.md) forbid
#     destructive actions and any threshold change that would make a gate pass.
#
# Start:  setsid nohup bash /opt/foods/scripts/agent_loop.sh >> /opt/foods/logs/agent/loop.out 2>&1 &
# Stop:   kill "$(cat /opt/foods/state/agent.pid)"
set -uo pipefail
ROOT=/opt/foods
ENVF=/opt/agent/.env
INTERVAL=${AGENT_INTERVAL:-1800}
CYCLE_TIMEOUT=${AGENT_TIMEOUT:-1800}

# Root invocation (e.g. from ssh) re-execs itself as `agent`.
if [ "$(id -u)" -eq 0 ]; then
  exec su - agent -c "AGENT_INTERVAL=$INTERVAL AGENT_TIMEOUT=$CYCLE_TIMEOUT bash $ROOT/scripts/agent_loop.sh"
fi

LOCK="$ROOT/state/agent.lock"
PIDF="$ROOT/state/agent.pid"
LOGDIR="$ROOT/logs/agent"
PROMPT="$ROOT/scripts/agent_prompt.txt"

mkdir -p "$LOGDIR"
echo $$ > "$PIDF"

# shellcheck disable=SC1090
set -a; . "$ENVF"; set +a
cd "$ROOT" || exit 1

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" >> "$LOGDIR/loop.log"; }

log "agent loop started pid=$$ user=$(id -un) interval=${INTERVAL}s timeout=${CYCLE_TIMEOUT}s"

while true; do
  exec 9>"$LOCK"
  if flock -n 9; then
    day=$(date -u +%Y%m%d)
    log "wake"
    timeout "$CYCLE_TIMEOUT" claude -p "$(cat "$PROMPT")" \
      --dangerously-skip-permissions \
      --output-format text \
      --max-turns 40 \
      >> "$LOGDIR/agent_${day}.log" 2>&1
    rc=$?
    log "cycle rc=${rc}"
  else
    log "another agent cycle holds the lock; skipping"
  fi
  exec 9>&-
  sleep "$INTERVAL"
done
