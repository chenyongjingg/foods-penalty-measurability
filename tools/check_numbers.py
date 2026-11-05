#!/usr/bin/env python3
"""Check every number in the manuscript against numbers.csv.

For each number-like token in the manuscript this prints whether some numbers.csv
row licenses it. Licensed means: the token equals the row's value, or its value
rounded to the token's precision, or 100x the value rounded to one decimal
(percent form). Numbers that no row licenses are reported; a human then decides
whether they are structural (section numbers, years, thresholds quoted from the
protocol) or a real leak.

Usage:  python check_numbers.py [manuscript.md]
Exit code 1 if any unlicensed numeric token remains.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

CSV = Path(r"D:\Foods\numbers.csv")
DOC = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\Foods\manuscript\manuscript_v1.md")

# structural tokens that are not measurements: section/table/figure numbers, the
# reference markers, protocol constants quoted as design choices, and calendar dates.
STRUCTURAL = {
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    "0.5", "0.3", "0.7", "0.75", "20", "50", "200", "2000", "5000", "1000",
    "2015", "2019", "2020", "2021", "2022", "2024", "2025", "2026",
    "8192", "8,192", "3000", "4000", "5192", "5,192", "1e-4", "16", "32",
    "120",                          # +-120-character adjudication window (design constant)
    "12,000",                       # 12,000-character input cap shared by E13/E15/E16
    "0.42",                         # jieba 0.42.1, a software version
    "535", "113", "121",            # numbers.csv rows; deviations unique numbers / headings
    "3,4,5",                        # citation marker
    "20261104",                     # negative-control slice seed (an id, not a measurement)
    "2020", "2021", "2022", "2024", "2025", "2015", "2019",  # reference years
}


# numbers quoted from a cited work rather than measured here; licensed by that work's
# registered record (refs_crossref.json / the published abstract), not by numbers.csv.
CITED = {
    "782",   # ref [2]: 782 Indian food-safety cases, 2022-2024 (ACL Anthology abstract)
}


SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")


def tokens(text: str):
    """Yield number-like tokens that are not inside a hash, an identifier, a section
    reference or a DOI. A scientific-notation expression is yielded whole, including
    the typographic form with Unicode superscripts ("2.16 × 10⁻³⁷"), because otherwise
    the mantissa is checked alone and no row for the exponent can license it."""
    for m in re.finditer(
            r"\d[\d,]*\.?\d*(?:\s*[×x]\s*10\s*[\^\-−⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹]*\s*[⁰¹²³⁴⁵⁶⁷⁸⁹\d]+)?", text):
        raw, pos = m.group(0), m.start()
        before = text[pos - 1] if pos else " "
        after = text[m.end()] if m.end() < len(text) else " "
        # inside an identifier / hash / DOI
        if before.isalnum() or before in "_-.:/" or after.isalnum() or after in "_:":
            continue
        # a truncated sha256 prefix: eight or more hex digits followed by an ellipsis.
        # A measurement of that shape does not occur in this manuscript, and the full
        # hash is written out in the product files it points to.
        if after == "…" and len(raw) >= 8 and re.fullmatch(r"[0-9a-f]+", raw):
            continue
        # section reference such as 3.3 / 2.1 (a single digit either side)
        if re.fullmatch(r"\d\.\d", raw):
            continue
        # a trailing sentence period or comma is not part of the number
        raw = raw.rstrip(".,")
        yield raw, pos


def norm(raw: str) -> float | None:
    s = raw.translate(SUP).replace(",", "").replace(" ", "")
    m = re.fullmatch(r"([\d.]+)[×x]10\^?(-?\d+)", s)
    if m:
        return float(m.group(1)) * 10 ** int(m.group(2))
    s = s.replace("−", "-")
    try:
        return float(s)
    except ValueError:
        return None


def main() -> int:
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    vals: dict[str, str] = {}
    for r in rows:
        v = r["value"]
        if r["id"] == "t1tab.body":
            # every cell of Table 1 is licensed by the single serialised row
            for cell in v.replace(";", ":").split(":"):
                vals.setdefault(cell, "t1tab.body")
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        # Deliberately narrow: only exact and 4/3-decimal forms, plus the percent
        # forms. Coarser rounding (2dp, 1dp, integer) used to licence unrelated
        # numbers -- e.g. a body "0.3241" passed because some row rounded to 0.32 --
        # which made "every number is licensed by a row" vacuously true.
        for k in (f, round(f, 4), round(f, 3), int(f) if f == int(f) else f,
                  round(f * 100, 1), round(f * 100, 2)):
            vals.setdefault(repr(k), r["id"])
            vals.setdefault(f"{k:g}", r["id"])
            vals.setdefault(f"{k:,.0f}", r["id"])
        # scientific notation: compare mantissas, since round(x, 3) collapses any
        # value below 1e-3 to 0 and would license nothing.
        if f:
            for spec in ("e", ".2e", ".3e", ".4e"):
                vals.setdefault(f"{f:{spec}}", r["id"])

    text = DOC.read_text(encoding="utf-8")
    # The References section is licensed by refs_crossref.json (registered metadata),
    # not by numbers.csv: volumes, pages and years there are bibliographic, not
    # measurements. Scan stops at the References heading; an unclosed reference block
    # would show up as unlicensed tokens below, so this cannot hide a body number.
    refs_at = text.find("\n## References")
    refs_note = ""
    if refs_at != -1:
        refs_note = f"(references section excluded: {len(text) - refs_at} chars)"
        text = text[:refs_at]
    misses: list[tuple[str, int]] = []
    hits = 0
    for raw, pos in tokens(text):
        if raw in STRUCTURAL or raw in CITED:
            continue
        f = norm(raw)
        if f is None:
            continue
        cands = {raw, raw.replace(",", ""), f"{f:g}", f"{round(f,4):g}", f"{round(f,3):g}",
                 f"{f:,.0f}" if f == int(f) else f"{f:g}"}
        if f:
            cands |= {f"{f:.2e}", f"{f:.3e}", f"{f:.4e}"}
        if any(c in vals for c in cands):
            hits += 1
        else:
            line = text.count("\n", 0, pos) + 1
            misses.append((raw, line))

    print(f"licensed tokens: {hits} {refs_note}")
    if misses:
        print(f"UNLICENSED tokens: {len(misses)}")
        seen = set()
        for raw, line in misses:
            key = (raw, line)
            if key in seen:
                continue
            seen.add(key)
            print(f"  line {line:>4}: {raw}")
        return 1
    print("all numeric tokens licensed or explicitly structural")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
