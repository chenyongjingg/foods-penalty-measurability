"""E6 -- deterministic descriptive suite (Plan v7, part 2, E6).

Results 1 of the Foods submission: what violation types, over what time span,
on which food categories, in which jurisdictions, with what penalty severity.

Everything here is a rule engine over the document text plus the registry
fields -- no LLM decides a reported number. The one model call in this file is
the **negative-control** check required by the plan (50 random documents, both
labelling channels, rule-vs-model agreement), and its outcome only decides
whether a dimension is reported at fine or coarse granularity.

Three tables, three different statutes of the number:

1. `category_distribution` -- deterministic, from `config/statute_map_v2.yaml`
   (v1 mappings copied verbatim, coverage extended, new categories marked
   `descriptive_only`). This is Results 1.
2. `llm_cross_tab` -- the same corpus scored by the frozen silver category.
   Descriptive only; it is *not* the deterministic result and the paper must
   not swap them (D-77: the deterministic result wins on conflict).
3. `negative_control` -- rule vs dual-channel model on a seeded 50-document
   sample. Gate: >= 0.85 target, >= 0.75 floor, below floor the suite is
   reported as `coarse`.

Why the anchor table (v1) is not edited: its output is E1's anchor F1, which is
frozen (D-58/D-71). Extending it would refresh a frozen statistic.

Usage:
    ./venv/bin/python scripts/e6_descriptive.py [--control-n 50] [--no-control]
Exit 0 = products written; exit 1 = a precondition failed (missing text,
LLM unavailable when a control was requested, ...).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from foods_pipeline.common import cfg, load_yaml, path_of, write_json, utc_iso  # noqa: E402
from foods_pipeline.label import anchors  # noqa: E402
from foods_pipeline.label.llm import LLMClient, parse_json  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

DATA = ROOT / "data"
SILVER = DATA / "silver" / "silver.jsonl"
OUT = DATA / "analysis" / "e6_descriptive.json"
REPORT = DATA / "reports" / "e6_tables.md"

PROVINCES = ["北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
             "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海",
             "内蒙古", "广西", "西藏", "宁夏", "新疆"]

# --- negative control ------------------------------------------------------
# Two independently worded prompts over one closed category set. The set is the
# full v2 taxonomy: the control is meant to test the rule engine's assignment,
# so the model must have the same option list the rule has.
CONTROL_ALPHA = """你是食品安全行政处罚文书的编码员。只依据文书内容，判断该处罚决定针对的违法行为属于哪一类，从下面的封闭清单中选且只选一个，用英文代码回答。

{defs}

要求：只输出一行 JSON，不要解释。格式：
{{"violation_category": "<CODE>"}}

文书：
<<<DOC>>>
"""
CONTROL_BETA = """任务：给一份中国食品安全行政处罚决定书归类。

步骤（在心里做，不要输出）：1) 找出处罚所依据的法律条文；2) 判断该条文规制的行为；3) 把它对应到下面清单中的一个代码。

{defs}

只输出 JSON：{{"violation_category": "<CODE>", "basis_quote": "支持的原文片段（不超过30字）"}}

