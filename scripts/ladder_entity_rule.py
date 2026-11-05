"""Bring ladder-processed records onto the label protocol's entity rule (D-64).

When the two channels agree on the mention set and on the category, the label
stage keeps the **matched intersection** (`align.match(ea, eb, tau)`), not
channel A. The 2026-11-04 ladder wrote channel A's vote instead, so a document
it promoted to the high tier would enter the main corpus under a different
entity-construction rule from every other high-tier document.

The voted channels are stored on the record (`channels.a` / `channels.b`), so
the intersection can be recomputed exactly — no model call, no inference. This
script does that for records the ladder already wrote, and records the rule it
applied in `entity_rule`.

Usage:
    ./venv/bin/python scripts/ladder_entity_rule.py            # report only
    ./venv/bin/python scripts/ladder_entity_rule.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foods_pipeline.common import cfg  # noqa: E402
from foods_pipeline.label import align  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data" / "silver" / "silver.jsonl"
RECEIPT = ROOT / "data" / "metrics" / "ladder_entity_rule.json"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    tau = float(cfg("label.span_tau", 0.5))
    target = float(cfg("label.agreement_target", 0.85))
    recs = [json.loads(l) for l in open(SILVER, encoding="utf-8") if l.strip()]

    docs_voted = docs_changed = docs_skipped_no_channels = 0
    ents_before = ents_after = 0
    high_changed = 0
    for r in recs:
        if r.get("decoding") != "self_consistency":
            continue
        docs_voted += 1
        ch = r.get("channels") or {}
        a, b = ch.get("a"), ch.get("b")
        f1 = (r.get("metrics") or {}).get("agreement_f1_exact")
        if not isinstance(a, list) or not isinstance(b, list) or f1 is None:
            docs_skipped_no_channels += 1
            continue
        if not (f1 >= target and ch.get("cat_a") and ch.get("cat_a") == ch.get("cat_b")):
            r.setdefault("entity_rule", "channel_a_vote")
            continue
        inter = [x for x, _y, _s in align.match(a, b, tau)]
        if inter != r.get("entities"):
            ents_before += len(r.get("entities") or [])
            ents_after += len(inter)
            r["entities"] = inter
            r["entity_rule"] = "intersection"
            docs_changed += 1
            if r.get("tier") == "high":
                high_changed += 1

    before = _sha(SILVER)
    receipt = {
        "at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "silver": str(SILVER), "silver_sha256_before": before,
        "tau": tau, "agreement_target": target,
        "n_voted_docs": docs_voted, "n_docs_changed": docs_changed,
        "n_docs_skipped_no_channels": docs_skipped_no_channels,
        "n_high_tier_changed": high_changed,
        "entities_before_on_changed": ents_before,
        "entities_after_on_changed": ents_after,
        "applied": bool(args.apply),
        "rule": ("f1 >= target and cat_a == cat_b -> matched intersection of the "
                 "two voted channels; otherwise channel A's vote (D-64)"),
    }
    if args.apply and docs_changed:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
        bak = ROOT / "data" / "archive" / f"pre_entity_rule_{stamp}"
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
        "n_voted_docs", "n_docs_changed", "n_high_tier_changed",
        "entities_before_on_changed", "entities_after_on_changed", "applied")},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
