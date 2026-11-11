# -*- coding: utf-8 -*-
"""Render COVER_LETTER.md as a plain Word file.

The cover letter is uploaded as its own document, so it is deliberately not
laid on the manuscript template: no heading styles, no line numbers, no page
numbers. One paragraph per block of the markdown, Times New Roman 12 pt,
single-spaced with 12 pt after, Letter page with 1 in margins.

Typographic quotes are applied at render time only; COVER_LETTER.md stays
ASCII so the two files cannot drift apart in wording.

Output: COVER_LETTER.docx
"""
from __future__ import annotations

import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path

import docx
from docx.shared import Inches, Pt

HERE = Path(__file__).resolve().parent
SRC = HERE / "COVER_LETTER.md"
OUT = HERE / "COVER_LETTER.docx"


def smart(text: str) -> str:
    """Straight quotes -> typographic, alternating per string.

    Every string here has at most one double-quoted span (the article title),
    so alternating from an opening quote is exact; the single quote in
    "journal's" is an apostrophe, which is what a lone ' always is.
    """
    out, open_q = [], True
    for ch in text:
        if ch == '"':
            out.append("“" if open_q else "”")
            open_q = not open_q
        elif ch == "'":
            out.append("’")
        else:
            out.append(ch)
    return "".join(out)


def main() -> int:
    paras = [p.strip() for p in SRC.read_text(encoding="utf-8").split("\n\n") if p.strip()]
    # A block separated by a blank line is one Word paragraph; a single newline
    # inside a block is a line break within it. The signature block depends on
    # this: name, affiliation and "on behalf of" must sit tight, while the
    # blank line after "Sincerely," keeps the gap a signature needs.
    blocks: list[tuple[list[str], int]] = []
    for i, p in enumerate(paras):
        lines = [l.strip() for l in p.split("\n") if l.strip()]
        blocks.append((lines, 12 if i < len(paras) - 1 else 0))

    d = docx.Document()
    s = d.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, side, Inches(1.0))

    normal = d.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    pf = normal.paragraph_format
    pf.space_before = Pt(0)
    pf.line_spacing = 1.0

    for lines, after in blocks:
        p = d.add_paragraph()
        for i, line in enumerate(lines):
            run = p.add_run(smart(line))
            if i < len(lines) - 1:
                run.add_break()
        p.paragraph_format.space_after = Pt(after)

    d.save(str(OUT))
    src = SRC.read_text(encoding="utf-8")
    words = len(re.findall(r"[A-Za-z][A-Za-z’'\-]*", src))
    print(f"wrote {OUT.name}: {len(blocks)} paragraphs, source {words} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
