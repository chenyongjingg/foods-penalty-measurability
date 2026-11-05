"""Channel ② deterministic anchor engine: statutes + structured fields.

Plan §5.2 defines the anchor as a non-LLM rule engine over the *structured*
fields of a penalty decision: the cited legal basis mapped to a violation
category, plus format checks on party name / decision date / fine amount.

Two implementation notes, recorded in DEVIATIONS.md (D-18):

1. Mapping *every* cited article does not work. 《食品安全法》第一百二十四条 is
   the penalty basis for several different fraud types and appears in nearly
   every decision, so "any cited article" makes almost every document
   ambiguous (measured: 3 of 27 documents resolved to one category). The
   engine therefore reads the **penalty clause** — the article that follows
   依据/根据 — and only falls back to all cited articles when no penalty
   clause is found.
2. When the penalty clause still admits several categories (the 124 case), the
   engine uses a fixed lexicon of violation phrases (伪造检验报告 / 篡改溯源 /
   伪造认证 / 标注虚假) to pick among *that clause's* categories only. It never
   invents a category outside the statute's own candidate set.

Ambiguity policy stays as in `statute_map.yaml`: if the engine cannot resolve
one category, the document is excluded from anchor F1 (recorded, never
guessed).
"""
from __future__ import annotations

import re

from ..common import load_yaml

_ARTICLE = re.compile(
    r"《?([一-鿿]{2,20}?(?:法|条例|办法))》?\s*第([一二三四五六七八九十百零〇\d]+)条")
# The penalty clause: "依据《X法》第Y条…之规定" / "根据《X法》第Y条".
_PENALTY = re.compile(
    r"(?:依据|根据)\s*《([^》]{2,40})》\s*((?:第[一二三四五六七八九十百零〇\d]+条"
    r"(?:第[一二三四五六七八九十百零〇\d]+款)?"
    r"(?:第[一二三四五六七八九十百零〇\d]+项)?[、，,和及\s]*)+)")

# Violation-phrase lexicon. Each pattern is anchored on the *violation object*,
# not on a bare verb, so "篡改生产日期" cannot be read as traceability fraud.
FACT_RULES = [
    ("TAMPERED_TRACEABILITY", [r"(?:篡改|伪造|删除)[^。；]{0,12}(?:溯源码|追溯码|溯源信息|追溯信息)"]),
    ("FAKE_CERTIFICATION", [r"(?:伪造|变造|冒用|买卖|虚假)[^。；]{0,12}(?:认证证书|认证标志|认证材料)"]),
    ("FORGED_INSPECTION_REPORT", [r"(?:伪造|变造|虚假|买卖|出具)[^。；]{0,12}(?:检验报告|检测报告|检验结论|检测数据|检疫证明)"]),
    ("FALSE_LABELING", [r"(?:标注虚假|虚假标注|篡改[^。；]{0,6}生产日期|虚假生产日期|冒用[^。；]{0,8}(?:厂名|厂址|产地))"]),
    ("UNLICENSED_OPERATION", [r"(?:未取得|无证|超出许可范围)[^。；]{0,10}(?:许可|生产经营)"]),
]

_FORMAT = None


def _fmt() -> dict:
    global _FORMAT
    if _FORMAT is None:
        _FORMAT = load_yaml("config/statute_map.yaml").get("format_rules", {})
    return _FORMAT


def _cn_num(s: str) -> str:
    return s.strip()


def _norm_law(name: str) -> str:
    """Normalize a law name captured from running text (DEVIATIONS.md D-39).

    PDF/HTML extraction yields names like ``食用农产品市场销售质量安全监督管理办
    法\\n``, ``依照食品安全法`` or ``中华人民共和国商标法（2019修正）``. Without
    normalization the alias lookup misses and the article silently maps to no
    category, which lowers anchor coverage for a text-formatting reason rather
    than a legal one. Only *formatting* is removed here — leading connectors,
    whitespace, parenthetical amendments — never a suffix, because
    ``食品安全法实施条例`` is a different instrument from ``食品安全法``.
    """
    name = re.sub(r"\s+", "", name)
    name = re.sub(r"（[^）]*）|\([^)]*\)", "", name)
    for pre in ("依照", "根据", "按照", "依据", "违反"):
        if name.startswith(pre):
            name = name[len(pre):]
    return name


