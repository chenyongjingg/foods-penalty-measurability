#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure the labelling instrument's run-to-run noise under a frozen protocol.

Why (D-44): comparing the archived v1 silver against the v2 re-label on 621
documents with byte-identical text showed the mean agreement moving
0.7585 -> 0.7026, and channel A (temperature 0) changing its entity set on 41%
of those documents. A deterministic channel that changes its answer on the same
input means the difference cannot be attributed to the protocol change alone.
This script does not change any result: it re-labels a fixed stratified sample
with the *current* code and writes a separate receipt, so the noise band of
agreement and the tier-flip rate can be quoted instead of guessed.

Read-only with respect to silver.jsonl / the docs table. Output:
data/metrics/stability_v2.json.

Usage: ./venv/bin/python scripts/stability_v2.py [--n 48] [--workers 1] [--seed 20261104]
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foods_pipeline.label.silver import Labeler  # noqa: E402
from foods_pipeline.common import utc_iso  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load_silver(p: Path) -> dict:
    out = {}
    with p.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["doc_id"]] = r
    return out


def sample_stratified(recs: dict, n: int, seed: int) -> list[dict]:
    """Proportional by (lang, tier), floor 4 per cell, capped by availability."""
    cells = defaultdict(list)
    for d, r in recs.items():
        cells[(r.get("lang") or "zh", r.get("tier") or "low")].append(d)
    for v in cells.values():
        v.sort()
    total = sum(len(v) for v in cells.values())
    picked = []
    for key in sorted(cells):
        v = cells[key]
        quota = max(4, round(n * len(v) / total)) if total else 0
        rng = random.Random(f"{seed}:{key[0]}:{key[1]}")
        picked.extend(rng.sample(v, min(quota, len(v))))
    rng = random.Random(seed)
    picked = sorted(set(picked))
    if len(picked) > n:
        picked = sorted(rng.sample(picked, n))
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seed", type=int, default=20261104)
    ap.add_argument("--out", default="data/metrics/stability_v2.json")
    a = ap.parse_args()

    silver = load_silver(ROOT / "data" / "silver" / "silver.jsonl")
    ids = sample_stratified(silver, a.n, a.seed)

    con = sqlite3.connect(f"file:{ROOT/'state'/'foods.sqlite'}?mode=ro", uri=True)
    rows = {r[0]: r[1:] for r in con.execute(
        "select doc_id, source, lang, text_path, meta from docs")}
    con.close()

    lab = Labeler()
    if not lab.llm.health():
        print("LLM unreachable", file=sys.stderr)
        return 2

    def work(doc_id: str):
        src, lang, text_path, meta = rows[doc_id]
        text = Path(text_path).read_text(encoding="utf-8")
        doc = {"doc_id": doc_id, "source": src, "lang": lang or "zh",
               "meta": meta or "{}"}
        rec, reason = lab._one(doc, text, doc["lang"])
        return doc_id, rec, reason

    results, errors = [], []
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
        futs = {pool.submit(work, d): d for d in ids}
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                doc_id, rec, reason = fut.result()
            except Exception as exc:  # noqa: BLE001
                errors.append({"doc_id": d, "error": f"{type(exc).__name__}: {exc}"})
                continue
            if not rec:
                errors.append({"doc_id": d, "error": reason or "rejected"})
                continue
            old = silver[doc_id]
            old_f1 = (old.get("metrics") or {}).get("agreement_f1") or 0.0
            new_f1 = rec["metrics"]["agreement_f1"]
            results.append({
                "doc_id": doc_id, "lang": rec["lang"],
                "tier_a": old.get("tier"), "tier_b": rec["tier"],
                "f1_a": old_f1, "f1_b": new_f1, "delta": round(new_f1 - old_f1, 4),
                "adjudicated_a": (old.get("metrics") or {}).get("adjudicated"),
                "adjudicated_b": rec["metrics"]["adjudicated"],
                "cat_a": old.get("violation_category"),
                "cat_b": rec["violation_category"],
            })

    d = [r["delta"] for r in results]
    tiers = Counter((r["tier_a"], r["tier_b"]) for r in results)
    summary = {
        "n_requested": len(ids), "n_scored": len(results), "n_errors": len(errors),
        "mean_f1_a": round(statistics.mean(r["f1_a"] for r in results), 4) if results else None,
        "mean_f1_b": round(statistics.mean(r["f1_b"] for r in results), 4) if results else None,
        "mean_delta": round(statistics.mean(d), 4) if d else None,
        "sd_delta": round(statistics.stdev(d), 4) if len(d) > 1 else None,
        "tier_same": sum(v for (x, y), v in tiers.items() if x == y),
        "tier_changed": sum(v for (x, y), v in tiers.items() if x != y),
        "tier_transitions": {f"{x}->{y}": v for (x, y), v in sorted(tiers.items())},
        "cat_same": sum(1 for r in results if r["cat_a"] == r["cat_b"]),
        "adjudicated_a": sum(1 for r in results if r["adjudicated_a"]),
        "adjudicated_b": sum(1 for r in results if r["adjudicated_b"]),
        "seed": a.seed, "workers": a.workers,
        "protocol": {"doc_text_chars": None, "note": "same as the run that produced silver.jsonl"},
    }
    try:
        from foods_pipeline.label import prompts
        summary["protocol"]["prompt_hashes"] = prompts.version()
        from foods_pipeline.common import cfg
        summary["protocol"]["doc_text_chars"] = int(cfg("label.doc_text_chars", 0))
        summary["protocol"]["max_tokens"] = {
            "a": cfg("llm.channel_a.max_tokens"), "b": cfg("llm.channel_b.max_tokens"),
            "adj": cfg("llm.adjudicator.max_tokens")}
    except Exception:  # noqa: BLE001
        pass
    summary["at_utc"] = utc_iso()

    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "per_doc": sorted(
        results, key=lambda r: r["doc_id"]), "errors": errors}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
