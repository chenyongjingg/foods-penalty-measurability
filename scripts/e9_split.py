#!/usr/bin/env python3
"""Train/eval split audit for E9 (D-95): how many anchored evaluation documents the
adapter also trained on. Computed from products only; no model call."""
import hashlib, json, sys, time
from pathlib import Path
ROOT = Path("/opt/foods"); sys.path.insert(0, str(ROOT))
from foods_pipeline.label.anchors import anchor_pairs

train = [json.loads(l) for l in (ROOT/"data/train/selftrain.jsonl").open(encoding="utf-8") if l.strip()]
sil = [json.loads(l) for l in (ROOT/"data/silver/silver.jsonl").open(encoding="utf-8") if l.strip()]
evalset = [r for r in sil if (r.get("anchor") or {}).get("basis") in
           ("penalty_statute", "cited_statute", "statute+fact", None)
           and (r.get("anchor") or {}).get("category")]
pairs, fact_only = anchor_pairs(evalset)
assert len(pairs) == len(evalset), "eval set disagrees with anchor_pairs"
tids = {r.get("doc_id") for r in train}; eids = {r["doc_id"] for r in evalset}
overlap = sorted(tids & eids)
out = {
    "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "product": "E9 train/eval split audit (D-95)",
    "silver_sha256": hashlib.sha256((ROOT/"data/silver/silver.jsonl").read_bytes()).hexdigest(),
    "n_train": len(tids), "n_eval": len(eids), "n_overlap": len(overlap),
    "n_clean_eval": len(eids - tids), "fact_only_excluded": fact_only,
    "overlap_doc_ids": overlap,
    "rule": "primary figure = clean subset (eval minus train); full-set figure = leakage_inflated",
}
p = ROOT/"data/analysis/e9_split.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("n_train","n_eval","n_overlap","n_clean_eval")}))
