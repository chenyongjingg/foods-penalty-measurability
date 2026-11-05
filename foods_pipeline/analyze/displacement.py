"""Displacement coding, six types (Plan §3, §6.1 E4).

A displacement event is an *adaptation after a governance shock*, not merely a
fraud technique. Two guards implement that definition:

1. the document must be in the main corpus and from the Chinese frame — the
   US sample is a typology comparison and its records describe single recalls,
   not post-enforcement adaptations;
2. the matched phrase must sit within `CONTEXT_CHARS` of a governance term
   (处罚/查处/打击/立案/判决…), so "异地" in a company address does not count as
   spatial displacement.

Coding is deterministic and auditable (no LLM in the main path).
"""
from __future__ import annotations

import json
import re

from ..common import cfg, get_logger, path_of, utc_iso, write_json
from ..manifest import Manifest

PATTERNS = {
    "spatial": [r"跨(?:省|市|地区)(?:生产|经营|销售|运输)", r"转移(?:至|到)(?:其他|外|别)",
                r"异地(?:生产|经营|销售)", r"外省(?:生产|经营)"],
    "temporal": [r"(?:处罚|查处|检查)(?:后|之后)(?:继续|再次|仍)", r"夜间(?:生产|经营)",
                 r"节假日后"],
    "target": [r"转向(?:其他|另一)", r"改为(?:生产|销售|经营)(?:其他|另一)", r"换(?:品类|产品)"],
    "tactical": [r"更换(?:手法|方式|方法)", r"改用", r"不再使用", r"新手法"],
    "functional": [r"转向(?:相邻|其他)(?:服务|业务)", r"代办(?:其他|认证|检测)", r"兼营"],
    "perpetrator": [r"借用(?:他人|他人资质)", r"实际控制人", r"换人", r"他人名义", r"挂靠"],
}

GOVERNANCE = re.compile(r"处罚|查处|打击|整治|专项|立案|判决|通报|没收|罚款")
CONTEXT_CHARS = 60


def _contextual(text: str, start: int, end: int) -> bool:
    lo, hi = max(0, start - CONTEXT_CHARS), min(len(text), end + CONTEXT_CHARS)
    return bool(GOVERNANCE.search(text[lo:hi]))


def _scan(rows: list[dict], m: Manifest) -> tuple[list[dict], int]:
    """Apply every pattern to every document in `rows` (one row per doc)."""
    hits, scanned = [], 0
    for r in rows:
        doc_id = r["doc_id"]
        rec = m.get(doc_id)
        if not rec or not rec.get("text_path"):
            continue
        try:
            text = open(rec["text_path"], encoding="utf-8").read()
        except Exception:
            continue
        scanned += 1
        found = {}
        for typ, pats in PATTERNS.items():
            for pat in pats:
                mm = re.search(pat, text)
                if mm and _contextual(text, mm.start(), mm.end()):
                    found[typ] = mm.group(0)
                    break
        if found:
            hits.append({"doc_id": doc_id, "types": found, "tier": r.get("tier")})
    return hits, scanned


def run() -> dict:
    from ..common import iter_jsonl
    p = path_of("data") / "extracted" / "dataset.jsonl"
    docs: dict[str, list] = {}
    wide: dict[str, dict] = {}
    if p.exists():
        for r in iter_jsonl(p):
            if r["source"] not in ("cfws", "municipal"):
                continue
            # One row per document is enough for the wide scan; the main corpus
            # keeps the pre-registered high-tier restriction.
            wide.setdefault(r["doc_id"], r)
            if r.get("main_corpus"):
                docs.setdefault(r["doc_id"], []).append(r)
    outdir = path_of("data") / "analysis"
    m = Manifest()
    hits, scanned = _scan([v[0] for v in docs.values()], m)
    # Sensitivity: the same rule applied to every Chinese tier. The main
    # corpus is the headline, but a zero there is uninterpretable without
    # knowing whether the detector can fire anywhere (D-57).
    wide_hits, wide_scanned = _scan(list(wide.values()), m)
    counts: dict = {}
    for h in hits:
        for t in h["types"]:
            counts[t] = counts.get(t, 0) + 1
    floor = int(cfg("analysis.e4_events_floor", 8))
    target = int(cfg("analysis.e4_events_target", 15))
    # "0 events" is only a finding if documents were actually read. The
    # denominator travels with the count so a corpus that failed to load
    # cannot be mistaken for a corpus with no displacement.
    if scanned == 0:
        status = "not_estimable"
    elif len(hits) >= target:
        status = "target_met"
    elif len(hits) >= floor:
        status = "floor_met"
    else:
        status = "downgraded_to_qualitative"
    wide_counts: dict = {}
    for h in wide_hits:
        for t in h["types"]:
            wide_counts[t] = wide_counts.get(t, 0) + 1
    wide_by_tier: dict = {}
    for h in wide_hits:
        wide_by_tier[h.get("tier")] = wide_by_tier.get(h.get("tier"), 0) + 1
    res = {"n_events": len(hits), "by_type": counts, "status": status,
           "denominator": {"n_docs_in_scope": len(docs), "n_docs_scanned": scanned},
           "rule": {"context_chars": CONTEXT_CHARS,
                    "requires": "governance term within context window",
                    "corpus": "main corpus, cfws/municipal only"},
           "sensitivity_all_chinese_tiers": {
               "n_events": len(wide_hits), "by_type": wide_counts,
               "by_tier": wide_by_tier,
               "n_docs_in_scope": len(wide), "n_docs_scanned": wide_scanned,
               "note": ("Same rule, every Chinese tier. Reported so a zero in the "
                        "main corpus is not read as a dead detector: if this is "
                        "also zero, the pattern set never fires anywhere in the "
                        "corpus (D-57). The headline status is still decided by "
                        "the main-corpus count.")},
           "events": hits[:200], "at_utc": utc_iso()}
    write_json(outdir / "displacement.json", res)
    get_logger("analyze.displacement").info("displacement: %s events=%d", status, len(hits))
    return res
