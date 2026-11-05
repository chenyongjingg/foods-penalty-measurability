"""D1' keyword sensitivity (Plan P115, rigor check).

The inclusion rule is a lexical conjunction: a fraud term AND a document-type
term AND a food context. Any such rule draws a line, and the corpus on one side
of it is not the same population as the corpus on the other. This module
re-computes the rule under the fixed variants in `analysis.keyword_variants`
(declared in config before this ran) over the *whole admission frame* — the
documents the current rule admits and the ones it drops — and reports how many
documents each variant moves in or out.

It is descriptive: it does not re-label anything and it does not change the
corpus. Its job is to make the boundary visible, so that a reviewer can see
whether a conclusion depends on the particular term list.

Scope: Chinese documents from the D1' frame (cfws, municipal). openFDA records
are included by their API query (DEVIATIONS D-8/D-16) and are out of scope.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..common import cfg, get_logger, path_of, utc_iso, write_json
from ..clean.normalize import _term_near, extract_text, lang_of, mask_pii, normalize
from ..manifest import Manifest


def _frame_texts(m: Manifest) -> list[dict]:
    """Every Chinese document that reached the intake decision, with its text.

    Clean documents have a stored text file; filtered documents keep theirs in
    data/clean/filtered (written by Cleaner) or, for documents filtered before
    that directory existed, are re-extracted from the raw file — the raw store
    is append-only, so the text is recoverable.
    """
    out = []
    with m.conn() as c:
        rows = c.execute(
            "SELECT doc_id, source, stage, text_path, raw_path, meta, lang FROM docs "
            "WHERE stage IN ('clean','labeled','extracted','filtered_out','duplicate','failed')"
        ).fetchall()
    filt_dir = path_of("data") / "clean" / "filtered"
    # Documents filtered out before that directory existed are re-extracted
    # here; the write below needs the directory to exist.
    filt_dir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        if r["source"] not in ("cfws", "municipal"):
            continue
        text = None
        p = r["text_path"]
        if p and Path(p).exists():
            text = Path(p).read_text(encoding="utf-8")
        else:
            fp = filt_dir / f"{r['doc_id'].replace(':', '_')}.txt"
            if fp.exists():
                text = fp.read_text(encoding="utf-8")
            elif r["raw_path"] and Path(r["raw_path"]).exists():
                try:
                    meta = json.loads(r["meta"] or "{}")
                    raw, _kind = extract_text(r["raw_path"], meta)
                    if len((raw or "").strip()) >= 40:
                        text = normalize(mask_pii(raw))
                        fp.write_text(text, encoding="utf-8")
                except Exception:  # noqa: BLE001
                    text = None
        if not text or len(text.strip()) < 40:
            continue
        if lang_of(text) != "zh":
            continue
        out.append({"doc_id": r["doc_id"], "stage": r["stage"],
                    "text": text, "chars": len(text)})
    return out


def _decide(text: str, fraud: list[str], doc: list[str], food: list[str],
            window: int, proximity: bool) -> bool:
    has_fraud = any(t in text for t in fraud)
    has_doc = any(t in text for t in doc)
    has_food = any(t in text for t in food)
    if not (has_fraud and has_doc and has_food):
        return False
    if not proximity:
        return True
    return _term_near(text, fraud, doc, window)


def run() -> dict:
    m = Manifest()
    docs = _frame_texts(m)
    base_fraud = list(cfg("intake.fraud_terms", []))
    base_doc = list(cfg("intake.document_terms", []))
    base_food = list(cfg("intake.food_terms", []))
    window = int(cfg("intake.window_chars", 80))
    variants = cfg("analysis.keyword_variants", []) or [{"id": "plan_rule"}]

    # The high-tier documents are what the main estimates rest on; a variant
    # that loses many of them matters more than one that gains junk.
    high_ids = set()
    silver = path_of("data") / "silver" / "silver.jsonl"
    if silver.exists():
        with open(silver, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get("tier") == "high" and r.get("lang") == "zh":
                        high_ids.add(r["doc_id"])

    sets, res = {}, {"frame": len(docs), "variants": {}, "at_utc": utc_iso()}
    for v in variants:
        vid = v.get("id")
        fraud = [t for t in base_fraud if t not in (v.get("drop_fraud") or [])]
        fraud += [t for t in (v.get("add_fraud") or []) if t not in fraud]
        doc_terms = list(v.get("document_terms") or base_doc)
        prox = bool(v.get("require_proximity", False))
        admitted = {d["doc_id"] for d in docs
                    if _decide(d["text"], fraud, doc_terms, base_food, window, prox)}
        sets[vid] = admitted
    # The baseline is the configured rule. If it is absent from the variant
    # list, fall back to the first variant but say so in the output — an empty
    # baseline set is a real result, not a reason to pick another variant.
    if "plan_rule" in sets:
        base, base_id = sets["plan_rule"], "plan_rule"
    else:
        base_id = next(iter(sets), None)
        base = sets.get(base_id, set())
    res["baseline_variant"] = base_id
    for vid, admitted in sets.items():
        res["variants"][vid] = {
            "admitted": len(admitted),
            "vs_baseline": {"added": len(admitted - base), "dropped": len(base - admitted),
                             "jaccard": round(len(admitted & base) / len(admitted | base), 4)
                             if (admitted | base) else None},
            "high_tier_retained": (round(len(admitted & high_ids) / len(high_ids), 4)
                                   if high_ids else None),
            "high_tier_lost": sorted(high_ids - admitted),
        }
    # What the current rule admits out of the whole frame — the number that
    # makes "the corpus is a boundary, not a population" concrete.
    res["plan_rule_admitted_share"] = round(len(base) / len(docs), 4) if docs else None
    res["high_tier_n"] = len(high_ids)
    res["notes"] = ("descriptive only; the corpus is not rebuilt from these variants. "
                    "plan_rule is the configured rule, so added/dropped are 0 by construction.")
    outdir = path_of("data") / "analysis"
    write_json(outdir / "keyword_sensitivity.json", res)
    get_logger("analyze.keywords").info(
        "keyword sensitivity: frame=%d admitted=%d", len(docs), len(base))
    return res
