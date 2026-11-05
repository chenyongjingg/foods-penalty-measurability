#!/usr/bin/env python
"""D-111 (appended under a duplicate heading D-108; canonical ID fixed by D-110).

Food-commodity keyword presence index over the frozen cleaned full texts.

This is a *literal substring presence* measurement at document level, not a
classifier, not a label, and not a prevalence estimate. "Term absent" does not
mean "commodity absent": a document may name only a brand, an alias, or only the
violation. The lexicon below was fixed in the deviation register BEFORE any count
was taken and must not be edited after this script has run.

Matching rule (as registered): Python `in` on the raw UTF-8 text of
data/clean/docs/<doc_id>.txt. No tokenisation, no regex wildcards, no case or
variant folding. Document header counts as part of the text.

Outputs
  data/analysis/e12_commodity_index.json     counts + per-category doc_id lists
  data/analysis/e12_precision_sample.json    context windows for the adjudication
                                             sample, chosen by sha256(doc_id) order
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path("/opt/foods")
SILVER = ROOT / "data/silver/silver.jsonl"
DOCS = ROOT / "data/clean/docs"
OUT = ROOT / "data/analysis/e12_commodity_index.json"
SAMPLE_OUT = ROOT / "data/analysis/e12_precision_sample.json"

CRITERION = "D-111"
WINDOW = 120          # +-120 characters around each hit, as registered
SAMPLE_N = 15         # first min(15, N_k) doc_ids in sha256(doc_id) order
MAX_TERMS_SHOWN = 6   # bound the sample file; every matched term still counted

# ---------------------------------------------------------------------------
# LEXICON — fixed in D-111 before any counting. Do not edit after the first run.
# ---------------------------------------------------------------------------
LEXICON: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("粮食及其制品", ("大米", "小米", "面粉", "挂面", "馒头", "米粉", "年糕", "粽子", "玉米", "小麦")),
    2: ("食用油脂", ("食用油", "植物油", "花生油", "菜籽油", "大豆油", "调和油", "猪油")),
    3: ("生鲜肉", ("猪肉", "牛肉", "羊肉", "鸡肉", "鸭肉", "鹅肉", "鲜肉", "冻肉")),
    4: ("肉制品", ("火腿", "香肠", "腊肉", "肉干", "肉丸", "卤肉", "酱卤", "熟食", "肉皮", "牛肚", "凤爪", "鸡爪", "鸭脖")),
    5: ("水产及其制品", ("鱼", "虾", "蟹", "贝", "海参", "鱿鱼", "鱼丸", "鱼干")),
    6: ("蛋及蛋制品", ("鸡蛋", "鸭蛋", "咸蛋", "皮蛋", "蛋制品")),
    7: ("乳及乳制品", ("牛奶", "羊奶", "奶粉", "酸奶", "奶酪", "乳粉", "乳制品")),
    8: ("蔬菜及其制品", ("蔬菜", "青菜", "白菜", "豆芽", "腌菜", "酸菜", "笋")),
    9: ("水果及其制品", ("水果", "苹果", "香蕉", "荔枝", "桂圆", "葡萄", "杨桃", "枇杷", "果干", "蜜饯")),
    10: ("豆制品", ("豆腐", "腐竹", "豆干", "豆皮", "素鸡", "豆制品")),
    11: ("糕点烘焙", ("糕点", "月饼", "面包", "蛋糕", "饼干", "桃酥", "麻花", "麻饼", "馍", "烧饼")),
    12: ("酒类", ("白酒", "黄酒", "啤酒", "葡萄酒", "米酒", "酒类")),
    13: ("饮料及冷冻饮品", ("饮料", "果汁", "茶饮料", "矿泉水", "纯净水", "冰淇淋", "雪糕")),
    14: ("茶叶", ("茶叶", "绿茶", "红茶", "普洱", "花茶")),
    15: ("调味品", ("酱油", "食醋", "醋", "味精", "食盐", "食用盐", "辣椒", "胡椒粉", "花椒", "调味品", "鸡精")),
    16: ("保健食品", ("保健食品", "膳食补充剂", "鱼油", "蜂胶", "钙片")),
    17: ("糖果蜜饯及炒货", ("糖果", "蜜饯", "果冻", "巧克力", "瓜子", "坚果", "花生", "槟榔")),
    18: ("特殊膳食用食品", ("婴幼儿配方", "辅食", "特殊医学用途", "运动营养")),
}

NEGATIVE = ("电池", "锅炉", "计量秤")


def r4(x: float) -> float:
    return round(x, 4)


def main() -> None:
    rows = [json.loads(line) for line in SILVER.read_text(encoding="utf-8").splitlines() if line.strip()]
    doc_ids = [r["doc_id"] for r in rows]

    # Filename convention on disk is doc_id with ':' replaced by '_'; every doc_id
    # in this corpus contains one ':'. Files with no matching doc_id are counted and
    # named, not silently ignored: the index covers the 1128 mapped texts only.
    def path_for(did: str) -> Path:
        return DOCS / f"{did.replace(':', '_')}.txt"

    on_disk = {p.name for p in DOCS.glob("*.txt")}
    mapped = {path_for(d).name for d in doc_ids}
    orphans = sorted(on_disk - mapped)
    assert len(mapped) == len(doc_ids), "doc_id collision after ':' -> '_' mapping"

    texts: dict[str, str] = {}
    listing = hashlib.sha256()
    total_bytes = 0
    for did in doc_ids:
        raw = path_for(did).read_bytes()
        total_bytes += len(raw)
        listing.update(f"{did}\t{hashlib.sha256(raw).hexdigest()}\n".encode())
        texts[did] = raw.decode("utf-8", errors="replace")

    cat_hits: dict[int, list[str]] = {}
    cat_terms: dict[int, dict[str, int]] = {}
    for cid, (_name, terms) in LEXICON.items():
        hits, tcount = [], {}
        for did in doc_ids:
            t = texts[did]
            matched = [term for term in sorted(set(terms), key=len, reverse=True) if term in t]
            if matched:
                hits.append(did)
                for term in matched:
                    tcount[term] = tcount.get(term, 0) + 1
        cat_hits[cid] = hits
        cat_terms[cid] = tcount

    any_hit = {did for hits in cat_hits.values() for did in hits}
    neg_counts = {term: sum(1 for did in doc_ids if term in texts[did]) for term in NEGATIVE}
    neg_only = [did for did in doc_ids
                if did not in any_hit and any(term in texts[did] for term in NEGATIVE)]

    n = len(doc_ids)
    out = {
        "at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "criterion_register": CRITERION,
        "role": "descriptive_keyword_presence_only",
        "matching_rule": "literal substring (`in`) on raw UTF-8 of data/clean/docs/<doc_id>.txt; "
                         "no tokenisation, no regex, no case/variant folding",
        "n_docs_total": n,
        "n_docs_any_commodity_term": len(any_hit),
        "n_docs_no_commodity_term": n - len(any_hit),
        "inputs": {
            "silver_sha256": hashlib.sha256(SILVER.read_bytes()).hexdigest(),
            "clean_docs_dir": str(DOCS),
            "n_clean_files": len(texts),
            "clean_bytes_total": total_bytes,
            "clean_docs_listing_sha256": listing.hexdigest(),
            "filename_convention": "data/clean/docs/<doc_id with ':' -> '_'>.txt",
            "n_files_on_disk": len(on_disk),
            "n_orphan_files_not_in_silver": len(orphans),
            "orphan_files": orphans,
        },
        "lexicon": {str(cid): {"name": name, "terms": list(dict.fromkeys(terms)),
                               "n_terms": len(set(terms))}
                    for cid, (name, terms) in LEXICON.items()},
        "negative_control": {
            "terms": list(NEGATIVE),
            "n_docs_per_term": neg_counts,
            "n_docs_with_negative_term_and_no_category_hit": len(neg_only),
            "doc_ids_negative_only": sorted(neg_only),
            "note": "non-food terms; used to detect a lexicon that fires on unrelated text",
        },
        "categories": {},
    }
    for cid, (name, terms) in LEXICON.items():
        hits = cat_hits[cid]
        out["categories"][str(cid)] = {
            "name": name,
            "n_docs": len(hits),
            "share_of_window": r4(len(hits) / n),
            "terms_with_hits": dict(sorted(cat_terms[cid].items(), key=lambda kv: -kv[1])),
            "terms_zero_hits": [t for t in dict.fromkeys(terms) if t not in cat_terms[cid]],
            "doc_ids": sorted(hits),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)

    # --- adjudication sample: deterministic, sha256(doc_id) order, NOT random ---
    sample = {
        "at_utc": out["at_utc"],
        "criterion_register": CRITERION,
        "role": "precision_sample_for_manual_adjudication",
        "selection_rule": f"per category, doc_ids sorted by sha256(doc_id) ascending, first min({SAMPLE_N}, N_k)",
        "window_chars": WINDOW,
        "items": [],
    }
    for cid, (name, terms) in LEXICON.items():
        hits = sorted(cat_hits[cid], key=lambda d: hashlib.sha256(d.encode()).hexdigest())
        for did in hits[:SAMPLE_N]:
            t = texts[did]
            # Only terms that actually occur, longest first, capped for file size.
            present = [term for term in sorted(set(terms), key=len, reverse=True) if term in t]
            wins = []
            for term in present[:MAX_TERMS_SHOWN]:
                pos = t.find(term)
                lo, hi = max(0, pos - WINDOW), min(len(t), pos + len(term) + WINDOW)
                wins.append({"term": term, "pos": pos,
                             "window": t[lo:hi].replace("\n", " ")})
            sample["items"].append({"doc_id": did, "category": cid, "category_name": name,
                                    "windows": wins, "verdict": None, "note": ""})
    tmp = SAMPLE_OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(SAMPLE_OUT)

    print("n_docs", n, "any_hit", len(any_hit), "no_hit", n - len(any_hit))
    for cid in sorted(LEXICON):
        c = out["categories"][str(cid)]
        print(f"{cid:>2} {c['name']:<12} {c['n_docs']:>4}  {c['share_of_window']:.4f}")
    print("negative", neg_counts, "neg_only", len(neg_only))
    print("sample_items", len(sample["items"]))
    print("sha_index", hashlib.sha256(OUT.read_bytes()).hexdigest())
    print("sha_sample", hashlib.sha256(SAMPLE_OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
