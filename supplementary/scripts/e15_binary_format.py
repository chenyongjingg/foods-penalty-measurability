#!/usr/bin/env python
"""D-121: does the E13 failure depend on the forced-choice format?

Same documents, same +-context, same 270 gold items, same gate. The ONE change is
the question: instead of "pick one of 18", ask per category "is the penalised
product of this class? 1/0".

    --stage val    the 270 gold pairs only (fast gate check)
    --stage full   1,128 documents x 18 categories (only if the gate passed)

Resumable: every answered pair is appended and re-read on start.

Serving note: the 18 questions for one document share a byte-identical prefix, so
vLLM is started with --enable-prefix-caching. That is a serving optimisation, not
a change to the prompt, the model or the decoder (greedy, temperature 0), and it
cannot change an output.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/opt/foods/scripts")

from e13_commodity_subject import (  # noqa: E402
    CATS, CHAR_CAP, HUMAN, INDEX, SILVER, SYSTEM, balanced_accuracy, kappa, path_for, sha, utc,
)

ROOT = Path("/opt/foods")
PREDS = ROOT / "data/analysis/e15_preds.jsonl"
OUT_VAL = ROOT / "data/analysis/e15_validation.json"
OUT_FULL = ROOT / "data/analysis/e15_binary_subject.json"
API = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "qwen2.5-7b-instruct"
CRITERION = "D-121"
WORKERS = 32
MAX_RETRY = 3

# D-122: the document comes FIRST and the question LAST, so the 18 questions about
# one document share the whole text as a common prefix (prefix caching). Without
# this the full pass costs ~3.4 h of prefill.
USER_TMPL = """下面是一份中国食品安全行政处罚文书的正文，读完后回答文末的一个问题。

规则：
- 只看被生产、被销售或被查处的那一个商品。配料表、菜单、经营范围、同案其他商品里出现的，一律**不算**。
- 该商品只是被顺带提到（例如出现在配料或法条里）时，答 0。

===== 文书正文 =====
{text}

===== 问题 =====
**本案被查处的商品**（违法行为直接指向的那一个食品）是不是「{cat}」这一类？
只输出一个字符：是 = 1，否 = 0。不要解释。
"""


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 4), round((c + h) / d, 4))


def ask(cat: str, text: str) -> tuple[int, str]:
    import requests

    body = {"model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER_TMPL.format(cat=cat, text=text)}],
            "temperature": 0.0, "max_tokens": 16}  # D-121 fixes max_tokens=16
    last = ""
    for attempt in range(MAX_RETRY):
        try:
            r = requests.post(API, json=body, timeout=300)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            # strict: a 0/1 that is not part of a longer number, so a stray category
            # number ("13") becomes unparseable instead of being silently read as 1.
            m = re.search(r"(?<![0-9])([01])(?![0-9])", raw)
            if m:
                return int(m.group(1)), raw
            if "是" in raw:
                return 1, raw
            if "否" in raw or "不" in raw:
                return 0, raw
            last = f"unparsed:{raw[:40]}"
        except Exception as e:  # noqa: BLE001
            last = f"error:{type(e).__name__}:{e}"[:150]
        time.sleep(1.5 * (attempt + 1))
    return -1, last


def load_done() -> dict[str, dict]:
    done = {}
    if PREDS.exists():
        for line in PREDS.open(encoding="utf-8"):
            try:
                d = json.loads(line)
                done[f"{d['doc_id']}|{d['category']}"] = d
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
    done = load_done()

    if a.stage == "val":
        jobs = [(it["doc_id"], it["category"]) for it in human["items"]
                if it["doc_id"] in texts]
    else:
        jobs = [(d, c) for d in texts for c in CATS]
    if a.limit:
        jobs = jobs[:a.limit]
    jobs = [j for j in jobs if f"{j[0]}|{j[1]}" not in done]
    print(f"stage={a.stage} jobs={len(jobs)} already={len(done)}", flush=True)

    t0 = time.time()
    n = [0]
    lock = threading.Lock()

    def work(job: tuple[str, int]) -> None:
        did, cid = job
        text, full = texts[did]
        lab, raw = ask(CATS[cid], text)
        row = {"doc_id": did, "category": cid, "label": lab, "raw": raw,
               "truncated": full > CHAR_CAP, "at_utc": utc()}
        key = f"{did}|{cid}"
        with lock:
            with PREDS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            done[key] = row
            n[0] += 1
            if n[0] % 200 == 0:
                print(f"[{a.stage}] {n[0]}/{len(jobs)} {time.time()-t0:.0f}s "
                      f"err={sum(1 for v in list(done.values()) if v['label'] < 0)}", flush=True)

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, jobs))

    # ---------------- gate on the 270 gold pairs ----------------
    pairs, detail = [], []
    for it in human["items"]:
        k = f"{it['doc_id']}|{it['category']}"
        lab = done.get(k, {}).get("label", -1)
        if lab < 0:
            continue
        pred = 1 if lab == 1 else 0
        truth = 1 if it["verdict"] == "S" else 0
        pairs.append((pred, truth))
        detail.append({"doc_id": it["doc_id"], "category": it["category"],
                       "verdict": it["verdict"], "pred": pred, "agree": pred == truth})

    kap = kappa(pairs)
    ba, tpr, tnr = balanced_accuracy(pairs)
    gate = (kap >= 0.60) and (ba >= 0.75)

    if a.stage == "val":
        out = {
            "at_utc": utc(), "criterion_register": CRITERION,
            "role": "format_sensitivity_binary_vs_forced_choice",
            "model": MODEL, "format": "per-category binary 1/0",
            "inputs": {"silver_sha256": silver_sha, "human_sha256": sha(HUMAN)},
            "n_items": len(pairs),
            "kappa": round(kap, 4), "balanced_accuracy": round(ba, 4),
            "tpr": round(tpr, 4), "tnr": round(tnr, 4),
            "gate_kappa_min": 0.60, "gate_ba_min": 0.75,
            "gate_passed": bool(gate),
            "s2_verdict": "validated" if gate else "not_validated",
            "comparison": {"e13_forced_choice": {"kappa": 0.3241, "balanced_accuracy": 0.6519,
                                                 "tpr": 0.4423, "tnr": 0.8614}},
            "items": detail,
            "preds_sha256": sha(PREDS),
        }
        OUT_VAL.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"VAL verdict={out['s2_verdict']} kappa={kap:.4f} BA={ba:.4f} "
              f"tpr={tpr:.4f} tnr={tnr:.4f} n={len(pairs)}")
        print("sha", sha(OUT_VAL))
        return

    # ---------------- full corpus (only meaningful if the gate passed) ----------------
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    per_cat = {}
    for cid, name in CATS.items():
        A = set(index["categories"][str(cid)]["doc_ids"])
        B = {k.split("|")[0] for k, v in done.items()
             if v["category"] == cid and v["label"] == 1}
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
        "role": "corpus_wide_commodity_subject_binary",
        "model": MODEL, "format": "per-category binary 1/0",
        "prefix_caching": True,
        "inputs": {"silver_sha256": silver_sha, "index_sha256": sha(INDEX),
                   "human_sha256": sha(HUMAN)},
        "s1_gate": {"kappa": round(kap, 4), "balanced_accuracy": round(ba, 4),
                    "tpr": round(tpr, 4), "tnr": round(tnr, 4),
                    "gate_passed": bool(gate)},
        "coverage": {"n_docs": len(texts), "n_pairs_expected": len(texts) * len(CATS),
                     "n_pairs_done": len(done),
                     "n_unparseable": sum(1 for v in done.values() if v["label"] < 0)},
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
