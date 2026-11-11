# -*- coding: utf-8 -*-
"""Gate for v2. Every check prints its measured count, not a verdict alone.

C1  number freeze      : every numeric token in the v1 body survives in the v2 body
C2  table integrity    : Tables 1-4 byte-identical to v1 (captions may change)
C3  hashes / anchors   : sha256 values and provenance strings still present
C4  abstract           : <=250 words, 4 sub-headings, 15 mandated numbers
C5  length             : whole-file <=12,000 and >=5% below v1; the 15% target is
                         printed as MET / NOT MET rather than asserted
C6  dangling refs      : no "Section X.Y"
C7  citations          : [n] contiguous 1..N in first-appearance order, N list entries
C8  authorship         : author order, email-to-initial mapping, CRediT draft owner
C9  column fit         : no numeric cell wider than its column at 9 pt
C10 prose              : banned meta-discourse 0; "which is why" <=3; "instrument output" <=1
C11 statements         : each statement is its own level-2 heading, ordered
                         Ethics -> Data -> COI -> Funding -> Author Contributions ->
                         Acknowledgments -> Supplementary (Frontiers template)
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
V1 = HERE / "manuscript_frontiers_v1.src.md"
V2 = HERE / "manuscript_frontiers_v2.src.md"
V2MD = HERE / "manuscript_frontiers_v2.md"

NUM = re.compile(r"(?<![\w.])[−-]?\d(?:[\d,]*\d)?(?:\.\d+)?%?")


def body_of(text: str) -> str:
    """Everything except the reference list.

    The reference section is cut as a block rather than by splitting the file:
    since the Frontiers template asks for tables at the end of the manuscript,
    the Tables section now sits after {REFERENCES} and is still body content.
    """
    text = re.sub(r"## References\n(?:(?!\{REFERENCES\}).*\n)*\{REFERENCES\}\n", "", text)
    return text


def tokens(text: str) -> list[str]:
    return NUM.findall(re.sub(r"`[^`]*`", " ", text))


def words(text: str) -> int:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"[|#*_>]", " ", text)
    return len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", text))


def table_block(text: str, n: int) -> str:
    m = re.search(r"\*\*Table %d\.\*\*.*?\n\n((?:\|.*\n)+)" % n, text)
    return m.group(1) if m else ""


def main() -> int:
    t1, t2 = V1.read_text(encoding="utf-8"), V2.read_text(encoding="utf-8")
    b1, b2 = body_of(t1), body_of(t2)
    fails: list[str] = []

    # ---- C1 -------------------------------------------------------------
    s1, s2 = set(tokens(b1)), set(tokens(b2))
    # A token may leave the body only if the thing that carried it was removed on
    # instruction. The list is named rather than patterned: a general "it looked
    # like an e-mail address" rule would also swallow a real number that happened
    # to sit in one. Each entry must still occur exactly once in v1, as the local
    # part of an address, or it is not exempt.
    EMAIL_EXEMPT = {
        "202321440020": "Xiyuan Wang, author removed",
        "2024111033": "Chenrui Yang, author removed",
        "202420610006": "Yongjin Chen, address replaced 2026-11-11",
        "20196846": "Songze Zhu, address replaced 2026-11-11",
    }
    exempted = [tok for tok in sorted(s1 - s2)
                if tok in EMAIL_EXEMPT and t1.count(tok) == 1
                and re.search(rf"(?<![\w.]){re.escape(tok)}@", t1)]
    gone = sorted(s1 - s2 - set(exempted))
    extra = sorted(s2 - s1)
    print(f"C1 number freeze : v1 {len(s1)} distinct tokens, v2 {len(s2)}")
    if exempted:
        print("   exempt (e-mail local parts, once in v1):",
              " | ".join(f"{t} ({EMAIL_EXEMPT[t]})" for t in exempted))
    if gone:
        print("   LOST VALUES:", " | ".join(gone))
        fails.append(f"C1 {len(gone)} lost")
    else:
        print("   PASS - no numeric token from v1 is absent from v2")
    if extra:
        print("   new tokens (review):", " | ".join(extra))

    # ---- C2 -------------------------------------------------------------
    for n in (1, 2, 3, 4):
        a, b = table_block(t1, n), table_block(t2, n)
        same = bool(a) and a == b
        print(f"C2 Table {n}       : {'PASS byte-identical' if same else 'FAIL differs/absent'}"
              f" ({len(a)} vs {len(b)} chars)")
        if not same:
            fails.append(f"C2 table {n}")

    # ---- C3 -------------------------------------------------------------
    anchors = ["a1deda2c", "52e3ca41", "11108382", "5b961f5c", "0e560f5a",
               "silver.sha256", "n = 875", "e12_commodity_precision.json",
               "data/reports/portal_mechanics.json", "DEVIATIONS.md", "numbers.csv"]
    miss_a = [a for a in anchors if a not in t2]
    print(f"C3 anchors       : {'PASS' if not miss_a else 'FAIL missing ' + str(miss_a)}"
          f" ({len(anchors) - len(miss_a)}/{len(anchors)})")
    if miss_a:
        fails.append("C3 anchors")

    # ---- C4 -------------------------------------------------------------
    m = re.search(r"## Abstract\n(.*?)\n---", t2, re.S)
    abst = m.group(1) if m else ""
    aw = words(abst)
    subs = [s for s in ("Background:", "Methods:", "Results:", "Conclusions:") if s in abst]
    req = ["0.7460", "0.7825", "0.9296", "0.3852", "0.0881", "1,128", "875", "253",
           "604", "679", "270", "0.4195", "0.4885", "0.7390", "14 of 50"]
    miss_r = [r for r in req if r not in abst]
    print(f"C4 abstract      : {aw} words (limit 250), {len(subs)}/4 sub-headings, "
          f"{len(req) - len(miss_r)}/{len(req)} mandated numbers")
    if aw > 250 or len(subs) != 4 or miss_r:
        if miss_r:
            print("   MISSING numbers:", miss_r)
        fails.append("C4 abstract")

    # ---- C5 -------------------------------------------------------------
    w1 = words(re.sub(r"```.*?```", "", t1, flags=re.S))
    w2 = words(re.sub(r"```.*?```", "", t2, flags=re.S))
    cut = (w1 - w2) / w1 * 100
    print(f"C5 length        : v1 {w1} -> v2 {w2} words ({cut:.1f}% below), limit 12,000"
          f" -> {'PASS' if w2 <= 12000 else 'FAIL'}")
    print(f"   15% trim target: {'MET' if cut >= 15 else 'NOT MET'} ({cut:.1f}%)")
    if w2 > 12000 or cut < 5:
        fails.append("C5 length")

    # ---- C6 -------------------------------------------------------------
    dangling = re.findall(r"Section \d+\.\d+", t2)
    print(f"C6 cross-refs    : {'PASS none' if not dangling else 'FAIL ' + str(sorted(set(dangling)))}")
    if dangling:
        fails.append("C6 dangling section refs")

    # ---- C7 -------------------------------------------------------------
    md = V2MD.read_text(encoding="utf-8")
    cited = [int(n) for grp in re.findall(r"\[(\d+(?:,\d+)*)\]", md.split("## References")[0])
             for n in grp.split(",")]
    firsts, seen = [], set()
    for n in cited:
        if n not in seen:
            seen.add(n)
            firsts.append(n)
    ordered = firsts == sorted(firsts) == list(range(1, len(firsts) + 1))
    n_refs = len(re.findall(r"^\d+\. ", md.split("## References")[1], re.M))
    print(f"C7 citations     : {len(set(cited))} distinct, first-appearance ordered "
          f"{'PASS' if ordered else 'FAIL'}, list entries {n_refs} "
          f"{'PASS' if n_refs == len(set(cited)) else 'FAIL'}")
    if not ordered or n_refs != len(set(cited)):
        fails.append("C7 citations")

    # ---- C8 -------------------------------------------------------------
    AUTHORS = {"Ziying Xue": "1", "Yongjin Chen": "2", "Songze Zhu": "2"}
    AFFIL = {"1": "School of Criminal Investigation",
             "2": "School of Police Administration"}
    auth_ok = ("Ziying Xue^1^, Yongjin Chen^2^ and Songze Zhu^2^"
               in t2) and all(f"{n}^{s}^" in t2 for n, s in AUTHORS.items())
    dept_ok = all(re.search(r"\^%s\^ %s, People’s Public Security University of China" % (k, v), t2)
                  for k, v in AFFIL.items())
    email_ok = all(s in t2 for s in ("15620821066@163.com (Z.X.)",
                                     "3337851329@qq.com (Y.C.)",
                                     "Correspondence: Songze Zhu, 18513826980@163.com")) and \
        not any(s in t2 for s in ("(C.Y.)", "(X.W.)", "Chenrui", "Xiyuan",
                                  "202420610006", "20196846"))
    credit_ok = ("Z.X. curated the data, performed the formal analysis, wrote the software and "
                 "prepared the original draft" in t2) and "All three authors" in t2 \
        and "designed its method (methodology)" in t2
    print(f"C8 authorship    : order {'PASS' if auth_ok else 'FAIL'}, departments "
          f"{'PASS' if dept_ok else 'FAIL'}, emails {'PASS' if email_ok else 'FAIL'}, "
          f"CRediT draft to Z.X. {'PASS' if credit_ok else 'FAIL'}")
    if not (auth_ok and dept_ok and email_ok and credit_ok):
        fails.append("C8 authorship")

    # ---- C9 -------------------------------------------------------------
    widths = {1: [1.30, 0.72, 1.05, 1.42, 2.30], 2: [1.55, 0.80, 0.90, 3.54],
              3: [1.42, 1.10, 0.72, 0.72, 1.16, 1.67], 4: [0.85, 2.37, 0.72, 0.95, 0.95, 0.95]}
    CHAR_IN = 0.0625         # 9 pt Times digit advance
    PAD_IN = 0.16            # cell margins left+right
    # Prose cells may wrap between words; what must not wrap is a single number.
    NUMTOK = re.compile(r"[\(\[\{]?[−\-]?[\d.,]+[%\)\]\}]*(?:[–-][\d.,]+[\)\]]*)?$")
    over = []
    for n, w in widths.items():
        rows = [ln for ln in table_block(t2, n).splitlines() if ln.startswith("|")]
        for ln in rows[1:]:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            for i, c in enumerate(cells):
                if i >= len(w):
                    continue
                for tok in re.sub(r"[*`]", "", c).split():
                    if not NUMTOK.match(tok):
                        continue
                    need = len(tok) * CHAR_IN + PAD_IN
                    if need > w[i]:
                        over.append((n, i, tok, round(need, 2), w[i]))
    print(f"C9 column fit    : {'PASS' if not over else 'FAIL ' + str(len(over)) + ' numeric tokens'}")
    for o in over[:6]:
        print("   ", o)
    if over:
        fails.append("C9 column fit")

    # ---- C10 ------------------------------------------------------------
    banned = ["Two properties matter", "Three things bear", "it is worth noting",
              "we must emphasize", "notably", "crucially", "importantly", "in fact"]
    hits = {b: len(re.findall(re.escape(b), t2, re.I)) for b in banned}
    hits = {k: v for k, v in hits.items() if v}
    which = len(re.findall(r"which is why", t2, re.I))
    instr = len(re.findall(r"instrument output", t2, re.I))
    print(f"C10 prose        : meta-discourse {hits or 'PASS 0'}, 'which is why' {which} (<=3), "
          f"'instrument output' {instr} (<=1)")
    if hits or which > 3 or instr > 1:
        fails.append("C10 prose")

    # ---- C11 ------------------------------------------------------------
    order = ["Ethics Statement", "Data Availability Statement", "Conflict of Interest",
             "Funding", "Author Contributions", "Acknowledgments", "Supplementary Material"]
    pos = [t2.find(f"## {k}") for k in order]
    ok = all(p >= 0 for p in pos) and pos == sorted(pos)
    print(f"C11 statements   : {'PASS Frontiers order' if ok else 'FAIL ' + str(dict(zip(order, pos)))}")
    if not ok:
        fails.append("C11 statements")

    print("\nRESULT:", "ALL CHECKS PASS" if not fails else "FAILURES: " + "; ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
