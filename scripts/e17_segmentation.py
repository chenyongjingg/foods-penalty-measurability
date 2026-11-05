#!/usr/bin/env python
"""D-127: does word segmentation remove the boundary artefacts, and what does it cost?

R0  literal substring match over the full text (frozen E12 rule; must reproduce its counts)
R1  a term counts only if it can be assembled from consecutive jieba tokens, i.e. both
    ends of the hit fall on a token boundary

Both directions are reported: what R1 removes and what R1 loses. On the 270 adjudicated
items the same verdicts are reused, so a rule that deletes false matches and a rule that
deletes true subjects cannot look the same in the output.

Each document is segmented ONCE and then tested against all 18 term lists; segmenting
per (document, category) would repeat the same work eighteen times.

jieba lives in /opt/foods/third_party (PYTHONPATH), never in the project venv.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/foods/third_party")

import jieba  # noqa: E402

ROOT = Path("/opt/foods")
SILVER = ROOT / "data/silver/silver.jsonl"
INDEX = ROOT / "data/analysis/e12_commodity_index.json"
HUMAN = ROOT / "data/analysis/e12_commodity_precision.json"
OUT = ROOT / "data/analysis/e17_segmentation.json"
CRITERION = "D-127"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_for(did: str) -> Path:
    return ROOT / "data/clean/docs" / f"{did.replace(':', '_')}.txt"


def boundaries(text: str):
    """Character offsets of jieba token starts and ends, plus the token set."""
    starts, ends, pos, toks = set(), set(), 0, []
    for t in jieba.lcut(text):
        if not t.strip():
            pos += len(t)
            continue
        starts.add(pos)
        pos += len(t)
        ends.add(pos)
        toks.append(t)
    return starts, ends, toks


def hits_on_boundaries(text: str, terms, starts, ends) -> set[str]:
    out = set()
    for term in terms:
        i = text.find(term)
        while i != -1:
            if i in starts and (i + len(term)) in ends:
                out.add(term)
                break
            i = text.find(term, i + 1)
    return out


def main() -> None:
    recs = [json.loads(l) for l in SILVER.open(encoding="utf-8")]
    silver_sha = sha(SILVER)
    if not silver_sha.startswith("a1deda2c"):
        raise SystemExit(f"REFUSED: silver sha {silver_sha[:8]}")

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    lexicon = {int(k): v for k, v in index["lexicon"].items()}
    human = json.loads(HUMAN.read_text(encoding="utf-8"))
    terms = {cid: [t for t in v["terms"] if t] for cid, v in lexicon.items()}

    texts = {}
    for r in recs:
        p = path_for(r["doc_id"])
        if p.exists():
            texts[r["doc_id"]] = p.read_text(encoding="utf-8")
    print(f"docs {len(texts)}", flush=True)

    r0_counts = {c: 0 for c in lexicon}
    r1_counts = {c: 0 for c in lexicon}
    docs_r0 = {c: set() for c in lexicon}
    docs_r1 = {c: set() for c in lexicon}
    lost, gained = {c: {} for c in lexicon}, {c: {} for c in lexicon}
    per_doc = {}

    t0 = time.time()
    for n, (did, text) in enumerate(sorted(texts.items()), 1):
        starts, ends, _ = boundaries(text)
        row = {}
        for cid, ts in terms.items():
            a = {t for t in ts if t in text}
            b = hits_on_boundaries(text, ts, starts, ends)
            if a:
                r0_counts[cid] += 1
                docs_r0[cid].add(did)
            if b:
                r1_counts[cid] += 1
                docs_r1[cid].add(did)
            for t in a - b:
                lost[cid][t] = lost[cid].get(t, 0) + 1
            for t in b - a:
                gained[cid][t] = gained[cid].get(t, 0) + 1
            if a or b:
                row[cid] = (bool(a), bool(b))
        per_doc[did] = row
        if n % 100 == 0:
            print(f"[e17] {n}/{len(texts)} {time.time()-t0:.0f}s", flush=True)

    frozen = {int(k): v["n_docs"] for k, v in index["categories"].items()}
    mismatch = {str(k): [frozen[k], r0_counts[k]] for k in frozen if frozen[k] != r0_counts[k]}

    crosstab = {"R0_pass_R1_pass": 0, "R0_pass_R1_drop": 0,
                "R0_drop_R1_pass": 0, "both_drop": 0}
    dropped = {"S": 0, "I": 0, "T": 0, "F": 0}
    s_total = s_r1 = n_r1 = 0
    for it in human["items"]:
        did, cid = it["doc_id"], it["category"]
        r0, r1 = per_doc.get(did, {}).get(cid, (False, False))
        if r0 and r1:
            crosstab["R0_pass_R1_pass"] += 1
        elif r0 and not r1:
            crosstab["R0_pass_R1_drop"] += 1
            dropped[it["verdict"]] += 1
        elif r1:
            crosstab["R0_drop_R1_pass"] += 1
        else:
            crosstab["both_drop"] += 1
        if it["verdict"] == "S":
            s_total += 1
            s_r1 += 1 if r1 else 0
        n_r1 += 1 if r1 else 0

    out = {
        "at_utc": utc(), "criterion_register": CRITERION,
        "role": "segmentation_sensitivity_two_directional",
        "jieba": {"version": jieba.__version__, "mode": "lcut default",
                  "user_dict": False, "path": "/opt/foods/third_party"},
        "rule_r0": "literal substring over full text (frozen E12 rule)",
        "rule_r1": "term must be assembled from consecutive jieba tokens (both ends on a boundary)",
        "inputs": {"silver_sha256": silver_sha, "index_sha256": sha(INDEX),
                   "human_sha256": sha(HUMAN)},
        "baseline_self_check": {"reproduced_frozen_counts": not mismatch, "mismatch": mismatch},
        "per_category": {
            str(cid): {
                "name": lexicon[cid]["name"],
                "R0_docs": r0_counts[cid], "R1_docs": r1_counts[cid],
                "lost_docs": len(docs_r0[cid] - docs_r1[cid]),
                "gained_docs": len(docs_r1[cid] - docs_r0[cid]),
                "terms_lost": dict(sorted(lost[cid].items(), key=lambda kv: -kv[1])[:10]),
                "terms_gained": dict(sorted(gained[cid].items(), key=lambda kv: -kv[1])[:10]),
            } for cid in lexicon
        },
        "totals": {"R0_docs_any": len(set().union(*docs_r0.values())),
                   "R1_docs_any": len(set().union(*docs_r1.values())),
                   "frozen_any": index.get("n_docs_any_commodity_term")},
        "adjudicated_270": {
            "crosstab": crosstab, "dropped_by_verdict": dropped,
            "subject_cases_R0": s_total, "subject_cases_surviving_R1": s_r1,
            "R1_pass_items": n_r1,
            "subject_precision_R0": round(s_total / 270, 4),
            "subject_precision_R1": round(s_r1 / n_r1, 4) if n_r1 else None,
            "note": "the frozen product reports 104/270 = 0.3852 for R0; R1's denominator "
                    "is the items R1 still passes, so the two are not the same quantity "
                    "unless the crosstab shows no drops",
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("crosstab", crosstab)
    print("dropped by verdict", dropped)
    print("subject precision R0/R1", out["adjudicated_270"]["subject_precision_R0"],
          out["adjudicated_270"]["subject_precision_R1"])
    print("sha", sha(OUT))


if __name__ == "__main__":
    main()
