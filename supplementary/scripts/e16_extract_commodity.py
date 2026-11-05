#!/usr/bin/env python
"""D-124: extract the penalised commodity as a noun phrase, then map deterministically.

E13 (forced choice) and E15 (per-category binary) both ask the model to *classify*.
Both failed the gate. This asks it only to *name* the product; the 18-way mapping is
done afterwards by the E12 lexicon, in code, identically for every document.

This is the LAST automated attempt (D-124 fixes the cap): if it fails the gate, the
recall stays not_estimable and the manual zero-hit sample takes over.

    --stage val    270 gold pairs
    --stage full   1,128 documents (only after the gate passed)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/opt/foods/scripts")

from e13_commodity_subject import (  # noqa: E402 - identical system prompt is the point
    CATS, CHAR_CAP, HUMAN, INDEX, SILVER, SYSTEM, balanced_accuracy, kappa, path_for, sha, utc,
)

ROOT = Path("/opt/foods")
PREDS = ROOT / "data/analysis/e16_preds.jsonl"
OUT_VAL = ROOT / "data/analysis/e16_validation.json"
OUT_FULL = ROOT / "data/analysis/e16_extracted_subject.json"
API = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "qwen2.5-7b-instruct"
CRITERION = "D-124"
WORKERS = 24
MAX_RETRY = 3

USER_TMPL = """下面是一份中国食品安全行政处罚文书的正文，读完后回答文末的一个问题。

===== 文书正文 =====
{text}