决定书全文：
<<<DOC>>>
"""


# Coarse buckets (D-76 fallback). Fixed before the negative control is read.
COARSE = {
    "FORGED_INSPECTION_REPORT": "DATA_FALSIFICATION",
    "TAMPERED_TRACEABILITY": "DATA_FALSIFICATION",
    "FAKE_CERTIFICATION": "DATA_FALSIFICATION",
    "FALSE_LABELING": "DATA_FALSIFICATION",
    "UNLICENSED_OPERATION": "UNLICENSED",
    "TRADEMARK_INFRINGEMENT": "MARKET_ORDER",
    "FALSE_ADVERTISING": "MARKET_ORDER",
    "PRODUCT_QUALITY": "MARKET_ORDER",
    "PROCEDURAL_NONCOMPLIANCE": "PROCEDURAL",
    "UNRESOLVED": "UNDETERMINED",
}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dedupe(d: dict) -> dict:
    return dict(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))


# --- statute map v2 --------------------------------------------------------
def load_v2() -> dict:
    return load_yaml("config/statute_map_v2.yaml")


def _canon_v2(mp: dict) -> dict:
    canon = {}
    for law, names in (mp.get("law_aliases") or {}).items():
        for n in names:
            canon[n] = law
    return canon


def _pairs(mp: dict) -> dict[str, set[tuple[str, str]]]:
    out = {}
    for cat, spec in mp["categories"].items():
        out[cat] = {tuple(p) for p in spec.get("statutes", [])}
    return out


def label_v2(text: str, mp: dict) -> dict:
    """Same algorithm as `anchors.label`, different table.

    Kept deliberately identical: penalty clause first, then all cited
    articles; when several categories remain, the violation-phrase lexicon may
    pick *inside* that set only. Any behavioural difference between v1 and v2
    is therefore attributable to the table, which is the only thing E6 changes.
    """
    canon = _canon_v2(mp)
    pairs = _pairs(mp)

    def norm(statutes):
        return [(canon.get(law, law), art) for law, art in statutes]

    def map_to_cats(statutes):
        got = set()
        for cat, ps in pairs.items():
            for s in statutes:
                if s in ps:
                    got.add(cat)
        return got

    cited = norm(anchors.extract_statutes(text))
    penalty = norm(anchors.penalty_statutes(text))
    facts = anchors.fact_categories(text)
    src = "penalty_statute"
    cand = map_to_cats(penalty) if penalty else set()
    if not cand:
        cand = map_to_cats(cited)
        src = "cited_statute"
    if len(cand) == 1:
        return {"category": next(iter(cand)), "basis": src}
    if cand:
        chosen = [c for c in facts if c in cand]
        if len(chosen) == 1:
            return {"category": chosen[0], "basis": "statute+fact"}
        return {"category": None,
                "basis": "ambiguous_facts" if len(chosen) > 1 else "ambiguous_statute"}
    if len(facts) == 1:
        return {"category": facts[0], "basis": "fact_only"}
    return {"category": None,
            "basis": "ambiguous_facts" if len(facts) > 1 else "none"}


APPL = "行政处罚法"


def unresolved_none_profile(text: str, mp: dict) -> dict:
    """What a basis='none' document actually files under (D-81).

    Description, not a gate. Two readings per document:

    * `penalty_only_appl` -- the penalty clause names nothing but the
      Administrative Penalty Law. That is a mechanism, not a coverage gap: the
      substantive violation is described in the facts, while the decision's
      penalty clause invokes only the procedural act, so a statute-to-category
      engine has nothing to map.
    * `cited` -- every statute the document cites (doc-level, deduplicated).
      The point is to show whether the residue is one missing statute or a
      long tail of subject matter outside the five fraud categories.
    """
    canon = _canon_v2(mp)
    pen = sorted({canon.get(law, law) for law, _ in anchors.penalty_statutes(text)})
    cited = sorted({canon.get(law, law) for law, _ in anchors.extract_statutes(text)})
    return {"penalty_only_appl": bool(pen) and all(APPL in p for p in pen),
            "cited": cited}


# --- food categories -------------------------------------------------------
def load_food() -> dict:
    return load_yaml("config/food_categories.yaml")


FACT_START = re.compile(r"(?:经查|经调查|查明|违法事实|现查明)")
FACT_END = re.compile(r"(?:上述事实|以上事实|上述行为|有下列证据|证据证明|本局认为|我局认为)")


def fact_segment(text: str, limit: int = 1500) -> str:
    """The case-specific part of a decision: from 经查/查明 to 上述事实/证据.

    The rest of the document is statute text quoted verbatim, and that text
    contains the same product nouns as the facts, so matching on the whole
    document measures the template, not the product (measured: "食品、食品添加
    剂" appears in 498/763 decisions). Falls back to the head of the document
    when no fact marker exists, and the fallback is counted separately.
    """
    m = FACT_START.search(text)
    if not m:
        return text[:limit]
    s = m.start()
    e = FACT_END.search(text, s + 10)
    return text[s:(e.start() if e else s + limit)]


def food_hits(payload: dict, fd: dict) -> dict:
    per_cat: dict[str, str] = {}
    for field in fd.get("match_fields", ["text"]):
        blob = payload.get(field) or ""
        if not blob:
            continue
        for cat, spec in fd["categories"].items():
            if cat in per_cat:
                continue
            for term in spec.get("terms", []):
                if term in blob:
                    per_cat[cat] = field
                    break
    primary = None
    for cat in fd.get("primary_priority", []):
        if cat in per_cat:
            primary = cat
            break
    return {"categories": sorted(per_cat), "match_source": per_cat, "primary": primary}


# --- jurisdiction / penalty ------------------------------------------------
def region_of(agency: str | None) -> dict:
    a = (agency or "").strip()
    if not a:
        return {"province": None, "city": None, "level": "unknown"}
    prov = next((p for p in PROVINCES if p in a), None)
    m = re.search(r"([一-鿿]{2,10}?(?:市|自治州|地区))市场监督管理", a)
    city = m.group(1) if m else None
    if prov:
        level = "province_named"
    elif city:
        level = "city"
    elif re.search(r"(县|区)", a):
        level = "county"
    else:
        level = "other"
    return {"province": prov, "city": city, "level": level}


MONEY = re.compile(r"罚款\s*(?:人民币)?\s*([0-9][0-9,，]*(?:\.[0-9]+)?)\s*(万元|元)")
FREE = re.compile(r"(?:没收违法所得|没收非法所得)\s*(?:人民币)?\s*([0-9][0-9,，]*(?:\.[0-9]+)?)\s*(万元|元)")


def _num(s: str, unit: str) -> float:
    v = float(s.replace(",", "").replace("，", ""))
    return v * 10000.0 if unit == "万元" else v


def penalty_of(text: str) -> dict:
    fines = [_num(a, u) for a, u in MONEY.findall(text)]
    gains = [_num(a, u) for a, u in FREE.findall(text)]
    return {"fine_max": max(fines) if fines else None,
            "fine_n_mentions": len(fines),
            "confiscation_max": max(gains) if gains else None}


def _quantiles(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    xs = sorted(xs)

    def q(p):
        k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
        return round(xs[k], 2)

    return {"n": len(xs), "min": round(xs[0], 2), "p25": q(25), "median": q(50),
            "p75": q(75), "p90": q(90), "max": round(xs[-1], 2),
            "mean": round(sum(xs) / len(xs), 2)}


# --- negative control ------------------------------------------------------
def _defs(mp: dict) -> str:
    lines = []
    for cat, spec in mp["categories"].items():
        if cat == "OTHER":
            continue
        tag = "（描述性扩展类，非造假框架内）" if spec.get("descriptive_only") else ""
        lines.append(f"- {cat}: {spec.get('label_zh','')}{tag}")
    lines.append("- OTHER: 上述都不符合")
    return "\n".join(lines)


def control(recs: list[dict], texts: dict, mp: dict, n: int, seed: int) -> dict:
    rng = random.Random(seed)
    ids = sorted(r["doc_id"] for r in recs)
    sample = sorted(rng.sample(ids, min(n, len(ids))))
    by_id = {r["doc_id"]: r for r in recs}
    llm = LLMClient()
    if not llm.health():
        raise RuntimeError("LLM endpoint unavailable for the E6 negative control")
    defs = _defs(mp)
    a_cfg, b_cfg = cfg("llm.channel_a"), cfg("llm.channel_b")
    cap = int(cfg("label.doc_text_chars", 20000))
    def one(did: str) -> dict:
        text = (texts.get(did) or "")[:cap]
        rule = label_v2(text, mp)
        pa = CONTROL_ALPHA.format(defs=defs).replace("<<<DOC>>>", text)
        pb = CONTROL_BETA.format(defs=defs).replace("<<<DOC>>>", text)
        try:
            oa = parse_json(llm.chat(a_cfg["model"], pa, temperature=0.0,
                                     max_tokens=200)[0]) or {}
            ob = parse_json(llm.chat(b_cfg["model"], pb, temperature=0.3,
                                     max_tokens=200)[0]) or {}
        except Exception as exc:  # noqa: BLE001
            return {"doc_id": did, "error": str(exc)[:200]}
        ca = (oa.get("violation_category") or "").strip().upper() or None
        cb = (ob.get("violation_category") or "").strip().upper() or None
        return {"doc_id": did, "rule": rule["category"], "basis": rule["basis"],
                "a": ca, "b": cb,
                "rule_vs_a": rule["category"] is not None and rule["category"] == ca,
                "rule_vs_b": rule["category"] is not None and rule["category"] == cb}

    from concurrent.futures import ThreadPoolExecutor
    workers = max(1, int(cfg("label.workers", 4)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, sample))
    ok = [r for r in rows if "error" not in r]
    def rate(key):
        return round(sum(1 for r in ok if r[key]) / len(ok), 4) if ok else None
    ra, rb = rate("rule_vs_a"), rate("rule_vs_b")
    primary = round((ra + rb) / 2, 4) if ok else None
    # Post-hoc diagnostic (D-79): the pre-registered statistic counts a rule
    # abstention as a disagreement. That conflates "the engine refused to
    # decide" with "the engine decided wrongly", so coverage and the rate among
    # decided documents are reported next to it. The gate above is unchanged --
    # this diagnostic was added after seeing the primary and is labelled so.
    decided = [r for r in ok if r["rule"]]
    diag = {
        "rule_coverage": round(len(decided) / len(ok), 4) if ok else None,
        "agreement_on_decided": {
            "n": len(decided),
            "rule_vs_a": round(sum(1 for r in decided if r["rule_vs_a"]) / len(decided), 4)
            if decided else None,
            "rule_vs_b": round(sum(1 for r in decided if r["rule_vs_b"]) / len(decided), 4)
            if decided else None,
        },
        "label": "post-hoc diagnostic, not the gate (D-79)",
    }
    tgt, flo = float(cfg("label.agreement_target")), float(cfg("label.agreement_floor"))
    status = ("target_met" if primary is not None and primary >= tgt else
              "floor_met" if primary is not None and primary >= flo else "below_floor")
    return {"n_requested": n, "n_scored": len(ok), "seed": seed,
            "doc_ids": sample, "rows": rows,
            "rule_vs_a": ra, "rule_vs_b": rb,
            "agreement_primary": primary,
            "agreement_definition": ("mean of (rule==channel_a) and (rule==channel_b), exact "
                                     "category match, documents the rule leaves unresolved "
                                     "count as disagreements"),
            "llm_a_vs_b": round(sum(1 for r in ok if r["a"] and r["a"] == r["b"]) / len(ok), 4)
            if ok else None,
            "thresholds": {"target": tgt, "floor": flo}, "status": status,
            "diagnostic": diag}


# --- main ------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-n", type=int, default=50)
    ap.add_argument("--no-control", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    mp = load_v2()
    if int(mp.get("version", 0)) < 2:
        print("statute_map_v2.yaml has no version>=2", file=sys.stderr)
        return 1
    fd = load_food()
    all_recs = [json.loads(line) for line in open(SILVER, encoding="utf-8") if line.strip()]
    # Results 1 is the Chinese penalty-decision corpus (D1'). The US recalls
    # (D3a) are a different document genre and are handled in E8; pooling them
    # here would mix two instruments in one trend line.
    recs = [r for r in all_recs if r.get("lang") == "zh"]
    excluded = len(all_recs) - len(recs)
    if not recs:
        print("no Chinese silver records", file=sys.stderr)
        return 1

    m = Manifest()
    texts, metas, pub = {}, {}, {}
    with m.conn() as c:
        for row in c.execute("SELECT doc_id, text_path, meta, published FROM docs"):
            if row["text_path"]:
                try:
                    texts[row["doc_id"]] = Path(row["text_path"]).read_text(encoding="utf-8")
                except OSError:
                    pass
            metas[row["doc_id"]] = json.loads(row["meta"] or "{}")
            pub[row["doc_id"]] = row["published"]

    missing = [r["doc_id"] for r in recs if r["doc_id"] not in texts]
    if missing:
        print(f"{len(missing)} silver docs have no text on disk, e.g. {missing[:3]}",
              file=sys.stderr)
        return 1

    cats, basis = collections.Counter(), collections.Counter()
    year_cat: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    year_n = collections.Counter()
    food_multi, food_primary = collections.Counter(), collections.Counter()
    food_src = collections.Counter()
    prov, city, level = collections.Counter(), collections.Counter(), collections.Counter()
    fines, fines_by_cat = [], collections.defaultdict(list)
    llm_xtab: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    n_lang = collections.Counter()
    none_n, none_appl, none_law = 0, 0, collections.Counter()

    for r in recs:
        did = r["doc_id"]
        text = texts[did]
        lab = label_v2(text, mp)
        cat = lab["category"] or "UNRESOLVED"
        cats[cat] += 1
        basis[lab["basis"]] += 1
        if cat == "UNRESOLVED" and lab["basis"] == "none":
            none_n += 1
            prof = unresolved_none_profile(text, mp)
            none_appl += int(prof["penalty_only_appl"])
            for law in prof["cited"]:
                none_law[law] += 1
        n_lang[r.get("lang")] += 1
        year = (pub.get(did) or "")[:4] or "unknown"
        year_n[year] += 1
        year_cat[year][cat] += 1
        llm_xtab[r.get("violation_category") or "NONE"][cat] += 1
        meta = metas.get(did, {})
        fh = food_hits({"penalty_content": meta.get("penalty_content") or "",
                        "fact_segment": fact_segment(text)}, fd)
        for c_ in fh["categories"]:
            food_multi[c_] += 1
        food_primary[fh["primary"] or "UNMATCHED"] += 1
        for c_, f_ in fh["match_source"].items():
            food_src[f_] += 1
        rg = region_of(meta.get("agency"))
        prov[rg["province"] or "unresolved"] += 1
        city[rg["city"] or "unresolved"] += 1
        level[rg["level"]] += 1
        pen = penalty_of(text)
        if pen["fine_max"] is not None:
            fines.append(pen["fine_max"])
            fines_by_cat[cat].append(pen["fine_max"])

    out = {
        "at_utc": utc_iso(),
        "silver": {"path": str(SILVER), "sha256": _sha(SILVER), "n": len(recs)},
        "map_version": int(mp["version"]),
        "food_dict_version": int(fd.get("version", 1)),
        "n_docs": len(recs),
        "frame": "Chinese penalty decisions (silver lang=zh); US recalls are E8's population",
        "excluded_non_cn": excluded,
        "by_lang": dict(n_lang),
        "category_distribution": _dedupe(cats),
        "basis_distribution": _dedupe(basis),
        "resolved_share": round(1 - cats["UNRESOLVED"] / len(recs), 4),
        "unresolved_none": {
            "n": none_n,
            "penalty_clause_only_administrative_penalty_law": none_appl,
            "law_mentioned_doc_counts": dict(sorted(none_law.items(),
                                                    key=lambda kv: (-kv[1], kv[0]))[:15]),
            "note": ("Documents whose cited statutes miss the v2 map entirely. "
                     "Two readings, both descriptive: a formal mechanism (penalty "
                     "clause invokes only the Administrative Penalty Law) and the "
                     "subject matter they actually cite (e.g. measurement law, bar "
                     "code, patent, trade secrets -- outside the five fraud "
                     "categories). Neither is used to move a document into a "
                     "category (D-81).")},
        "year_distribution": dict(sorted(year_n.items())),
        "year_category_counts": {y: dict(sorted(v.items())) for y, v in sorted(year_cat.items())},
        "food_category": {"multi_label": _dedupe(food_multi),
                          "primary": _dedupe(food_primary),
                          "match_source": dict(sorted(food_src.items())),
                          "unmatched_share": round(food_primary["UNMATCHED"] / len(recs), 4)},
        "region": {"level": _dedupe(level), "province": _dedupe(prov),
                   "city_top": dict(sorted(city.items(), key=lambda kv: (-kv[1], kv[0]))[:30]),
                   "note": ("The national portal does not publish a province field; municipal "
                            "sites (the planned region source) are uncalibrated, 1 of 50 with "
                            "1 admitted document. Region is therefore read from the issuing "
                            "authority string: province when named, otherwise city/county as "
                            "written. No province is imputed from a city name.")},
        "penalty": {"fine_quantiles": _quantiles(fines),
                    "by_category": {k: _quantiles(v) for k, v in sorted(fines_by_cat.items())},
                    "unit": "CNY"},
        "llm_cross_tab": {k: dict(sorted(v.items())) for k, v in sorted(llm_xtab.items())},
        "llm_cross_tab_note": ("Rows are the frozen silver (LLM) category, columns the "
                               "deterministic v2 category. Descriptive only; on conflict the "
                               "deterministic result is the one reported (D-77)."),
    }

    # Coarse fallback required by the plan when a dimension fails its negative
    # control: the detailed table is kept, but the reported Results 1 figure is
    # this one. Mapping is fixed here, before the control outcome is read.
    coarse = collections.Counter()
    for k, v in cats.items():
        coarse[COARSE.get(k, "UNDETERMINED")] += v
    out["coarse_distribution"] = _dedupe(coarse)

    if args.no_control:
        out["negative_control"] = {"status": "not_run", "reason": "--no-control"}
        out["granularity"] = "unverified"
    else:
        seed = args.seed if args.seed is not None else int(cfg("analysis.seed", 20261104))
        ctl = control(recs, texts, mp, args.control_n, seed)
        out["negative_control"] = ctl
        out["granularity"] = "fine" if ctl["status"] in ("target_met", "floor_met") else "coarse"

    write_json(OUT, out)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(_markdown(out), encoding="utf-8")
    print(json.dumps({"e6": "ok", "n_docs": len(recs),
                      "granularity": out["granularity"],
                      "control": out["negative_control"].get("agreement_primary"),
                      "out": str(OUT)}, ensure_ascii=False))
    return 0


def _markdown(o: dict) -> str:
    L = ["# E6 确定性描述表（Results 1）", "",
         f"- 生成时刻：{o['at_utc']}",
         f"- 语料：{o['silver']['n']} 篇，sha `{o['silver']['sha256'][:16]}…`",
         f"- 法规映射表版本：v{o['map_version']}；食品词典版本：v{o['food_dict_version']}",
         f"- 规则可判定比例：{o['resolved_share']:.4f}", "",
         "## 1 违规类型分布（确定性，规则引擎）", "",
         "| 类别 | 篇数 | 占比 |", "|---|---:|---:|"]
    n = o["n_docs"]
    for k, v in o["category_distribution"].items():
        L.append(f"| {k} | {v} | {v / n:.4f} |")
    if o.get("coarse_distribution"):
        L += ["", "### 粗粒度（负对照未过底线时，Results 1 报这一张）", "",
              "| 粗类 | 篇数 | 占比 |", "|---|---:|---:|"]
        for k, v in o["coarse_distribution"].items():
            L.append(f"| {k} | {v} | {v / n:.4f} |")
    L += ["", "## 2 判定依据分布", "", "| basis | 篇数 |", "|---|---:|"]
    for k, v in o["basis_distribution"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## 3 年度趋势（篇数）", "", "| 年 | 篇数 |", "|---|---:|"]
    for k, v in o["year_distribution"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## 4 食品类别（主类）", "", "| 类别 | 篇数 | 占比 |", "|---|---:|---:|"]
    for k, v in o["food_category"]["primary"].items():
        L.append(f"| {k} | {v} | {v / n:.4f} |")
    L += ["", "## 5 地域（按发文机关）", "", "| 层级 | 篇数 |", "|---|---:|"]
    for k, v in o["region"]["level"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "### 市级 top 15", "", "| 市 | 篇数 |", "|---|---:|"]
    for k, v in list(o["region"]["city_top"].items())[:15]:
        L.append(f"| {k} | {v} |")
    pq = o["penalty"]["fine_quantiles"]
    L += ["", "## 6 处罚力度（罚款，元）", "",
          f"- 有罚款金额的文书：{pq.get('n', 0)}/{n}",
          f"- 中位数 {pq.get('median')}；p25 {pq.get('p25')}；p75 {pq.get('p75')}；"
          f"p90 {pq.get('p90')}；最大 {pq.get('max')}"]
    L += ["", "## 7 负对照（规则 vs 双通道 LLM）", ""]
    c = o["negative_control"]
    if c.get("status") == "not_run":
        L.append(f"- 未运行：{c.get('reason')}")
    else:
        L += [f"- 样本：{c['n_scored']}/{c['n_requested']}（seed {c['seed']}）",
              f"- 规则 vs 通道 A：{c['rule_vs_a']}",
              f"- 规则 vs 通道 B：{c['rule_vs_b']}",
              f"- 主判据（两者均值）：{c['agreement_primary']} → **{c['status']}**",
              f"- 通道 A vs B：{c['llm_a_vs_b']}"]
        dg = c.get("diagnostic") or {}
        if dg:
            L += [f"- 事后诊断（非判据，D-79）：规则可判定率 {dg.get('rule_coverage')}；"
                  f"在可判定子集上 vs A {dg['agreement_on_decided']['rule_vs_a']}、"
                  f"vs B {dg['agreement_on_decided']['rule_vs_b']}"]
        L += ["", f"粒度判定：**{o['granularity']}**"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
