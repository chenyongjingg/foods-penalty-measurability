"""Return filtered-out cfws documents to the raw stage for re-cleaning.

Why: the intake rule changed (D-19). Documents rejected under the old
proximity rule were never given a second look; the clean stage re-applies the
current rule, so putting them back at `raw` is enough — no text is
reconstructed by hand, and a document that still fails is filtered again.

Usage: python scripts/readmit.py [source] [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import utc_iso  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    source = args[0] if args else "cfws"
    dry = "--dry-run" in sys.argv
    m = Manifest()
    ids = [d["doc_id"] for d in m.iter_stage("filtered_out", source=source)]
    print(f"source={source} filtered_out={len(ids)}")
    if dry or not ids:
        return 0
    at = utc_iso()
    for doc_id in ids:
        m.set_stage(doc_id, "raw", note=f"readmit:intake_v2:{at}")
    print(f"reset {len(ids)} docs to raw at {at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