===== 问题 =====
本案被查处的商品是哪一个食品？只写出**商品名称**，不超过 20 个字。
不要写厂家名、地址、违法事实或法条依据。若无法确定，或本案根本不对应食品商品，只输出：无
"""


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 4), round((c + h) / d, 4))


def clean(raw: str) -> str:
    line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    line = re.sub(r"^[#*\s]*(商品名称|答案|回答)[:：]\s*", "", line)
    line = line.strip("。．.，,、；;：: \t\"'“”「」")
    return line[:20]


def build_mapper(lexicon: dict):
    """Return phrase -> category id (0 = no lexicon term found)."""
    pairs = []
    for cid_s, v in lexicon.items():
        cid = int(cid_s)
        for t in v["terms"]:
            if t:
                pairs.append((cid, t))

    def mapper(phrase: str) -> tuple[int, str]:
        if not phrase or phrase in {"无", "无法确定", "无。", "不确定"}:
            return 0, ""
        hits = []
        for cid, t in pairs:
            pos = phrase.find(t)
            if pos >= 0:
                hits.append((-len(t), pos, cid, t))
        if not hits:
            return 0, ""
        hits.sort()
        _, _, cid, t = hits[0]
        return cid, t

    return mapper


def ask(text: str) -> tuple[str, str]:
    import requests

    body = {"model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER_TMPL.format(text=text)}],
            "temperature": 0.0, "max_tokens": 32}
    last = ""
    for attempt in range(MAX_RETRY):
        try:
            r = requests.post(API, json=body, timeout=300)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            if raw:
                return clean(raw), raw
            last = "empty"
        except Exception as e:  # noqa: BLE001
            last = f"error:{type(e).__name__}:{e}"[:150]
        time.sleep(1.5 * (attempt + 1))
    return "", last


def load_done() -> dict[str, dict]:
    done = {}
    if PREDS.exists():
        for line in PREDS.open(encoding="utf-8"):
            try:
                d = json.loads(line)
                done[d["doc_id"]] = d
            except json.JSONDecodeError:
                pass
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["val", "full"], required=True)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    recs = [json.loads(l) for l in SILVER.open(encoding="utf-8")]
    silver_sha = sha(SILVER)
    if not silver_sha.startswith("a1deda2c"):
        raise SystemExit(f"REFUSED: silver sha {silver_sha[:8]}")

    texts = {}
    for r in recs:
        p = path_for(r["doc_id"])
        if p.exists():
            t = p.read_text(encoding="utf-8")
            texts[r["doc_id"]] = (t[:CHAR_CAP], len(t))

    human = json.loads(HUMAN.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    mapper = build_mapper(index["lexicon"])

    done = load_done()
    todo = [d for d in texts if d not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"stage={a.stage} docs={len(texts)} done={len(done)} todo={len(todo)}", flush=True)

    t0 = time.time()
    n = [0]
    lock = threading.Lock()

    def work(did: str) -> None:
        text, full = texts[did]
        phrase, raw = ask(text)
        mapped, term = mapper(phrase)
        row = {"doc_id": did, "phrase": phrase, "mapped_category": mapped, "matched_term": term,
               "raw": raw, "truncated": full > CHAR_CAP, "at_utc": utc()}
        with lock:
            with PREDS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            done[did] = row
            n[0] += 1
            if n[0] % 200 == 0:
                print(f"[{a.stage}] {n[0]}/{len(todo)} {time.time()-t0:.0f}s", flush=True)

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))

    pairs, detail = [], []
    for it in human["items"]:
        r = done.get(it["doc_id"])
        if r is None:
            continue
        pred = 1 if r["mapped_category"] == it["category"] else 0
        truth = 1 if it["verdict"] == "S" else 0
        pairs.append((pred, truth))
        detail.append({"doc_id": it["doc_id"], "category": it["category"],
                       "verdict": it["verdict"], "phrase": r["phrase"],
                       "mapped": r["mapped_category"], "pred": pred, "agree": pred == truth})

    kap = kappa(pairs)
    ba, tpr, tnr = balanced_accuracy(pairs)
    gate = (kap >= 0.60) and (ba >= 0.75)

    if a.stage == "val":
        out = {
            "at_utc": utc(), "criterion_register": CRITERION,
            "role": "extraction_then_deterministic_lexicon_mapping",
            "model": MODEL, "format": "free-text commodity name (<=20 chars) + E12 lexicon map",
            "inputs": {"silver_sha256": silver_sha, "human_sha256": sha(HUMAN),
                       "index_sha256": sha(INDEX)},
            "n_items": len(pairs),
            "n_docs_extracted": len(done),
            "n_empty_extraction": sum(1 for r in done.values() if not r["phrase"]),
            "n_unmapped": sum(1 for r in done.values() if r["mapped_category"] == 0),
            "kappa": round(kap, 4), "balanced_accuracy": round(ba, 4),
            "tpr": round(tpr, 4), "tnr": round(tnr, 4),
            "gate_kappa_min": 0.60, "gate_ba_min": 0.75,
            "gate_passed": bool(gate),
            "s2_verdict": "validated" if gate else "not_validated",
            "comparison": {
                "e13_forced_choice": {"kappa": 0.3241, "balanced_accuracy": 0.6519,
                                      "tpr": 0.4423, "tnr": 0.8614},
                "e15_per_category_binary": {"kappa": 0.4885, "balanced_accuracy": 0.7390,
                                            "tpr": 0.6346, "tnr": 0.8434},
            },
            "items": detail,
            "preds_sha256": sha(PREDS),
        }
        OUT_VAL.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"VAL verdict={out['s2_verdict']} kappa={kap:.4f} BA={ba:.4f} "
              f"tpr={tpr:.4f} tnr={tnr:.4f} n={len(pairs)} "
              f"empty={out['n_empty_extraction']} unmapped={out['n_unmapped']}")
        print("sha", sha(OUT_VAL))
        return

    per_cat = {}
    for cid, name in CATS.items():
        A = set(index["categories"][str(cid)]["doc_ids"])
        B = {d for d, r in done.items() if r["mapped_category"] == cid}
        inter = A & B
        per_cat[cid] = {
            "name": name, "A_keyword_hits": len(A), "B_llm_subject": len(B),
            "A_intersect_B": len(inter),
            "recall": round(len(inter) / len(B), 4) if B else None,
            "recall_wilson": wilson(len(inter), len(B)) if B else None,
            "precision_subject_human": human["per_category"][str(cid)]["precision_subject"],
        }
    out = {
        "at_utc": utc(), "criterion_register": CRITERION,
        "role": "corpus_wide_extracted_commodity",
        "model": MODEL, "format": "free-text commodity name + deterministic lexicon map",
        "prefix_caching": True,
        "inputs": {"silver_sha256": silver_sha, "index_sha256": sha(INDEX),
                   "human_sha256": sha(HUMAN)},
        "s1_gate": {"kappa": round(kap, 4), "balanced_accuracy": round(ba, 4),
                    "tpr": round(tpr, 4), "tnr": round(tnr, 4), "gate_passed": bool(gate)},
        "coverage": {"n_docs": len(texts), "n_extracted": len(done),
                     "n_empty": sum(1 for r in done.values() if not r["phrase"]),
                     "n_unmapped": sum(1 for r in done.values() if r["mapped_category"] == 0),
                     "mapped_histogram": {str(c): sum(1 for r in done.values()
                                                      if r["mapped_category"] == c)
                                          for c in range(0, 19)}},
        "per_category": per_cat,
        "preds_sha256": sha(PREDS),
    }
    OUT_FULL.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("FULL written; gate:", out["s1_gate"])
    for cid, v in per_cat.items():
        print(f"{cid:>2} {v['name']:<10} A={v['A_keyword_hits']:>4} B={v['B_llm_subject']:>4} "
              f"int={v['A_intersect_B']:>4} recall={v['recall']}")
    print("sha", sha(OUT_FULL))


if __name__ == "__main__":
    main()