def load_map() -> dict:
    return load_yaml("config/statute_map.yaml")


def _canon() -> dict:
    aliases = load_map().get("law_aliases", {})
    canon = {}
    for law, names in aliases.items():
        for n in names:
            canon[n] = law
    return canon


def extract_statutes(text: str) -> list[tuple[str, str]]:
    canon = _canon()
    out = []
    for m in _ARTICLE.finditer(text):
        _nm = _norm_law(m.group(1))
        law = canon.get(_nm, _nm)
        out.append((law, "第" + _cn_num(m.group(2)) + "条"))
    return out


def penalty_statutes(text: str) -> list[tuple[str, str]]:
    """Articles cited as the legal basis of the penalty (after 依据/根据)."""
    canon = _canon()
    out = []
    for m in _PENALTY.finditer(text):
        _nm = _norm_law(m.group(1))
        law = canon.get(_nm, _nm)
        for art in re.finditer(r"第([一二三四五六七八九十百零〇\d]+)条", m.group(2)):
            out.append((law, "第" + _cn_num(art.group(1)) + "条"))
    return out


def fact_categories(text: str) -> list[str]:
    cats = []
    for cat, pats in FACT_RULES:
        for pat in pats:
            if re.search(pat, text):
                cats.append(cat)
                break
    return cats


def _map_statutes(statutes: list[tuple[str, str]]) -> set[str]:
    mp = load_map()
    cats = set()
    for cat, spec in mp["categories"].items():
        pairs = {tuple(p) for p in spec.get("statutes", [])}
        for s in statutes:
            if s in pairs:
                cats.add(cat)
    return cats


def structured_fields(text: str) -> dict:
    """Deterministic extraction of party / case number / date / fine."""
    rules = _fmt()
    party = None
    m = re.search(r"当事人[：:]\s*([^\n。；]{2,40})", text)
    if m:
        party = m.group(1).strip()
    case_no = None
    m = re.search(rules.get("case_no_regex", r"\d{3,}号"), text)
    if m:
        case_no = m.group(0).strip()
    date = None
    m = re.search(rules.get("date_regex", r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})"), text)
    if m:
        date = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    money = None
    m = re.search(rules.get("money_regex", r"([0-9,，.]+)\s*(万元|元)"), text)
    if m:
        money = m.group(0).strip()
    return {"party": party, "case_no": case_no, "date": date, "fine": money}


def label(text: str) -> dict:
    mp = load_map()
    cited = extract_statutes(text)
    penalty = penalty_statutes(text)
    facts = fact_categories(text)
    # Which source the category was read from (DEVIATIONS.md D-34). The
    # penalty clause stays the first choice; when it is present but maps to no
    # known category — a decision whose penalty sentence cites only
    # 《行政处罚法》 (late-payment surcharge, no fraud article) — the engine
    # falls back to the categories of *all* cited articles, as it already did
    # when no penalty clause was found at all. Before D-34 that second case
    # fell straight through to the free-text fact lexicon and lost the statute
    # grounding for 16 of 392 Chinese decisions.
    src = "penalty_statute"
    cand = _map_statutes(penalty) if penalty else set()
    if not cand:
        cand = _map_statutes(cited)
        src = "cited_statute"
    cat = None
    basis = None
    if len(cand) == 1:
        cat, basis = next(iter(cand)), src
    elif cand:
        # The penalty clause admits several categories (e.g. 食品安全法124条):
        # use the violation phrase, but only to choose inside the clause's set.
        chosen = [c for c in facts if c in cand]
        if len(chosen) == 1:
            cat, basis = chosen[0], "statute+fact"
        elif len(chosen) > 1:
            # several distinct fraud objects in one decision: not anchorable
            cat, basis = None, "ambiguous_facts"
        else:
            cat, basis = None, "ambiguous_statute"
    else:
        chosen = facts
        if len(chosen) == 1:
            cat, basis = chosen[0], "fact_only"
        elif len(chosen) > 1:
            cat, basis = None, "ambiguous_facts"
    return {
        "statutes": cited,
        "penalty_statutes": penalty,
        "categories": sorted(cand),
        "source": src,
        "facts": facts,
        "ambiguous": cat is None,
        "category": cat,
        "basis": basis,
        "fields": structured_fields(text),
    }


