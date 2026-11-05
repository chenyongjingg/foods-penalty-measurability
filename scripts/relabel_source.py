"""Reset one source's labelled documents so they are re-labelled.

Usage: python scripts/relabel_source.py openfda|all [--dry-run]

`all` exists for protocol revisions that change the *input* to every channel
(the 2026-11-04 revision removed the 6,000-character document cap; DEVIATIONS
D-30). A corpus half-labelled under one input length and half under another
cannot be pooled, so the whole corpus is reset in that case.

The old silver file is archived to data/archive/ before it is rewritten: the
reset destroys the previous labels, and the v1-vs-v2 comparison is part of the
audit trail.

Why this exists: prompts are versioned artefacts. When channel prompts change
materially, documents labelled under the old prompts must be re-labelled, not
kept alongside new ones — mixing prompt versions inside one E1 estimate would
make the agreement statistic uninterpretable. The reset is recorded per
document in the manifest note, so the corpus history stays auditable.

Safety: refuses to run while a `cli label` process is alive (concurrent
appends to silver.jsonl would corrupt the file).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import path_of, utc_iso  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402


def label_running() -> bool:
    try:
        out = subprocess.run(["pgrep", "-af", "cli label"], capture_output=True,
                             text=True, timeout=10).stdout
    except Exception:
        return False
    return any("cli label" in ln and "pgrep" not in ln for ln in out.splitlines())


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    source = sys.argv[1]
    dry = "--dry-run" in sys.argv
    if label_running():
        raise SystemExit("REFUSED: a `cli label` process is running; stop it first")
    m = Manifest()
    ids = []
    for stage in ("labeled", "extracted"):
        for doc in (m.iter_stage(stage) if source == "all" else m.iter_stage(stage, source=source)):
            ids.append(doc["doc_id"])
    if not ids:
        print(f"nothing to reset for source={source}")
        return 0
    silver = path_of("data") / "silver" / "silver.jsonl"
    keep, dropped = [], 0
    if silver.exists():
        with open(silver, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if source == "all" or r.get("source") == source:
                    dropped += 1
                else:
                    keep.append(r)
        if not dry:
            archive = path_of("data") / "archive"
            archive.mkdir(parents=True, exist_ok=True)
            stamp = utc_iso().replace(":", "")
            silver.replace(archive / f"silver_{source}_{stamp}.jsonl")
            print(f"archived silver -> {archive.name}/silver_{source}_{stamp}.jsonl")
    print(f"source={source} docs={len(ids)} silver_dropped={dropped} silver_kept={len(keep)}")
    if dry:
        return 0
    tmp = silver.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, silver)
    at = utc_iso()
    for doc_id in ids:
        m.set_stage(doc_id, "clean", note=f"relabel:{source}:{at}")
    print(f"reset {len(ids)} docs to clean at {at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
