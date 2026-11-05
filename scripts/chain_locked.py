"""Run label -> extract -> analyze -> report under the same cycle lock as the
daemon, so a manual re-label never overlaps a scheduled 02:00 UTC cycle.

Overlap matters for correctness, not just load: two label processes each list
the clean stage at their own start, so the same document would be labelled
twice and appended twice to silver.jsonl.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

ROOT = Path("/opt/foods")
PY = str(ROOT / "venv" / "bin" / "python")
STAGES = sys.argv[1:] or ["label", "extract", "analyze", "report"]

# A protocol revision resets the corpus before re-labelling it. The reset must
# happen inside the same lock as the label run: between the two, the documents
# sit at `clean` and another label process (the daemon) would pick them up
# under the old settings.
SPECIAL = {
    "relabel_all": [PY, "scripts/relabel_source.py", "all"],
    # D-34: recompute the deterministic anchor after an engine change without
    # re-labelling; it also re-tiers, so it must hold the same lock as label.
    "retier": [PY, "scripts/retier.py"],
}


def log(msg: str) -> None:
    print(f"[chain] {datetime.now(timezone.utc):%FT%TZ} {msg}", flush=True)


log(f"waiting for cycle lock ({','.join(STAGES)})")
with FileLock(str(ROOT / "state" / "cycle.lock"), timeout=6 * 3600):
    log("lock acquired")
    for stage in STAGES:
        t0 = time.time()
        cmd = SPECIAL.get(stage) or [PY, "-m", "foods_pipeline.cli", stage]
        r = subprocess.run(cmd, cwd=str(ROOT),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        duration = time.time() - t0
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        log(f"{stage} rc={r.returncode} {duration:.0f}s :: {tail[0][:300]}")
log("done")
