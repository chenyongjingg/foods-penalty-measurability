# -*- coding: utf-8 -*-
"""Verify the built .docx against the layout the publisher's template implies.

The submission file is laid out on Frontiers' own Word template
(Frontiers_Word_Templates/Frontiers_Template.docx, styles and sectPr kept,
instructional body dropped), so the expected geometry is the template's, not a
generic A4 page.

D1  page        : Letter 8.50 x 11.00 in; template margins 0.89 left / 0.82 right /
                  0.79 top; usable width 6.79 in
D2  spacing     : single line spacing throughout (the template's Normal is
                  240-auto), resolving each paragraph's style chain; cells 1.0
D3  styles      : one Title at 16 pt bold centred; Heading 1 / Heading 2 in use;
                  every resolved body font Times New Roman
D4  tables      : fixed layout, widths sum <= usable width, header row repeats
D5  column fit  : every numeric cell's widest token fits its column at 9 pt
D6  cells       : all table runs 9 pt Times New Roman; numeric columns flush right
D7  figure      : exactly one image referenced by document.xml, >= 300 dpi at its
                  printed size, caption in the template's Caption style
D8  rules       : no paragraph borders
D9  text        : the docx carries every numeric token the markdown body carries
D10 package     : the template's "provisional file" sentence appears nowhere in
                  the package and the even-page footer is not referenced
D11 numbering   : line numbers run continuously across the page; exactly the six
                  substantive sections carry a section number (the appendix, the
                  statements, References and Tables are suppressed with numId 0)
"""
from __future__ import annotations

import io
import re
import struct
import sys
import zipfile
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
DOCX = HERE / "manuscript_frontiers_v2.docx"
MD = HERE / "manuscript_frontiers_v2.src.md"

PAGE_W_IN, PAGE_H_IN = 8.50, 11.00
MARGINS = {"left": 0.89, "right": 0.82, "top": 0.79}
USABLE = PAGE_W_IN - MARGINS["left"] - MARGINS["right"]          # 6.79 in
NUM_COLS = {0: [1], 1: [1, 2], 2: [1, 2, 3, 4, 5], 3: [2, 3, 4, 5]}
NUM = re.compile(r"(?<![\w.])[−-]?\d(?:[\d,]*\d)?(?:\.\d+)?%?")


def chain(style):
    """Paragraph style followed by its basedOn ancestors."""
    out, seen = [], set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        out.append(style)
        style = style.base_style
    return out


def eff_line_spacing(p):
    """Paragraph line spacing, falling back up the style chain; None = single."""
    for owner in [p] + chain(p.style):
        ls = owner.paragraph_format.line_spacing
        if ls is not None:
            return ls
    return 1.0


def eff_alignment(p):
    """Paragraph alignment, falling back up the style chain."""
    for owner in [p] + chain(p.style):
        al = owner.paragraph_format.alignment
        if al is not None:
            return al
    return None


def eff_font(p, run=None):
    """Run font, else the first font named up the paragraph's style chain."""
    if run is not None and run.font.name:
        return run.font.name
    for st in chain(p.style):
        if st.font.name:
            return st.font.name
    return None


