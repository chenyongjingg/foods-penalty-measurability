#!/usr/bin/env python
"""Split each zh penalty decision into a facts-only section.

Two variants per document:

  facts        -- fact narrative with every statute citation masked
                  (《X法》第N条 -> <条款>).  This is what a human coder sees:
                  realistic, because the real document reads this way.
  facts_strict -- identical, plus the decision block removed and the
                  violation-phrase lexicon masked.  Used to measure how much
                  of the label is carried by the narrative's own statutory
                  vocabulary.  If facts_strict is uninformative, that is a
                  result, not a bug.

Nothing is written back into data/silver or data/raw.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import hashlib
import datetime as dt
from pathlib import Path

ROOT = Path("/opt/foods")
SILVER = ROOT / "data/silver/silver.jsonl"
DB = ROOT / "state/foods.sqlite"
OUT_DIR = ROOT / "data/clean/facts"
OUT_JSON = ROOT / "data/analysis/facts_split.json"

_CN = "一二三四五六七八九十百零〇两\\d"
STATUTE_ARTICLE = re.compile(
    rf"《[^》]{{2,40}}》\s*第[{_CN}]+条(?:第[{_CN}]+款)?(?:第[{_CN}]+项)?(?:第[{_CN}]+目)?")
STATUTE_NAME = re.compile(r"《[^》]{2,40}》")
BARE_ARTICLE = re.compile(rf"第[{_CN}]+条(?:第[{_CN}]+款)?(?:第[{_CN}]+项)?")

# Violation vocabulary. Masked only in the strict variant.
PHRASES = [
    r"(?:伪造|变造|虚假|买卖|出具)[^。；，]{0,10}(?:检验报告|检测报告|检验结论|检测数据|检疫证明)",
    r"(?:篡改|伪造|删除)[^。；，]{0,10}(?:溯源码|追溯码|溯源信息|追溯信息)",
    r"(?:伪造|变造|冒用|买卖|虚假)[^。；，]{0,10}(?:认证证书|认证标志|认证材料)",
    r"(?:标注虚假|虚假标注|篡改[^。；，]{0,6}生产日期|虚假生产日期|冒用[^。；，]{0,8}(?:厂名|厂址|产地))",
    r"(?:未取得|无证|超出许可范围)[^。；，]{0,10}(?:许可|生产经营)",
]
PHRASE_RE = re.compile("|".join(f"(?:{p})" for p in PHRASES))

DECISION_RE = re.compile(
    r"(?:本局决定|我局决定|现决定|决定如下|决定对当事人|处罚如下|作出如下|给予以下)")
CHARGE_RE = re.compile(r"(?:违反了?|构成|属于)[^。]{0,80}?(?:行为|情形|规定)")
# Leak probe: does the surviving text still talk about the sanction?
PENALTY_WORDS = re.compile(r"罚款|没收违法所得|没收非法财物|责令停产|吊销许可|警告")


def _split_decision(text: str) -> tuple[str, bool]:
    """Cut the sanction block: from the sentence holding the last decision
    keyword to the end.  Falls back to no cut when no keyword is found."""
    m = None
    for m in DECISION_RE.finditer(text):
        pass
    if m is None:
        return text, False
    boundary = text.rfind("。", 0, m.start())
    return (text[: boundary + 1] if boundary > 0 else text[: m.start()]), True


def _mask(text: str) -> tuple[str, int]:
    n = 0
    text, k = STATUTE_ARTICLE.subn("<条款>", text)
    n += k
    text, k = STATUTE_NAME.subn("<法>", text)
    n += k
    text, k = BARE_ARTICLE.subn("<条款>", text)
    n += k
    return text, n


def _clean(t: str) -> str:
    t = re.sub(r"[ \t　]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "data/analysis").mkdir(parents=True, exist_ok=True)

    silver_sha = hashlib.sha256(SILVER.read_bytes()).hexdigest()
    recs = [json.loads(l) for l in SILVER.open(encoding="utf-8")]
    frame = [r for r in recs if r.get("lang") == "zh"]
    ids = [r["doc_id"] for r in frame]

    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    paths = {d: p for d, p in db.execute(
        "select doc_id, text_path from docs where lang='zh' and text_path is not null and text_path<>''")}

    per_doc, n_ok, n_missing, n_short = [], 0, 0, 0
    for r in frame:
        d = r["doc_id"]
        p = paths.get(d)
        if not p or not os.path.exists(p):
            n_missing += 1
            per_doc.append({"doc_id": d, "ok": False, "why": "no_text"})
            continue
        raw = Path(p).read_text(encoding="utf-8", errors="replace")
        body, cut = _split_decision(raw)
        facts, n_mask = _mask(_clean(body))
        strict, _ = _mask(_clean(CHARGE_RE.sub("<定性>", _split_decision(raw)[0])))
        strict = PHRASE_RE.sub("<违规表述>", strict)
        strict = _clean(strict)
        safe = d.replace(":", "_")
        (OUT_DIR / f"{safe}.txt").write_text(facts, encoding="utf-8")
        (OUT_DIR / f"{safe}.strict.txt").write_text(strict, encoding="utf-8")
        short = len(facts) < 200
        n_short += short
        n_ok += not short
        per_doc.append({
            "doc_id": d, "ok": True, "n_facts": len(facts), "n_strict": len(strict),
            "n_masked": n_mask, "decision_cut": cut, "short": bool(short),
            "penalty_leak": bool(PENALTY_WORDS.search(facts)),
        })

    out = {
        "at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "silver_sha256": silver_sha,
        "n_frame": len(frame),
        "n_ok": n_ok, "n_short": n_short, "n_missing_text": n_missing,
        "n_decision_cut": sum(1 for x in per_doc if x.get("decision_cut")),
        "n_penalty_leak": sum(1 for x in per_doc if x.get("penalty_leak")),
        "rule": "decision block cut at last 本局决定/处罚如下 anchor; statutes masked; strict additionally masks 定性句 and violation lexicon",
        "per_doc": per_doc,
    }
    tmp = OUT_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT_JSON)
    print(json.dumps({k: v for k, v in out.items() if k != "per_doc"}, ensure_ascii=False))
    print("sha", hashlib.sha256(OUT_JSON.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
