#!/usr/bin/env bash
# E9 GPU window (D-82 / D-83 窗口纪律):
#   1) 只有终版发布收据 status=released 才允许进入窗口;
#   2) 写 state/e9_window.json —— 值守代理据此不得重启 vLLM;
#   3) 停 vLLM, 等显存释放, 跑 e9_selftrain.py --run;
#   4) 无论成败(EXIT trap)都重启 vLLM 并删除标记, 并把属主权限交回组写。
set -uo pipefail
ROOT="${FOODS_ROOT:-/opt/foods}"
cd "$ROOT" || exit 1
LOG="$ROOT/logs/e9.out"
PY=/opt/e9venv/bin/python
MARK="$ROOT/state/e9_window.json"
STAMP="${E9_STAMP:-20261105}"
utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "[e9win $(utc)] $*" | tee -a "$LOG"; }

# --- precondition 1: release receipt -----------------------------------------
"$ROOT/venv/bin/python" - "$STAMP" <<'PY' || { echo "precondition failed: receipt"; exit 3; }
import json, sys
stamp = sys.argv[1]
d = json.load(open(f"/opt/foods/data/reports/finalize_{stamp}.json"))
ok = (d.get("status") == "released"
      and (d.get("checks", {}).get("bundle", {}) or {}).get("sha_ok")
      == (d.get("checks", {}).get("bundle", {}) or {}).get("n_listed"))
print("receipt:", d.get("status"), d.get("finished_utc"), "bundle_ok=", ok)
sys.exit(0 if ok else 2)
PY

# --- precondition 2: training stack ------------------------------------------
"$PY" -c "import torch,peft,bitsandbytes,transformers" || { echo "stack missing"; exit 4; }

# --- marker + trap -----------------------------------------------------------
printf '{"at_utc":"%s","reason":"E9 needs ~12GB VRAM; do NOT restart vLLM","owner":"run_e9_window.sh"}\n' "$(utc)" > "$MARK"
restart_llm() {
  say "restarting vLLM"
  bash "$ROOT/scripts/start_llm.sh" >> "$LOG" 2>&1
  for i in $(seq 1 60); do
    if curl -sf -m 3 http://127.0.0.1:${FOODS_LLM_PORT:-8000}/v1/models >/dev/null 2>&1; then
      say "vLLM ready"; break
    fi
    sleep 10
  done
  rm -f "$MARK"
  chmod -R g+w "$ROOT/data" "$ROOT/state" 2>/dev/null
  say "window closed, marker removed"
}
trap restart_llm EXIT

# --- stop vLLM ---------------------------------------------------------------
PIDF="$ROOT/state/vllm.pid"
if [ -f "$PIDF" ]; then
  P=$(cat "$PIDF")
  say "stopping vLLM pid $P"
  kill "$P" 2>/dev/null
  for i in $(seq 1 30); do kill -0 "$P" 2>/dev/null || break; sleep 2; done
  kill -0 "$P" 2>/dev/null && { say "SIGTERM ignored, SIGKILL"; kill -9 "$P" 2>/dev/null; sleep 5; }
fi
# 等显存真正释放(而不是等进程消失)
for i in $(seq 1 30); do
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
  say "vram used ${USED} MiB"
  [ "${USED:-99999}" -lt 4000 ] && break
  sleep 5
done

# --- run E9 ------------------------------------------------------------------
say "starting e9_selftrain.py ${E9_MODE:---run}"
"$PY" scripts/e9_selftrain.py ${E9_MODE:---run} >> "$LOG" 2>&1
RC=$?
say "e9_selftrain rc=$RC"
if [ -f "$ROOT/data/analysis/e9_selftrain.json" ]; then
  "$ROOT/venv/bin/python" - <<'PY' | tee -a "$LOG"
import json
d=json.load(open("/opt/foods/data/analysis/e9_selftrain.json"))
print(json.dumps({"at_utc":d["at_utc"],"base":d["base"]["score"]["anchor_f1"],
                  "adapter":d["adapter"]["score"]["anchor_f1"],
                  "delta":d["delta_macro_f1"],"verdict":d["verdict"],
                  "data":d["data"]},ensure_ascii=False))
PY
fi
chmod 664 "$ROOT/data/analysis/e9_selftrain.json" 2>/dev/null
exit "$RC"
