"""Restore the `normalized` field on ladder-processed records (DEVIATIONS.md D-62).

The 5-sample majority vote that the P095 ladder ran on 2026-11-04 rebuilt each
voted entity as `{type, text, start, end}` and dropped the model's
`normalized` form. The dataset writer falls back to `normalized = text`, and
`network.build()` keys nodes on the normalised name, so a voted document would
enter the graph with a different node identity from an unvoted one.

The pre-ladder records are archived, so the field is recoverable **exactly**:
for a voted entity whose document text is unchanged (same `text_sha`), look up
`(type, text)` in that document's archived entities and copy the normalised
form. Nothing is inferred, merged or guessed. An entity whose `(type, text)`
does not appear in the archive keeps the `text` fallback and is counted as
unrecovered.

Usage:
    ./venv/bin/python scripts/recover_normalized.py            # report only
    ./venv/bin/python scripts/recover_normalized.py --apply    # rewrite silver
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data" / "silver" / "silver.jsonl"
DEFAULT_ARCHIVE = ROOT / "data" / "archive" / "preretier_20261104T0704Z" / "silver.jsonl"
RECEIPT = ROOT / "data" / "metrics" / "normalized_recovery.json"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(p: Path) -> list[dict]:
    out = []
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    arch_p = Path(args.archive)
    if not arch_p.exists():
        print(f"archive absent: {arch_p}")
        return 2
    arch = {r["doc_id"]: r for r in _load(arch_p)}
    recs = _load(SILVER)

    docs, ents_voted, ents_missing, recovered, unrecovered = 0, 0, 0, 0, 0
    sha_mismatch = 0
    examples = []
    for r in recs:
        if r.get("decoding") != "self_consistency":
            continue
        docs += 1
        a = arch.get(r["doc_id"])
        same_text = bool(a) and a.get("text_sha") == r.get("text_sha")
        amap = {}
        if same_text:
            for e in a.get("entities", []):
                if e.get("normalized"):
                    amap[(e["type"], e["text"])] = e["normalized"]
        if a and not same_text:
            sha_mismatch += 1
        for e in r.get("entities", []):
            ents_voted += 1
            if e.get("normalized"):
                continue
            ents_missing += 1
            nm = amap.get((e["type"], e["text"]))
            if nm:
                recovered += 1
                e["normalized"] = nm
            else:
                unrecovered += 1
                if len(examples) < 10:
                    examples.append({"doc_id": r["doc_id"], "type": e["type"],
                                     "text": e["text"][:60],
                                     "same_text": same_text})

    before = _sha(SILVER)
    receipt = {
        "at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "silver": str(SILVER), "silver_sha256_before": before,
        "archive": str(arch_p), "archive_sha256": _sha(arch_p),
        "n_voted_docs": docs, "n_entities_voted": ents_voted,
        "n_entities_missing_normalized": ents_missing,
        "n_recovered": recovered, "n_unrecovered": unrecovered,
        "n_docs_text_sha_mismatch": sha_mismatch,
        "recovery_rate": (round(recovered / ents_missing, 4) if ents_missing else None),
        "unrecovered_examples": examples,
        "applied": bool(args.apply),
        "note": ("Exact (doc_id, type, text) lookup in the pre-ladder archive; "
                 "no merging or inference. Unrecovered entities keep the "
                 "normalized=text fallback and are counted here, not guessed."),
    }
    if args.apply and ents_missing:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
        bak = ROOT / "data" / "archive" / f"pre_normalized_recovery_{stamp}"
        bak.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SILVER, bak / "silver.jsonl")
        tmp = SILVER.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(SILVER)
        receipt["backup_dir"] = str(bak)
        receipt["silver_sha256_after"] = _sha(SILVER)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in (
        "n_voted_docs", "n_entities_voted", "n_entities_missing_normalized",
        "n_recovered", "n_unrecovered", "recovery_rate", "applied")},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
