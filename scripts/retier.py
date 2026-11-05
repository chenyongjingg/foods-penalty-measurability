"""Recompute anchor + confidence tier for existing silver records.

Needed after the anchor engine changed (D-18, D-34) and the tier rule was
aligned with the plan (D-15): the stored anchor/tier in silver.jsonl were
produced by the previous rules. Re-labelling would cost GPU hours and would
change the model outputs; recomputing a *deterministic* rule from the stored
channels is the faithful fix — the rule is a function of the document text and
the stored agreement F1, not of the model.

Every run archives the previous silver.jsonl under data/archive/ and writes a
receipt to data/metrics/anchor_{stamp}.json, so a tier change can always be
attributed to an anchor-engine change rather than to a re-label.

Usage: python scripts/retier.py [--dry-run]
Refuses to run while a label process is alive (concurrent silver writes).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import cfg, path_of, utc_iso  # noqa: E402
from foods_pipeline.label import anchors  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402


def label_running() -> bool:
    out = subprocess.run(["pgrep", "-af", "foods_pipeline.cli label"],
                         capture_output=True, text=True).stdout
    return any("cli label" in ln and "pgrep" not in ln for ln in out.splitlines())


def main() -> int:
    dry = "--dry-run" in sys.argv
    if label_running():
        raise SystemExit("REFUSED: a `cli label` process is running; stop it first")
    target = float(cfg("label.agreement_target", 0.85))
    floor = float(cfg("label.agreement_floor", 0.75))
    silver = path_of("data") / "silver" / "silver.jsonl"
    m = Manifest()
    recs = []
    with open(silver, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    changed = 0
    tiers = {"high": 0, "medium": 0, "low": 0}
    basis_before, basis_after = Counter(), Counter()
    cat_changed = pass_flipped = missing_text = 0
    tier_transitions: Counter = Counter()
    # D-47: `metrics.agreement_f1` is rounded to 4 dp before it is stored, so a
    # document whose exact F1 is 0.7498 is stored as 0.75 and re-reads as
    # "at or above the floor". Re-deriving the tier from the rounded number
    # therefore disagrees with the tier the label stage wrote. 21 of 987 records
    # (2.1%) sit exactly on this boundary. The fix is to recompute the exact F1
    # from the stored per-channel entity lists — the same deterministic function
    # the label stage used — and only fall back to the rounded value when the
    # channel lists are absent. The rounded value is kept in the record.
    from foods_pipeline.label import align as _align
    tau = float(cfg("label.span_tau", 0.5))
    f1_recomputed = f1_from_stored = 0
    boundary = []
    exact_stale = []
    for r in recs:
        rec = m.get(r["doc_id"])
        text = ""
        if rec and rec.get("text_path"):
            try:
                text = Path(rec["text_path"]).read_text(encoding="utf-8")
            except Exception:
                text = ""
        old = r.get("anchor") or {}
        basis_before[old.get("basis")] += 1
        if not text:
            missing_text += 1
        a = anchors.label(text) if text else old
        # D-67: anchors.label builds (law, article) pairs as tuples while silver
        # stores them as JSON arrays. Compare (and store) the JSON
        # representation, otherwise a no-op retier counts every anchored record
        # as "changed" on a type-only difference.
        a = json.loads(json.dumps(a, ensure_ascii=False))
        basis_after[a.get("basis")] += 1
        if old.get("category") != a.get("category"):
            cat_changed += 1
        ch = r.get("channels") or {}
        ca, cb = ch.get("a"), ch.get("b")
        mt = r.get("metrics") or {}
        # Recompute from the stored channels first. `agreement_f1_exact` is a
        # cache written at label time, and the self-consistency ladder rewrites
        # `channels` without updating it (measured: after the 2026-11-04 ladder
        # pass no record carried `decoding == "self_consistency"` yet, so the
        # rot had not landed, but the path exists). Trusting the cache would let
        # a later retier silently revert every ladder promotion. Whenever the
        # cache disagrees with the channels, the channels win and the mismatch
        # is counted in the receipt instead of being smoothed away.
        exact = mt.get("agreement_f1_exact")
        recomputed = (_align.micro_f1(ca, cb, tau)[2]
                      if isinstance(ca, list) and isinstance(cb, list) else None)
        if recomputed is not None:
            f1 = recomputed
            f1_recomputed += 1
            if isinstance(exact, (int, float)) and abs(float(exact) - f1) > 1e-9:
                exact_stale.append({"doc_id": r["doc_id"],
                                    "stored_exact": round(float(exact), 6),
                                    "from_channels": round(f1, 6),
                                    "decoding": r.get("decoding")})
            r["metrics"] = {**mt, "agreement_f1_exact": f1}
        elif isinstance(exact, (int, float)):
            f1 = float(exact)
            f1_from_stored += 1
        else:
            f1 = float(mt.get("agreement_f1") or 0.0)
            f1_from_stored += 1
        if abs(f1 - floor) < 5e-4 or abs(f1 - target) < 5e-4:
            boundary.append({"doc_id": r["doc_id"], "f1": round(f1, 6),
                             "stored": (r.get("metrics") or {}).get("agreement_f1")})
        anchor_pass = bool(a.get("category") and r.get("violation_category") == a.get("category"))
        if bool(r.get("anchor_pass")) != anchor_pass:
            pass_flipped += 1
        if f1 >= target and (anchor_pass or r.get("lang") != "zh"):
            tier = "high"
        elif f1 >= floor:
            tier = "medium"
        else:
            tier = "low"
        tiers[tier] += 1
        tier_transitions[(r.get("tier"), tier)] += 1
        if tier != r.get("tier") or a != r.get("anchor"):
            changed += 1
        r["anchor"], r["anchor_pass"], r["tier"] = a, anchor_pass, tier
    tier_transitions = {f"{a_}->{b_}": n for (a_, b_), n in sorted(tier_transitions.items())}
    print(f"records={len(recs)} changed={changed} tiers={tiers}")
    receipt = {
        "n_records": len(recs), "changed": changed, "tiers": tiers,
        "missing_text": missing_text,
        "category_changed": cat_changed, "anchor_pass_flipped": pass_flipped,
        "f1_recomputed_from_channels": f1_recomputed,
        "f1_from_stored_rounded": f1_from_stored,
        "f1_boundary_docs": len(boundary),
        "f1_boundary_examples": boundary[:20],
        "f1_exact_stale_docs": len(exact_stale),
        "f1_exact_stale_examples": exact_stale[:20],
        "basis_before": dict(basis_before), "basis_after": dict(basis_after),
        # The audit checklist reads `basis_counts`; keep it as the explicit
        # before/after pair so a reader does not have to know the two older
        # keys are the same numbers.
        "basis_counts": {"before": dict(basis_before), "after": dict(basis_after)},
        "tier_transitions": tier_transitions,
        "high_by_lang": dict(Counter(r["lang"] for r in recs if r["tier"] == "high")),
    }
    print(json.dumps(receipt, ensure_ascii=False))
    if dry:
        return 0
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    arch = path_of("data") / "archive" / f"preretier_{stamp}"
    arch.mkdir(parents=True, exist_ok=True)
    shutil.copy2(silver, arch / "silver.jsonl")
    tmp = silver.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, silver)
    out = path_of("data") / "metrics" / f"anchor_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    receipt["at_utc"] = utc_iso()
    receipt["archive"] = str(arch / "silver.jsonl")
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"receipt {out}")
    m.kv_set("retier", {"at_utc": utc_iso(), "records": len(recs),
                        "changed": changed, "tiers": tiers,
                        "receipt": str(out)})
    print(f"written {silver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
