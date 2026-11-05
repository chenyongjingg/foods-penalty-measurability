"""E7 -- behaviour-hazard typology of the main corpus (Plan v7, E7 = E2's
case-chain downgrade rung, now scheduled).

Input: the high tier of the Chinese frame (124 documents at the frozen
corpus). Output: a closed-set typology of what the decision says was done, at
what hazard level, by which role.

Construction, fixed before looking at the result:

* role pattern -- deterministic, from the already-extracted entity set
  (END_USER / SERVICE_PROVIDER). No new model call.
* method set -- deterministic, keyword rules over the document's fact segment
  mapped to a fixed method codebook. No new model call.
* hazard class -- the one thing the current extraction does not encode, so it
  is asked of both labelling channels independently (two differently worded
  prompts, different temperatures), and a disagreement is resolved by the
  third channel (5-sample majority vote, the same adjudication form the silver
  protocol uses). Agreement is the gate: >= 0.80 target, >= 0.70 floor; below
  the floor the typology is reported as provisional and every entry goes on
  the "needs human audit" list.

The typical quote shipped with the table is anonymised deterministically: the
party string from the anchor fields is replaced, and ID / phone patterns are
masked. Nothing else in the sentence is edited.

Usage:
    ./venv/bin/python scripts/e7_typology.py [--no-quotes]
Exit 0 = product written; exit 1 = precondition failed.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from foods_pipeline.common import cfg, path_of, write_json, utc_iso  # noqa: E402
from foods_pipeline.label.llm import LLMClient, parse_json  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

DATA = ROOT / "data"
SILVER = DATA / "silver" / "silver.jsonl"
OUT = DATA / "analysis" / "e7_typology.json"
REPORT = DATA / "reports" / "e7_typology.md"

HAZARD_CLASSES = {
    "FOOD_SAFETY": "文书认定的行为直接危及食品安全（病原、非法添加、超范围超限量使用添加剂、过期原料、掺假掺杂）",
    "CONSUMER_DECEPTION": "文书认定的行为主要是欺骗性信息（虚假标签、伪造检验报告、虚假认证、溯源造假），未直接危及食品安全",
    "MARKET_ORDER": "文书认定的行为主要扰乱市场秩序（无证经营、商标侵权、虚假广告），与食品安全或信息真伪均不直接相关",
    "MIXED": "同时包含上述两类以上的实质危害",
    "UNCLEAR": "文书内容不足以判断",
}

METHOD_RULES = [
    ("FORGED_REPORT", r"检验报告|检测报告|检验结论|检测数据|检疫证明"),
    ("TAMPERED_TRACEABILITY", r"溯源|追溯码|追溯信息|溯源码"),
    ("FAKE_CERTIFICATION", r"认证证书|认证标志|认证材料"),
    ("FALSE_LABELING", r"标签|标注|生产日期|保质期|厂名|厂址|产地"),
    ("UNLICENSED", r"许可|无证|超范围"),
    ("ADULTERATION", r"掺假|掺杂|以次充好|以假充真|假冒"),
    ("EXPIRED_MATERIAL", r"过期|超过保质期|变质"),
    ("ILLEGAL_ADDITIVE", r"添加剂|非食用物质"),
    ("TRADEMARK", r"商标"),
    ("FALSE_ADVERTISING", r"广告|宣传"),
]

ORG = re.compile(r"[一-龥A-Za-z0-9（）()·]{2,24}?"
                 r"(?:有限责任公司|有限公司|食品厂|加工厂|商行|经营部|门市部|小吃店|"
                 r"餐饮店|超市|商店|店|厂)")
REP = re.compile(r"(法定代表人|负责人|经营者)[：:为]?\s*[一-龥]{2,4}")
# Order matters: the licence prefix SC + 14 digits contains an 11-digit run
# that the phone pattern would otherwise eat, leaving "SC10〔电话已隐去〕45".
PII = [
    (re.compile(r"\d{6}(?:19|20)\d{2}[01]\d[0-3]\d{4}[0-9Xx]"), "〔身份证号已隐去〕"),
    (re.compile(r"SC\d{10,14}"), "〔许可证号已隐去〕"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "〔电话已隐去〕"),
    (re.compile(r"(?<![0-9A-Z])[0-9A-Z]{18}(?![0-9A-Z])"), "〔统一社会信用代码已隐去〕"),
]
SENT = re.compile(r"[^。；\n]{20,200}[。；]")
KEY = re.compile(r"伪造|篡改|虚假|标注|无证|过期|添加|掺|假冒|商标|检验|认证|溯源|不合格")

ALPHA = """你是食品安全行政处罚文书的编码员。只依据文书内容，判断该处罚所认定的违法行为的主要危害类别，从下面五个代码中选一个：