def main() -> int:
    d = docx.Document(str(DOCX))
    fails: list[str] = []

    # ---- D1 --------------------------------------------------------------
    s = d.sections[0]
    pw, ph = s.page_width.inches, s.page_height.inches
    ok_page = abs(pw - PAGE_W_IN) < 0.01 and abs(ph - PAGE_H_IN) < 0.01
    got = {"left": s.left_margin.inches, "right": s.right_margin.inches, "top": s.top_margin.inches}
    ok_m = all(abs(got[k] - v) < 0.01 for k, v in MARGINS.items())
    print(f"D1 page          : {pw:.2f} x {ph:.2f} in "
          f"{'PASS Letter' if ok_page else 'FAIL'}, margins "
          f"L{got['left']:.2f} R{got['right']:.2f} T{got['top']:.2f} in "
          f"{'PASS template' if ok_m else 'FAIL'}, usable {USABLE:.2f} in")
    if not (ok_page and ok_m):
        fails.append("D1 page")

    # ---- D2 --------------------------------------------------------------
    bad_sp = [(p.style.name, eff_line_spacing(p)) for p in d.paragraphs
              if p.text.strip() and abs(eff_line_spacing(p) - 1.0) > 1e-6]
    cell_bad = 0
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    if p.text.strip() and p.paragraph_format.line_spacing not in (None, 1.0):
                        cell_bad += 1
    print(f"D2 spacing       : body single {'PASS' if not bad_sp else 'FAIL ' + str(bad_sp[:4])}; "
          f"cells 1.0 {'PASS' if not cell_bad else 'FAIL ' + str(cell_bad)}")
    if bad_sp or cell_bad:
        fails.append("D2 spacing")

    # ---- D3 --------------------------------------------------------------
    titles = [p for p in d.paragraphs if p.style.name == "Title"]
    h1 = [p for p in d.paragraphs if p.style.name == "Heading 1"]
    h2 = [p for p in d.paragraphs if p.style.name == "Heading 2"]
    t_bad = []
    for p in titles:
        f = p.style.font
        if f.size is None or f.size.pt != 16 or not f.bold:
            t_bad.append((f.size.pt if f.size else None, f.bold))
        if eff_alignment(p) != WD_ALIGN_PARAGRAPH.CENTER:
            t_bad.append(("align", str(eff_alignment(p))))
    bold_h1 = [p.text[:30] for p in h1 if not p.style.font.bold]
    fonts = {eff_font(p, r) for p in d.paragraphs for r in p.runs if p.text.strip()}
    fonts.discard(None)
    ok_font = fonts <= {"Times New Roman"}
    print(f"D3 styles        : Title {len(titles)} "
          f"{'PASS 16 pt bold centred' if not t_bad else 'FAIL ' + str(t_bad)}, "
          f"Heading 1 {len(h1)} {'PASS' if not bold_h1 else 'FAIL ' + str(bold_h1[:3])}, "
          f"Heading 2 {len(h2)}, fonts {sorted(fonts)} {'PASS' if ok_font else 'FAIL'}")
    if t_bad or bold_h1 or not titles or not h2 or not ok_font:
        fails.append("D3 styles")

    # ---- D4 --------------------------------------------------------------
    t_bad, sums = [], []
    for ti, t in enumerate(d.tables):
        widths = [c.width.inches if c.width else None for c in t.rows[0].cells]
        tot = sum(w for w in widths if w)
        sums.append(round(tot, 2))
        layout = t._tbl.tblPr.find(qn("w:tblLayout"))
        fixed = layout is not None and layout.get(qn("w:type")) == "fixed"
        hdr = t.rows[0]._tr.trPr is not None and t.rows[0]._tr.trPr.find(qn("w:tblHeader")) is not None
        if not (fixed and hdr and tot <= USABLE + 0.01 and all(widths)):
            t_bad.append((ti + 1, fixed, hdr, round(tot, 2)))
    print(f"D4 tables        : widths {sums} (usable {USABLE:.2f}) "
          f"{'PASS' if not t_bad else 'FAIL ' + str(t_bad)}")
    if t_bad:
        fails.append("D4 tables")

    # ---- D5 / D6 ---------------------------------------------------------
    over, font_bad, align_bad = [], [], []
    for ti, t in enumerate(d.tables):
        widths = [c.width.inches for c in t.rows[0].cells]
        for ri, row in enumerate(t.rows):
            for ci, c in enumerate(row.cells):
                txt = c.text.strip()
                for tok in txt.replace("*", "").split():
                    tok = tok.strip("()[]%,")
                    if not tok or not re.fullmatch(r"[−-]?[\d.,]+(?:[–-][\d.,]+)?", tok):
                        continue
                    need = len(tok) * 0.0625 + 0.16
                    if need > widths[ci]:
                        over.append((ti + 1, ci, tok, round(need, 2), round(widths[ci], 2)))
                for p in c.paragraphs:
                    for r in p.runs:
                        if r.font.size is not None and r.font.size.pt != 9:
                            font_bad.append((ti + 1, r.text[:20], r.font.size.pt))
                        if r.text.strip() and r.font.name not in (None, "Times New Roman"):
                            font_bad.append((ti + 1, r.text[:20], r.font.name))
                    if ri > 0 and ci in NUM_COLS.get(ti, []) and txt:
                        if p.alignment != WD_ALIGN_PARAGRAPH.RIGHT:
                            align_bad.append((ti + 1, ci, txt[:16]))
    print(f"D5 column fit    : {'PASS' if not over else 'FAIL ' + str(over[:5])}")
    print(f"D6 cells         : 9 pt {'PASS' if not font_bad else 'FAIL ' + str(font_bad[:4])}; "
          f"numeric right-aligned {'PASS' if not align_bad else 'FAIL ' + str(align_bad[:4])}")
    if over:
        fails.append("D5 column fit")
    if font_bad or align_bad:
        fails.append("D6 cells")

    # ---- D7 --------------------------------------------------------------
    # The template's first-page header carries its logo, so "one image in the
    # package" would be false; what matters is one image in the document body.
    z = zipfile.ZipFile(str(DOCX))
    doc = z.read("word/document.xml").decode("utf-8")
    embeds = sorted(set(re.findall(r'r:embed="(rId\d+)"', doc)))
    px = None
    if len(embeds) == 1:
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        target = re.search(r'Id="%s"[^>]*Target="([^"]+)"' % embeds[0], rels)
        if target:
            part = "word/" + target.group(1).lstrip("/").replace("word/", "")
            b = z.read(part)
            px = struct.unpack(">II", b[16:24])
    m = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', doc)
    dpi = None
    if px and m:
        dpi = round(px[0] / (int(m.group(1)) / 914400))
    caps = [p for p in d.paragraphs
            if p.style.name == "Caption" and p.text.strip().startswith("Figure 1.")]
    ok_fig = len(embeds) == 1 and bool(caps) and dpi is not None and dpi >= 300
    print(f"D7 figure        : {len(embeds)} image(s) in body, {px[0]}x{px[1]} px at "
          f"{int(m.group(1)) / 914400:.2f} in wide -> {dpi} dpi, Caption style "
          f"{'PASS' if caps else 'FAIL'} {'PASS' if ok_fig else 'FAIL'}")
    if not ok_fig:
        fails.append("D7 figure")

    # ---- D8 --------------------------------------------------------------
    rules = doc.count("<w:pBdr>")
    print(f"D8 rules         : {rules} paragraph borders {'PASS' if rules == 0 else 'FAIL'}")
    if rules:
        fails.append("D8 rules")

    # ---- D9 --------------------------------------------------------------
    md = MD.read_text(encoding="utf-8")
    body = md  # tables sit after the reference list, so cut the list, not the tail
    body = re.sub(r"## References\n(?:(?!\{REFERENCES\}).*\n)*\{REFERENCES\}\n", "", body)
    body = re.sub(r"^---\n.*?\n---\n", "", body, flags=re.S)   # YAML never reaches the docx
    body = re.sub(r"\{[^{}\n]*\}", " ", body)                  # pandoc attributes, e.g. {width=100%}
    body = re.sub(r"^```.*$", "", body, flags=re.M)            # fences, not the commands inside
    want = set(NUM.findall(body))
    have = set(NUM.findall("\n".join(p.text for p in d.paragraphs)
                           + "\n" + "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)))
    miss = sorted(want - have)
    print(f"D9 text          : markdown body {len(want)} numeric tokens, "
          f"docx {len(have)}, missing {len(miss)} {'PASS' if not miss else 'FAIL ' + str(miss[:8])}")
    if miss:
        fails.append("D9 text")

    # ---- D10 -------------------------------------------------------------
    parts_with_text = [n for n in z.namelist()
                       if n.endswith(".xml") and b"provisional file" in z.read(n)]
    sect = re.search(r"<w:sectPr.*?</w:sectPr>", doc, re.S)
    even_ref = bool(sect) and 'w:type="even"' in "".join(
        re.findall(r'<w:footerReference[^>]*/>', sect.group(0)))
    print(f"D10 package      : 'provisional file' in {len(parts_with_text)} part(s) "
          f"{'PASS' if not parts_with_text else 'FAIL ' + str(parts_with_text)}, "
          f"even footer ref {'FAIL present' if even_ref else 'PASS absent'}")
    if parts_with_text or even_ref:
        fails.append("D10 package")

    # ---- D11 -------------------------------------------------------------
    # Line numbering is continuous, not restarted per page. The template's
    # sectPr carries <w:lnNumType>; a "restart" of anything but "continuous"
    # (or a missing element) would renumber every page from 1.
    ln = re.search(r"<w:lnNumType[^>]*/>", sect.group(0)) if sect else None
    restart = re.search(r'w:restart="([^"]+)"', ln.group(0)) if ln else None
    cont = bool(ln) and (restart is None or restart.group(1) == "continuous")

    # Section numbers come from the Heading 1 style's numId; a paragraph-level
    # numId 0 overrides it. Exactly the six substantive sections keep a number.
    SIX = ["Introduction", "Materials and Methods", "Results", "Discussion",
           "Limitations", "Conclusion"]
    numbered = []
    for p in h1:
        pPr = p._p.pPr
        numPr = pPr.find(qn("w:numPr")) if pPr is not None else None
        nid = None
        if numPr is not None and numPr.find(qn("w:numId")) is not None:
            nid = numPr.find(qn("w:numId")).get(qn("w:val"))
        if nid != "0":
            numbered.append(p.text.strip())
    print(f"D11 numbering    : line numbers "
          f"{'continuous' if cont else 'ABSENT / restart=' + (restart.group(1) if restart else 'none')}, "
          f"numbered sections {len(numbered)} of {len(h1)} "
          f"{'PASS 1-6' if numbered == SIX else 'FAIL ' + str(numbered)}")
    if not cont or numbered != SIX:
        fails.append("D11 numbering")

    print("\nRESULT:", "ALL CHECKS PASS" if not fails else "FAILURES: " + "; ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
