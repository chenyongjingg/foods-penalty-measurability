"""Pre-registered E1 on the current corpus, after the P095 ladder rewrote it.

The ladder replaces the two channels of a document with 5-sample majority
votes. After that, the corpus no longer contains the single-shot channels the
pre-registered E1 is defined on, so re-running `evaluate_e1` on silver measures
a mixture and `e1.json` says so (`decoding_mix`, D-63). The original channels
are archived, though, so the pre-registered value for the *current* corpus can
still be computed exactly: for every voted document whose text is unchanged
(same `text_sha`), substitute the archived record — channels, anchor and
category — and score with the same `evaluate_e1` the pipeline uses.

No model call, no inference. Documents whose original record cannot be found
are excluded from the score and counted, never filled in.

Usage:
    ./venv/bin/python scripts/e1_preladder.py [--out data/metrics/e1_preladder.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foods_pipeline.extract.runner import Extractor  # noqa: E402

SILVER = ROOT / "data" / "silver" / "silver.jsonl"


def _archives() -> list[Path]:
    """Every archived corpus, oldest first.

    The earliest archive predates every ladder run, so it holds the true
    single-shot channels; later ones only cover documents that arrived after
    them. Ordering is by the timestamp in the directory name, never by name —
    `preladder_…` sorts before `preretier_…` alphabetically but came later.
    """
    found = []
    for p in (ROOT / "data" / "archive").glob("*/silver.jsonl"):
        m = re.search(r"(\d{8}T\d{4}Z)", p.parent.name)
        found.append((m.group(1) if m else "99999999T9999Z", p))
    return [p for _stamp, p in sorted(found)]


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(p: Path) -> list[dict]:
    with open(p, "r", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "metrics" / "e1_preladder.json"))
    args = ap.parse_args()

    cur = _load(SILVER)
    pool: dict[tuple[str, str], dict] = {}
    used_archives = []
    for a in _archives():
        if not a.exists():
            continue
        used_archives.append({"path": str(a), "sha256": _sha(a), "n": 0,
                              "n_usable_single_shot": 0})
        for r in _load(a):
            used_archives[-1]["n"] += 1
            # Only single-shot copies can stand in for the pre-registered
            # channels. Voted entries are skipped rather than allowed to block
            # a later archive: `v1_20261104T0235Z` already contains 396 voted
            # records from the v1 ladder, and taking the earliest copy blindly
            # discarded the 07:04Z single-shot records for 365 documents.
            if r.get("decoding") == "self_consistency":
                continue
            used_archives[-1]["n_usable_single_shot"] += 1
            pool.setdefault((r.get("doc_id"), r.get("text_sha")), r)

    recs, n_voted, n_sub, n_lost = [], 0, 0, 0
    for r in cur:
        if r.get("decoding") == "self_consistency":
            n_voted += 1
            a = pool.get((r.get("doc_id"), r.get("text_sha")))
            # The archived copy must itself be single-shot. A snapshot taken
            # after this document was voted contains the voted channels, and
            # substituting those would smuggle the post-ladder estimator back
            # in under the pre-registered label (D-63/D-68).
            if (a is not None and isinstance(a.get("channels"), dict)
                    and a.get("decoding") != "self_consistency"):
                sub = dict(a)
                sub["doc_id"], sub["source"], sub["lang"] = (
                    r.get("doc_id"), r.get("source"), r.get("lang"))
                recs.append(sub)
                n_sub += 1
                continue
            n_lost += 1
            continue
        recs.append(r)

    ex = Extractor()
    e1 = ex.evaluate_e1(recs)
    out = {
        "at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "silver": str(SILVER), "silver_sha256": _sha(SILVER),
        "e1": e1,
        "provenance": {
            "n_silver": len(cur), "n_voted_in_silver": n_voted,
            "n_substituted_from_archive": n_sub,
            "n_voted_without_archive": n_lost,
            "n_scored": len(recs),
            "archives": used_archives,
            "rule": ("voted document -> archived record with identical text_sha "
                     "(channels, anchor, category); unchanged document -> silver "
                     "record; no archive -> excluded and counted"),
            "why": ("the pre-registered E1 is defined on the single-shot channels; "
                    "the ladder replaced them in silver (D-63/D-65)"),
        },
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"status": e1.get("status"), "mean": e1.get("mean_agreement"),
                      "n": e1.get("n"), "n_substituted": n_sub, "n_lost": n_lost,
                      "by_lang": {k: v.get("mean_agreement")
                                  for k, v in (e1.get("by_lang") or {}).items()},
                      "anchor_f1": (e1.get("anchor_f1") or {}).get("f1")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