def anchor_f1(pairs: list[tuple[str, str]]) -> dict:
    """pairs = [(llm_category, anchor_category)] on non-ambiguous docs.

    Macro-F1 is the plan's primary anchor statistic, but with a small set of
    anchor-eligible documents macro-F1 is dominated by classes that have no
    support (a class with zero true positives scores 0 and still divides the
    mean). Both micro and n are therefore always reported next to it, and
    `n` must be checked before the threshold is read (DEVIATIONS.md D-18).
    """
    if not pairs:
        return {"n": 0, "f1": None, "macro_f1": None, "micro_f1": None}
    labels = sorted({a for _, a in pairs} | {l for l, _ in pairs})
    f1s = []
    for lab in labels:
        tp = sum(1 for l, a in pairs if l == lab and a == lab)
        fp = sum(1 for l, a in pairs if l == lab and a != lab)
        fn = sum(1 for l, a in pairs if l != lab and a == lab)
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * p * r / (p + r) if (p + r) else 0.0)
    macro = sum(f1s) / len(f1s) if f1s else 0.0
    micro = sum(1 for l, a in pairs if l == a) / len(pairs)
    return {"n": len(pairs), "f1": round(macro, 4), "macro_f1": round(macro, 4),
            "micro_f1": round(micro, 4),
            "per_class_f1": dict(zip(labels, [round(x, 4) for x in f1s]))}


def anchor_pairs(recs: list[dict]) -> tuple[list[tuple[str, str]], int]:
    """(llm_category, anchor_category) pairs on statute-grounded anchors.

    Single definition of the pair rule, so the extract stage and the gate can
    never disagree about which documents enter the anchor statistic.
    """
    pairs, fact_only = [], 0
    for r in recs:
        a = r.get("anchor") or {}
        if not a.get("category"):
            continue
        if a.get("basis") in ("penalty_statute", "cited_statute",
                              "statute+fact", None):
            pairs.append((r.get("violation_category"), a["category"]))
        else:
            fact_only += 1
    return pairs, fact_only


def anchor_support(pairs: list[tuple[str, str]]) -> dict:
    """Per-class support next to the macro average.

    Macro-F1 divides by the number of labels present on either side, so a
    class with one document contributes a zero and shifts the mean by 1/k
    (D-18). That is fine as a summary only if the reader can see the support,
    hence this block: per class F1 / true support / predicted count, the macro
    over all classes, the macro restricted to classes with support >= 20, and
    micro accuracy.
    """
    from collections import Counter
    true_c = Counter(t for t, _ in pairs)
    pred_c = Counter(p for _, p in pairs)
    labels = sorted(set(true_c) | set(pred_c))
    per = {}
    for lab in labels:
        tp = sum(1 for t, p in pairs if t == lab and p == lab)
        fp = sum(1 for t, p in pairs if p == lab and t != lab)
        fn = sum(1 for t, p in pairs if t == lab and p != lab)
        pr = tp / (tp + fp) if (tp + fp) else 0.0
        rc = tp / (tp + fn) if (tp + fn) else 0.0
        per[lab] = {"f1": round(2 * pr * rc / (pr + rc), 4) if (pr + rc) else 0.0,
                    "support": true_c.get(lab, 0), "predicted": pred_c.get(lab, 0)}
    ge20 = [lab for lab in labels if true_c.get(lab, 0) >= 20]
    return {
        "n": len(pairs), "per_class": per,
        "macro_all_classes": (round(sum(v["f1"] for v in per.values()) / len(per), 4)
                              if per else 0.0),
        "macro_classes_support_ge20": (round(sum(per[l]["f1"] for l in ge20) / len(ge20), 4)
                                       if ge20 else None),
        "micro": (round(sum(1 for t, p in pairs if t == p) / len(pairs), 4)
                  if pairs else 0.0),
        "min_class_support": min(true_c.values()) if true_c else 0,
        "n_classes_support_lt3": sum(1 for v in true_c.values() if v < 3),
        "note": ("A macro figure over classes with almost no support is not a "
                 "statement about extraction quality; read it with this block "
                 "(D-18, D-58). The gated statistic is unchanged."),
    }
