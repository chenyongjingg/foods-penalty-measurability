#!/usr/bin/env python
"""D-117: corpus-wide commodity-subject measurement via a validated LLM pass.

Three stages, all fixed before the first call:

  S1  validate the LLM question against the 270 hand-adjudicated D-115 items
  S2  gate: kappa >= 0.60 AND balanced accuracy >= 0.75, else not_validated
  S3  apply to all 1,128 documents
  S4  per category: A (keyword hits), B (LLM subject), |A n B|, recall

Resumable by construction: every completed prediction is appended to
data/analysis/e13_preds.jsonl and re-read on start, so a crash costs one request,
not the run. (E9 burned 2.3 h of base-arm generation by scoring only at the end
and then raising on a None label -- see D-116. This script does not repeat that.)

Input to the model is the full cleaned text, truncated at CHAR_CAP characters.
There is no fact-paragraph extractor in this pipeline (the rule layer reads the
full text through fact_categories()), so the registered fallback in D-117 applies
and `input_basis` records that fact.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import math
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path("/opt/foods")
SILVER = ROOT / "data/silver/silver.jsonl"
DOCS = ROOT / "data/clean/docs"
INDEX = ROOT / "data/analysis/e12_commodity_index.json"
HUMAN = ROOT / "data/analysis/e12_commodity_precision.json"
PREDS = ROOT / "data/analysis/e13_preds.jsonl"
OUT = ROOT / "data/analysis/e13_commodity_subject.json"

CRITERION = "D-117"
API = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "qwen2.5-7b-instruct"
CHAR_CAP = 12_000
WORKERS = 16
MAX_RETRY = 3

CATS = {
    1: "粮食及其制品", 2: "食用油脂", 3: "生鲜肉", 4: "肉制品", 5: "水产及其制品",
    6: "蛋及蛋制品", 7: "乳及乳制品", 8: "蔬菜及其制品", 9: "水果及其制品",
    10: "豆制品", 11: "糕点烘焙", 12: "酒类", 13: "饮料及冷冻饮品", 14: "茶叶",
    15: "调味品", 16: "保健食品", 17: "糖果蜜饯及炒货", 18: "特殊膳食用食品",
}

SYSTEM = "你是中国食品安全行政处罚文书的专业阅读者，判断严谨，只回答被要求的编号。"

USER_TMPL = """下面是一份中国食品安全行政处罚文书的正文。请判断**本案被查处的商品**（违法行为直接指向的那一个食品）属于下列哪一类。

{cats}

规则：
- 只看被生产、被销售或被查处的那一个商品，**不要**被配料表、菜单、经营范围、同案其他商品带偏。
- 如果该商品只是文书里被顺带提到（例如出现在配料或法条中），而本案查处的不是它，按"不确定"处理。
- 无法确定被查处食品是什么，或本案根本不对应食品商品，回答 0。

只输出一个整数编号（0 到 18），不要解释。