{classes}

只输出 JSON：{{"hazard": "<CODE>"}}

文书：
<<<DOC>>>
"""

BETA = """任务：阅读一份中国食品安全行政处罚决定书，判断其违法行为的**实质危害**落在哪一类。

先在心里回答两个问题：(1) 该行为是否直接危及食品安全（病原、添加剂、过期、掺假）？(2) 该行为是否主要是欺骗性信息（虚假标注、伪造报告、虚假认证、溯源造假）？据此在下面清单中选且只选一个代码。

{classes}

输出 JSON：{{"hazard": "<CODE>", "reason": "不超过20字"}}

决定书：
<<<DOC>>>
"""


def _sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def _class_block() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in HAZARD_CLASSES.items())


FACT_START = re.compile(r"(?:经查|经调查|查明|违法事实|现查明)")
FACT_END = re.compile(r"(?:上述事实|以上事实|上述行为|有下列证据|证据证明|本局认为|我局认为)")


def fact_segment(text: str, limit: int = 1500) -> str:
    """Same rule as E6 (D-73): the case-specific part of the decision.

    Method codes are read from the facts, not from the extracted TACTIC spans:
    measured on the frozen corpus, 43 of 124 main-corpus documents carried no
    TACTIC entity at all, so a method table built from the extraction would
    have described the extractor's misses rather than the corpus. The fact
    segment is present in every decision and is the text the conduct is
    described in.
    """
    m = FACT_START.search(text)
    if not m:
        return text[:limit]
    s = m.start()
    e = FACT_END.search(text, s + 10)
    return text[s:(e.start() if e else s + limit)]


def method_codes(fact: str) -> list[str]:
    codes = []
    for m, pat in METHOD_RULES:
        if re.search(pat, fact):
            codes.append(m)
    return sorted(set(codes))


def role_pattern(types: collections.Counter) -> str:
    has_eu = types.get("END_USER", 0) > 0
    has_sp = types.get("SERVICE_PROVIDER", 0) > 0
    if has_eu and has_sp:
        return "BOTH"
    if has_eu:
        return "END_USER_ONLY"
    if has_sp:
        return "PROVIDER_ONLY"
    return "NEITHER"


def anonymise(text: str, party: str | None) -> str:
    """Mask parties, firms, legal representatives and identifiers.

    The source documents are public penalty decisions, so this is not a
    confidentiality control; it is the anonymisation the plan asks for, and it
    is deliberately over-inclusive: an entity name that happens to end in 店/厂
    is masked too.
    """
    t = text or ""
    if party:
        for variant in {party, party.replace("*", ""), party.replace("＊", "")}:
            if len(variant) >= 2:
                t = t.replace(variant, "某经营者")
    t = REP.sub(lambda m: m.group(1) + "〔已隐去〕", t)
    t = ORG.sub("某经营者", t)
    for pat, repl in PII:
        t = pat.sub(repl, t)
    return t


def _quote(text: str, party: str | None) -> str | None:
    """One sentence from the facts that names the conduct, anonymised."""
    seg = fact_segment(text, 2000)
    candidates = [m.group(0).strip() for m in SENT.finditer(seg)]
    # Prefer a sentence that names the conduct and reads as prose: a fragment
    # of an ID list can contain a keyword and still be useless as a quote.
    for s in candidates:
        if KEY.search(s) and len(s) >= 30 and re.search(r"[一-龥]{6,}", s) \
                and not re.match(r"^[：:，,。]", s):
            return "…" + anonymise(s, party)
    for s in candidates:
        if KEY.search(s) and len(s) >= 20:
            return "…" + anonymise(s, party)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-quotes", action="store_true", help="skip the quote panel")
    args = ap.parse_args()

    recs = [json.loads(line) for line in open(SILVER, encoding="utf-8") if line.strip()]
    main_recs = [r for r in recs if r.get("tier") == "high" and r.get("lang") == "zh"]
    if not main_recs:
        print("main corpus (high, zh) is empty", file=sys.stderr)
        return 1

    m = Manifest()
    texts, metas = {}, {}
    with m.conn() as c:
        for row in c.execute("SELECT doc_id, text_path, meta FROM docs"):
            metas[row["doc_id"]] = json.loads(row["meta"] or "{}")
            if row["text_path"]:
                try:
                    texts[row["doc_id"]] = Path(row["text_path"]).read_text(encoding="utf-8")
                except OSError:
                    pass
    missing = [r["doc_id"] for r in main_recs if r["doc_id"] not in texts]
    if missing:
        print(f"{len(missing)} main-corpus docs have no text, e.g. {missing[:3]}", file=sys.stderr)
        return 1

    llm = LLMClient()
    if not llm.health():
        print("LLM endpoint unavailable", file=sys.stderr)
        return 1
    a_cfg, b_cfg = cfg("llm.channel_a"), cfg("llm.channel_b")
    adj = cfg("llm.adjudicator")
    cap = int(cfg("label.doc_text_chars", 20000))
    block = _class_block()

    def ask(doc_id: str) -> dict:
        text = texts[doc_id][:cap]
        pa = ALPHA.format(classes=block).replace("<<<DOC>>>", text)
        pb = BETA.format(classes=block).replace("<<<DOC>>>", text)
        out = {"doc_id": doc_id}
        try:
            ja = parse_json(llm.chat(a_cfg["model"], pa, temperature=0.0, max_tokens=120)[0]) or {}
            jb = parse_json(llm.chat(b_cfg["model"], pb, temperature=0.3, max_tokens=160)[0]) or {}
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)[:200]
            return out

        def norm(x):
            v = (x or "").strip().upper()
            return v if v in HAZARD_CLASSES else None

        out["a"], out["b"] = norm(ja.get("hazard")), norm(jb.get("hazard"))
        return out

    from concurrent.futures import ThreadPoolExecutor
    workers = max(1, int(cfg("label.workers", 4)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        asked = list(pool.map(ask, [r["doc_id"] for r in main_recs]))
    by_id = {a["doc_id"]: a for a in asked}

    # third channel for disagreements
    disputed = [d for d in asked if "error" not in d and d["a"] != d["b"]]
    votes: dict[str, str | None] = {}
    if disputed:
        n_samples = int(adj.get("samples", 5))
        temp = float(adj.get("temperature", 0.7))

        def adjudicate(doc_id: str):
            text = texts[doc_id][:cap]
            p = BETA.format(classes=block).replace("<<<DOC>>>", text)
            try:
                outs = llm.chat(adj["model"], p, temperature=temp, max_tokens=160,
                                n=n_samples)
            except Exception:  # noqa: BLE001
                return doc_id, None
            cs = []
            for o in outs:
                j = parse_json(o) or {}
                v = (j.get("hazard") or "").strip().upper()
                if v in HAZARD_CLASSES:
                    cs.append(v)
            if not cs:
                return doc_id, None
            return doc_id, collections.Counter(cs).most_common(1)[0][0]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for did, v in pool.map(adjudicate, [d["doc_id"] for d in disputed]):
                votes[did] = v

    rows, n_agree, n_err = [], 0, 0
    for r in main_recs:
        did = r["doc_id"]
        a = by_id[did]
        if "error" in a:
            n_err += 1
            continue
        agreed = a["a"] == a["b"] and a["a"] is not None
        hazard = a["a"] if agreed else votes.get(did) or a["a"] or a["b"] or "UNCLEAR"
        if agreed:
            n_agree += 1
        types = collections.Counter(e["type"] for e in r["entities"])
        methods = method_codes(fact_segment(texts[did]))
        rows.append({"doc_id": did, "hazard_a": a["a"], "hazard_b": a["b"],
                     "hazard": hazard, "adjudicated": not agreed,
                     "methods": methods, "role": role_pattern(types),
                     "category": r.get("violation_category"),
                     "anchor_pass": r.get("anchor_pass")})

    n_scored = len(rows)
    if n_scored == 0:
        print("no document could be coded", file=sys.stderr)
        return 1
    agreement = round(n_agree / n_scored, 4)
    tgt, flo = 0.80, 0.70          # Plan v7 E7 thresholds, fixed before the run
    status = "target_met" if agreement >= tgt else "floor_met" if agreement >= flo else "below_floor"

    entries: dict[str, list[dict]] = collections.defaultdict(list)
    for x in rows:
        key = f"{x['hazard']}|{'+'.join(x['methods']) or '-'}|{x['role']}"
        entries[key].append(x)
    table = []
    for key, docs in sorted(entries.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        hz, meth, role = key.split("|")
        agree_rate = round(sum(1 for d in docs if not d["adjudicated"]) / len(docs), 4)
        table.append({"entry": key, "hazard": hz, "methods": meth.split("+") if meth != "-" else [],
                      "role": role, "n_docs": len(docs),
                      "dual_channel_agreement": agree_rate,
                      "status": "entry" if len(docs) >= 3 else "singleton"})
    audit = [t["entry"] for t in table if t["n_docs"] >= 3 and t["dual_channel_agreement"] < flo]

    quotes = []
    if not args.no_quotes:
        by_doc = {r["doc_id"]: r for r in main_recs}
        for t in [t for t in table if t["status"] == "entry"]:
            if len(quotes) >= 5:
                break
            for d in entries[t["entry"]]:
                party = ((by_doc[d["doc_id"]].get("anchor") or {}).get("fields") or {}).get("party")
                q = _quote(texts[d["doc_id"]], party)
                if q:
                    quotes.append({"entry": t["entry"], "doc_id": d["doc_id"], "quote": q})
                    break

    out = {
        "at_utc": utc_iso(),
        "corpus": {"tier": "high", "lang": "zh", "n": len(main_recs),
                   "n_scored": n_scored, "n_llm_error": n_err},
        "codebook": {"hazard": HAZARD_CLASSES, "methods": [m for m, _ in METHOD_RULES],
                     "roles": ["END_USER_ONLY", "PROVIDER_ONLY", "BOTH", "NEITHER"],
                     "method_source": ("deterministic keyword rules over the document's "
                                       "fact segment"),
                     "entry_rule": "support >= 3 documents; smaller groups are singletons"},
        "protocol": {"channels": ["alpha", "beta"], "adjudicator_samples": int(adj.get("samples", 5)),
                     "prompt_sha": {"alpha": _sha_text(ALPHA), "beta": _sha_text(BETA)},
                     "model": a_cfg["model"], "text_cap": cap},
        "dual_channel_agreement": agreement,
        "n_adjudicated": len(disputed),
        "thresholds": {"target": tgt, "floor": flo}, "status": status,
        "entries": table,
        "needs_human_audit": audit,
        "quotes": quotes,
        "hazard_distribution": dict(sorted(collections.Counter(x["hazard"] for x in rows).items())),
        "role_distribution": dict(sorted(collections.Counter(x["role"] for x in rows).items())),
        "method_distribution": dict(sorted(collections.Counter(
            m for x in rows for m in x["methods"]).items())),
    }
    write_json(OUT, out)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(_markdown(out), encoding="utf-8")
    print(json.dumps({"e7": "ok", "n": len(main_recs), "agreement": agreement,
                      "status": status, "entries": len([t for t in table if t["status"] == "entry"]),
                      "out": str(OUT)}, ensure_ascii=False))
    return 0


def _markdown(o: dict) -> str:
    L = ["# E7 行为—危害类型学（Results 2）", "",
         f"- 生成时刻：{o['at_utc']}",
         f"- 语料：high 层中文 {o['corpus']['n']} 篇（已编码 {o['corpus']['n_scored']}）",
         f"- 双通道一致率：{o['dual_channel_agreement']}（阈值 {o['thresholds']['target']}/"
         f"{o['thresholds']['floor']}）→ **{o['status']}**",
         f"- 第三通道裁决：{o['n_adjudicated']} 篇", "",
         "## 类型学条目", "", "| 条目 | 篇数 | 一致率 | 状态 |", "|---|---:|---:|---|"]
    for t in o["entries"]:
        L.append(f"| {t['entry']} | {t['n_docs']} | {t['dual_channel_agreement']} | {t['status']} |")
    if o["needs_human_audit"]:
        L += ["", "## 待人工审计清单", ""] + [f"- {e}" for e in o["needs_human_audit"]]
    if o["quotes"]:
        L += ["", "## 典型引文（已匿名化）", ""]
        for q in o["quotes"]:
            L.append(f"- `{q['entry']}` — {q['quote']}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
