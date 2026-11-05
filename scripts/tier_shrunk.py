"""Plan P095 entity-type shrinkage, written as a product-layer corpus variant.

Plan P095: when E1 still misses and agreement is below 0.75, shrink the entity
type set; if the paper is still short of the bar it becomes a methods-and-limits
Communication. M-6 declined to apply the shrinkage when agreement was 0.7585,
i.e. above the trigger. On protocol v2 the full-set mean agreement is below
0.75 (see data/metrics/e1.json), so the trigger is now met and the decision had
to be reopened (DEVIATIONS.md D-53).

What this script does NOT do: it does not change E1's status, does not rewrite
the stored tier in silver.jsonl, and does not claim agreement improved. Type
selection is a narrower question, not a better answer. It writes a separate
corpus variant so every downstream estimate can be reported twice -- once on
the pre-registered full-type corpus, once on the P095-shrunk corpus.

Selection rule (fixed in the plan and in evaluate_e1, applied here unchanged):
a type is kept when its pooled agreement F1 >= 0.75 and its combined support
(n_a + n_b) >= 20.

Output: data/metrics/tier_shrunk.json

Usage: python scripts/tier_shrunk.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import path_of, utc_iso  # noqa: E402
from foods_pipeline.label import align  # noqa: E402

TAU = 0.5
TARGET, FLOOR = 0.85, 0.75
SHRINK_MIN_F1 = 0.75
SHRINK_MIN_SUPPORT = 20
ACTOR_TYPES = ("SERVICE_PROVIDER", "END_USER")


def _pair(r: dict) -> tuple[list[dict], list[dict]]:
    ch = r.get("channels") or {}
    return list(ch.get("a") or []), list(ch.get("b") or [])


def _agreement(recs: list[dict], types: set[str] | None = None) -> dict:
    """Mirror of evaluate_e1._agreement: pooled per-type F1 + per-doc mean."""
    tps, na, nb = Counter(), Counter(), Counter()
    per_doc = []
    for r in recs:
        a, b = _pair(r)
        if types is not None:
            a = [e for e in a if e.get("type") in types]
            b = [e for e in b if e.get("type") in types]
        if not a and not b:
            continue
        pairs = align.match(a, b, TAU)
        for x, _, _ in pairs:
            tps[x.get("type")] += 1
        for e in a:
            na[e.get("type")] += 1
        for e in b:
            nb[e.get("type")] += 1
        per_doc.append(align.micro_f1(a, b, TAU)[2])
    per_type = {}
    for t in set(tps) | set(na) | set(nb):
        p = tps[t] / na[t] if na[t] else 0.0
        rr = tps[t] / nb[t] if nb[t] else 0.0
        per_type[t] = {
            "f1": round(2 * p * rr / (p + rr), 4) if (p + rr) else 0.0,
            "n_a": na[t], "n_b": nb[t], "tp": tps[t],
            "support": na[t] + nb[t],
        }
    return {
        "mean_agreement": round(sum(per_doc) / len(per_doc), 4) if per_doc else 0.0,
        "n_scored": len(per_doc),
        "per_type": per_type,
    }


def _tier(r: dict, f1: float) -> str:
    if f1 >= TARGET and (r.get("anchor_pass") or r.get("lang") != "zh"):
        return "high"
    if f1 >= FLOOR:
        return "medium"
    return "low"


def _stored_f1(r: dict) -> float:
    mt = r.get("metrics") or {}
    v = mt.get("agreement_f1_exact")
    if isinstance(v, (int, float)):
        return float(v)
    return float(mt.get("agreement_f1") or 0.0)


def main() -> int:
    silver = path_of("data") / "silver" / "silver.jsonl"
    raw = silver.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    recs = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]

    full = _agreement(recs)
    stable = sorted(
        t for t, v in full["per_type"].items()
        if v["f1"] >= SHRINK_MIN_F1 and v["support"] >= SHRINK_MIN_SUPPORT)
    shrunk = _agreement(recs, set(stable))
    dropped = sorted(t for t in full["per_type"] if t not in stable)

    # Re-tier each document on the stable subset. The anchor rule is unchanged,
    # and the stored tier is read from the record so the movement is auditable.
    transitions = Counter()
    shrunk_tier = {}
    for r in recs:
        a, b = _pair(r)
        a = [e for e in a if e.get("type") in stable]
        b = [e for e in b if e.get("type") in stable]
        if not a and not b:
            shrunk_tier[r["doc_id"]] = None   # no stable-type entity at all
            transitions[(r.get("tier"), "unscored")] += 1
            continue
        t = _tier(r, align.micro_f1(a, b, TAU)[2])
        shrunk_tier[r["doc_id"]] = t
        transitions[(r.get("tier"), t)] += 1

    def _counts(key) -> dict:
        c = Counter(key(r) for r in recs)
        return {k: c.get(k, 0) for k in ("high", "medium", "low")}

    stored_counts = _counts(lambda r: r.get("tier"))
    shrunk_counts = _counts(lambda r: shrunk_tier[r["doc_id"]])

    by_lang = {}
    for lang in ("zh", "en"):
        sub = [r for r in recs if r.get("lang") == lang]
        by_lang[lang] = {
            "n": len(sub),
            "stored": {k: v for k, v in Counter(r.get("tier") for r in sub).items()},
            "shrunk": {k: v for k, v in Counter(
                shrunk_tier[r["doc_id"]] for r in sub).items()},
        }

    # Does the shrunk corpus rescue the actor network? The shrinking rule drops
    # SERVICE_PROVIDER by construction when it is unstable, so measure the
    # actor structure directly instead of assuming it. This is an UPPER BOUND
    # read off silver channel A, not the gate's graph: the extract stage grounds
    # spans and, on voted documents, keeps the matched intersection (D-64), so
    # `stored_high` here can exceed
    # `network_metrics.actor_coverage.docs_with_two_or_more_actor_nodes`.
    # Node identity follows analyze/network.build() (normalised name,
    # deduplicated within a document). The main network is Chinese-only, so the
    # zh row is the one that matters.
    def _nodes(r: dict) -> tuple[set[str], set[str], set[str]]:
        a, _ = _pair(r)
        names, prov, endu = set(), set(), set()
        for e in a:
            if e.get("type") not in ACTOR_TYPES:
                continue
            # silver records carry `text` only; `normalized` is added by the
            # extract stage into dataset.jsonl. Text is the closest available
            # stand-in for node identity here, and it is conservative: it
            # under-merges rather than over-merges.
            nm = (e.get("normalized") or e.get("text") or "").strip()
            for ch in " \t\r\n（）()【】[]":
                nm = nm.replace(ch, "")
            if not nm:
                continue
            names.add(nm)
            (prov if e.get("type") == "SERVICE_PROVIDER" else endu).add(nm)
        return names, prov, endu

    act = {}
    for name, key in (("stored_high", lambda r: r.get("tier")),
                      ("shrunk_high", lambda r: shrunk_tier[r["doc_id"]])):
        row = {"docs": 0, "docs_with_any_actor_node": 0,
               "docs_with_two_or_more_actor_nodes": 0,
               "docs_with_provider": 0, "docs_with_provider_and_end_user": 0,
               "max_edges_possible_by_structure": 0}
        for r in recs:
            if key(r) != "high" or r.get("lang") != "zh":
                continue
            names, prov, endu = _nodes(r)
            row["docs"] += 1
            row["docs_with_any_actor_node"] += bool(names)
            row["docs_with_two_or_more_actor_nodes"] += len(names) >= 2
            row["docs_with_provider"] += bool(prov)
            row["docs_with_provider_and_end_user"] += bool(prov and endu)
            row["max_edges_possible_by_structure"] += len(names) * (len(names) - 1) // 2
        act[name] = row
    act["scope"] = ("Chinese high-tier documents only, channel a, node identity "
                    "= normalised name deduplicated within the document. This is "
                    "an upper bound reconstructed from silver channels, NOT the "
                    "extracted graph: grounding and the matched-intersection rule "
                    "on voted documents (D-64) only remove mentions, so it can "
                    "exceed network_metrics.actor_coverage. Quote that block for "
                    "the §6 structural ceiling (D-54, D-66).")

    out = {
        "at_utc": utc_iso(),
        "input": str(silver),
        "input_sha256": sha,
        "n_records": len(recs),
        "rule": {"min_type_f1": SHRINK_MIN_F1, "min_type_support": SHRINK_MIN_SUPPORT,
                 "tau": TAU, "target": TARGET, "floor": FLOOR},
        "full_set": {"mean_agreement": full["mean_agreement"],
                     "n_scored": full["n_scored"],
                     "per_type": full["per_type"]},
        "stable_types": stable,
        "dropped_types": dropped,
        "shrunk_set": {"mean_agreement": shrunk["mean_agreement"],
                       "n_scored": shrunk["n_scored"]},
        "tier_counts": {"stored": stored_counts, "shrunk": shrunk_counts},
        "tier_transitions": [{"from": k[0], "to": k[1], "n": v}
                             for k, v in sorted(transitions.items(),
                                                key=lambda x: (str(x[0][0]), str(x[0][1])))],
        "by_lang": by_lang,
        "actor_structure": act,
        "e1_status_unchanged": True,
        "note": ("This is a corpus variant mandated by plan P095, not a new E1 "
                 "result. E1 stays graded on the full type set so that a "
                 "post-hoc type selection cannot masquerade as agreement. "
                 "Shrinkage redefines the question; it must never be reported "
                 "as an improvement. Every downstream estimate that depends on "
                 "entity types must be given on both corpora, labelled (D-53)."),
    }
    dst = path_of("data") / "metrics" / "tier_shrunk.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"wrote {dst}\ninput sha={sha[:16]} n={len(recs)}")
    print(f"full agreement {full['mean_agreement']:.4f} -> "
          f"shrunk {shrunk['mean_agreement']:.4f} on {stable}")
    print(f"dropped: {dropped}")
    print(f"tiers stored {stored_counts} -> shrunk {shrunk_counts}")
    print(f"actor structure (zh high): {json.dumps(act, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