===== 文书正文 =====
{text}
"""


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def path_for(did: str) -> Path:
    return DOCS / f"{did.replace(':', '_')}.txt"


def build_prompt(text: str) -> str:
    cats = "\n".join(f"{k}. {v}" for k, v in CATS.items())
    return USER_TMPL.format(cats=cats, text=text)


def ask(text: str) -> tuple[int, str]:
    import requests

    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": build_prompt(text)}],
        "temperature": 0.0,
        "max_tokens": 16,
    }
    last = ""
    for attempt in range(MAX_RETRY):
        try:
            r = requests.post(API, json=body, timeout=300)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            m = re.search(r"\d+", raw)
            val = int(m.group(0)) if m else -1
            if 0 <= val <= 18:
                return val, raw
            last = f"unparsed:{raw[:60]}"
        except Exception as e:  # noqa: BLE001 - network/model errors are expected here
            last = f"error:{type(e).__name__}:{e}"[:160]
        time.sleep(1.5 * (attempt + 1))
    return -1, last


def kappa(pairs: list[tuple[int, int]]) -> float:
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def balanced_accuracy(pairs: list[tuple[int, int]]) -> tuple[float, float, float]:
    pos = [(a, b) for a, b in pairs if b == 1]
    neg = [(a, b) for a, b in pairs if b == 0]
    tpr = sum(1 for a, _ in pos if a == 1) / len(pos) if pos else float("nan")
    tnr = sum(1 for a, _ in neg if a == 0) / len(neg) if neg else float("nan")
    return (tpr + tnr) / 2, tpr, tnr


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 4), round((c + h) / d, 4))


def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    recs = [json.loads(l) for l in SILVER.open(encoding="utf-8")]
    silver_sha = sha(SILVER)
    if not silver_sha.startswith("a1deda2c"):
        raise SystemExit(f"REFUSED: silver sha {silver_sha[:8]} is not the frozen corpus")

    texts: dict[str, tuple[str, int]] = {}
    missing = []
    for r in recs:
        did = r["doc_id"]
        p = path_for(did)
        if not p.exists():
            missing.append(did)
            continue
        t = p.read_text(encoding="utf-8")
        texts[did] = (t[:CHAR_CAP], len(t))

    done: dict[str, dict] = {}
    if PREDS.exists():
        for line in PREDS.open(encoding="utf-8"):
            try:
                d = json.loads(line)
                done[d["doc_id"]] = d
            except json.JSONDecodeError:
                continue
    print(f"docs {len(texts)} missing {len(missing)} already_done {len(done)}", flush=True)

    todo = [d for d in texts if d not in done]
    if limit is not None:
        todo = todo[:limit]
    print(f"to_run {len(todo)}", flush=True)

    lock = threading.Lock()
    t0 = time.time()
    n_done = [0]

    def work(did: str) -> None:
        text, full_len = texts[did]
        cat, raw = ask(text)
        row = {"doc_id": did, "category": cat, "raw": raw,
               "chars_in": len(text), "chars_full": full_len,
               "truncated": full_len > CHAR_CAP, "at_utc": utc()}
        with lock:
            with PREDS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            done[did] = row
            n_done[0] += 1
            if n_done[0] % 50 == 0:
                el = time.time() - t0
                print(f"[s3] {n_done[0]}/{len(todo)} {el:.0f}s "
                      f"err={sum(1 for x in done.values() if x['category'] < 0)}", flush=True)

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))

    # ---------------- S1: validate against the 270 human items ----------------
    human = json.loads(HUMAN.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    pairs, detail = [], []
    for it in human["items"]:
        did, c, verdict = it["doc_id"], it["category"], it["verdict"]
        pred = done.get(did, {}).get("category", -1)
        if pred < 0:
            continue
        pairs.append((1 if pred == c else 0, 1 if verdict == "S" else 0))
        detail.append({"doc_id": did, "category": c, "verdict": verdict,
                       "llm_category": pred, "agree": (pred == c) == (verdict == "S")})

    k = kappa(pairs)
    ba, tpr, tnr = balanced_accuracy(pairs)
    n_pos = sum(1 for _, b in pairs if b == 1)
    gate_ok = (k >= 0.60) and (ba >= 0.75)

    # ---------------- S4: per-category recall ----------------
    per_cat = {}
    if gate_ok:
        for cid, name in CATS.items():
            A = set(index["categories"][str(cid)]["doc_ids"])
            B = {d for d, r in done.items() if r["category"] == cid}
            inter = A & B
            rec = len(inter) / len(B) if B else None
            per_cat[cid] = {
                "name": name,
                "A_keyword_hits": len(A),
                "B_llm_subject": len(B),
                "A_intersect_B": len(inter),
                "recall": round(rec, 4) if rec is not None else None,
                "recall_wilson": wilson(len(inter), len(B)) if B else None,
                "precision_subject_human": human["per_category"][str(cid)]["precision_subject"],
            }

    out = {
        "at_utc": utc(),
        "criterion_register": CRITERION,
        "role": "corpus_wide_commodity_subject_measurement",
        "inputs": {
            "silver_sha256": silver_sha,
            "index_sha256": sha(INDEX),
            "human_sha256": sha(HUMAN),
        },
        "model": {"name": MODEL, "temperature": 0.0, "max_tokens": 16,
                  "char_cap": CHAR_CAP},
        "input_basis": {
            "source": "full cleaned text",
            "fact_paragraph_available": False,
            "note": "no fact-paragraph extractor exists in this pipeline; D-117's registered fallback applies",
            "n_truncated": sum(1 for r in done.values() if r.get("truncated")),
        },
        "coverage": {
            "n_docs_corpus": len(recs),
            "n_texts_found": len(texts),
            "n_missing_text": len(missing),
            "missing_doc_ids": missing[:50],
            "n_predicted": sum(1 for r in done.values() if r["category"] >= 0),
            "n_unparseable": sum(1 for r in done.values() if r["category"] < 0),
            "category_histogram": {str(k2): sum(1 for r in done.values() if r["category"] == k2)
                                   for k2 in range(0, 19)},
        },
        "s1_validation": {
            "n_items": len(pairs),
            "n_positive_human_S": n_pos,
            "kappa": round(k, 4),
            "balanced_accuracy": round(ba, 4),
            "tpr": round(tpr, 4),
            "tnr": round(tnr, 4),
            "gate_kappa_min": 0.60,
            "gate_ba_min": 0.75,
            "gate_passed": bool(gate_ok),
            "items": detail,
        },
        "s2_verdict": "validated" if gate_ok else "not_validated",
        "s4_recall": per_cat if gate_ok else {},
        "preds_sha256": sha(PREDS),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("gate:", out["s2_verdict"], "kappa", round(k, 4), "BA", round(ba, 4),
          "tpr", round(tpr, 4), "tnr", round(tnr, 4), "n", len(pairs))
    if gate_ok:
        for cid, v in per_cat.items():
            print(f"{cid:>2} {v['name']:<10} A={v['A_keyword_hits']:>4} B={v['B_llm_subject']:>4} "
                  f"int={v['A_intersect_B']:>4} recall={v['recall']}")
    print("sha", sha(OUT))


if __name__ == "__main__":
    main()
