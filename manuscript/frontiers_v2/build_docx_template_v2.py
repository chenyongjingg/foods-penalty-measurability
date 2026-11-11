# -*- coding: utf-8 -*-
"""Lay v2 out on the publisher's own Word template.

The template is the file Frontiers distributes as Frontiers_Word_Templates.zip
(downloaded 2026-11-11). Its styles carry the layout the journal expects: Letter
page with 0.89 in side margins, Times New Roman 12 pt single-spaced body with
6 pt before / 12 pt after, 16 pt centred title, and the paragraph styles
Title, Author List, Heading 1-3, Caption.

Method: strip the template's instructional body but keep its styles and section
properties, hand that to pandoc as --reference-doc, then remap the few styles
pandoc emits by name (Body Text, First Paragraph, Compact) onto the template's
Normal, and apply the table geometry the numbers need.

Output: manuscript_frontiers_v2.docx (the submission file).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent.parent / "_frontiers_template" / "Frontiers_Word_Templates" / "Frontiers_Template.docx"
REF = HERE / "_frontiers_ref.docx"
SRC = HERE / "manuscript_frontiers_v2.md"
FLAT = HERE / "_pandoc_input_v2.md"
OUT = HERE / "manuscript_frontiers_v2.docx"

# Template page: Letter, margins 0.89 left / 0.82 right -> 6.79 in usable.
# Every table fills that width; the extra half inch goes to the widest prose
# column, numeric columns keep the widths the column-fit check validated.
COLUMN_WIDTHS = {
    0: [1.30, 0.72, 1.05, 1.22, 2.50],          # Product column carries file paths
    1: [1.55, 0.80, 0.90, 3.54],
    2: [1.42, 1.10, 0.72, 0.72, 1.16, 1.67],
    3: [0.85, 2.37, 0.72, 0.95, 0.95, 0.95],
}
# Table 1's product column must hold one unbroken token:
# data/analysis/e12_commodity_precision.json measures 2.20 in at 9 pt Times,
# and a cell loses 0.16 in to its default left/right margins. At 2.30 in Word
# broke it mid-word ("...precision.jso n"); 2.50 in leaves 2.34 in of text
# width. The 0.20 in comes from the prose column beside it, which wraps freely.

# Section numbers come from the Heading 1 style (numId 17). Only the six
# substantive sections keep one; the appendix, the statements, References and
# Tables are numbered differently by the publisher, so they carry numId 0.
NUMBERED_H1 = ["Introduction", "Materials and Methods", "Results",
               "Discussion", "Limitations", "Conclusion"]
NUMERIC_COLS = {0: [1], 1: [1, 2], 2: [1, 2, 3, 4, 5], 3: [2, 3, 4, 5]}


def clean_reference() -> None:
    """Keep the template's styles and sectPr, drop its instructional text."""
    d = docx.Document(str(TEMPLATE))
    body = d.element.body
    for child in list(body):
        if child.tag == qn("w:sectPr"):
            continue
        body.remove(child)
    d.save(str(REF))


def pandoc_input() -> None:
    text = SRC.read_text(encoding="utf-8")
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)   # YAML block
    # Bare --- lines are section separators; pandoc would render them as rules.
    text = "\n".join(l for l in text.split("\n") if l.strip() not in ("---",))
    FLAT.write_text(text, encoding="utf-8")


def ensure_section_numbering(d) -> None:
    """Define the list the Heading 1 style points at.

    The template's Heading 1 carries <w:numPr><w:numId w:val="17"/></w:numPr>,
    but pandoc writes its own numbering.xml and numId 17 is not in it, so the
    reference dangles and Word renders no section numbers at all. Define a
    plain decimal "1." list for that id so the six substantive sections print a
    number; the paragraphs that must not are pinned to numId 0 below.
    """
    numbering = d.part.numbering_part.element
    for n in numbering.findall(qn("w:num")):
        if n.get(qn("w:numId")) == "17":
            return
    abs_id = 900
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abs_id))
    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), "0")
    for tag, val in (("w:start", "1"), ("w:numFmt", "decimal"),
                     ("w:lvlText", "%1."), ("w:lvlJc", "left"), ("w:suff", "space")):
        el = OxmlElement(tag)
        el.set(qn("w:val"), val)
        lvl.append(el)
    pPr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "0")
    ind.set(qn("w:firstLine"), "0")
    pPr.append(ind)
    lvl.append(pPr)
    abstract.append(lvl)
    first_num = numbering.find(qn("w:num"))
    if first_num is not None:
        first_num.addprevious(abstract)   # abstractNum elements precede all num
    else:
        numbering.append(abstract)
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), "17")
    an = OxmlElement("w:abstractNumId")
    an.set(qn("w:val"), str(abs_id))
    num.append(an)
    numbering.append(num)


def set_numbering(p, num_id: str) -> None:
    """Pin a paragraph's list id directly (numId 0 = no numbering).

    The Heading 1 style's own numPr is not enough: Word renders nothing for a
    style-level reference that carries no ilvl, so the six numbered sections
    state ilvl and numId on the paragraph itself. numPr has to sit before the
    other pPr children the schema orders after it, so insert rather than append
    when any successor element is already present.
    """
    pPr = p._p.get_or_add_pPr()
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        numPr = OxmlElement("w:numPr")
        successors = ("w:suppressLineNumbers", "w:pBdr", "w:shd", "w:tabs",
                      "w:spacing", "w:ind", "w:contextualSpacing", "w:jc",
                      "w:outlineLvl", "w:rPr", "w:sectPr", "w:pPrChange")
        for tag in successors:
            el = pPr.find(qn(tag))
            if el is not None:
                el.addprevious(numPr)
                break
        else:
            pPr.append(numPr)
    for tag, val in (("w:ilvl", "0"), ("w:numId", num_id)):
        el = numPr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            numPr.append(el)
        el.set(qn("w:val"), val)


def set_table_layout_fixed(table) -> None:
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)


def repeat_header_row(table) -> None:
    trPr = table.rows[0]._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def strip_template_footer_text(path: Path) -> None:
    """Remove the template's provisional-file sentence from the orphaned part.

    The reference is already gone from sectPr, so it cannot print; scrubbing the
    text as well means a later edit cannot resurrect it.
    """
    import zipfile
    buf = path.read_bytes()
    with zipfile.ZipFile(path) as zin:
        items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            if info.filename == "word/footer1.xml":
                xml = data.decode("utf-8")
                xml = re.sub(r"<w:t[^>]*>[^<]*provisional file[^<]*</w:t>", "", xml)
                data = xml.encode("utf-8")
            zout.writestr(info, data)


def main() -> None:
    clean_reference()
    pandoc_input()
    subprocess.run(
        ["pandoc", FLAT.name, "-f", "markdown", "-t", "docx",
         "-o", OUT.name, "--reference-doc", REF.name, "--resource-path", str(HERE)],
        cwd=HERE, check=True,
    )

    d = docx.Document(str(OUT))

    # ---- pandoc's paragraph styles -> the template's Normal --------------
    remap = {"Body Text": "Normal", "First Paragraph": "Normal", "Compact": "Normal"}
    for p in d.paragraphs:
        if p.style.name in remap:
            p.style = d.styles[remap[p.style.name]]

    # ---- markdown levels -> the template's two body levels --------------
    # Snapshot both lists first: mutating Heading 3 -> Heading 2 in place would
    # otherwise make the new Heading 2 paragraphs eligible for the next remap.
    h2 = [p for p in d.paragraphs if p.style.name == "Heading 2"]
    h3 = [p for p in d.paragraphs if p.style.name == "Heading 3"]
    for p in h3:
        p.style = d.styles["Heading 2"]
    for p in h2:
        p.style = d.styles["Heading 1"]

    # ---- title page roles the template names ----------------------------
    heads = [p for p in d.paragraphs if p.style.name == "Heading 1"]
    if heads:
        heads[0].style = d.styles["Title"]           # article title

    # ---- section numbering: six sections, the rest unnumbered ------------
    ensure_section_numbering(d)
    for p in heads:
        if p.style.name == "Heading 1":
            set_numbering(p, "17" if p.text.strip() in NUMBERED_H1 else "0")
    for p in d.paragraphs:
        txt = p.text.strip()
        if p.style.name == "Heading 1" and txt == "Abstract":
            p.style = d.styles["Author List"]        # template heads the abstract in Author List
        elif txt.startswith("Ziying Xue") and p.style.name == "Normal":
            p.style = d.styles["Author List"]        # author line
        elif txt.startswith("**Keywords") or txt.startswith("Keywords:"):
            p.style = d.styles["Author List"]

    # ---- captions -> the template's Caption style ------------------------
    # Match "Table 1." / "Figure 1." only: the in-text sentence "Figure 1 places
    # each research question ..." starts with the same three words but no stop.
    for p in d.paragraphs:
        if re.match(r"^(Table [1-4]|Figure 1)\.", p.text.strip()):
            p.style = d.styles["Caption"]
            p.paragraph_format.keep_together = True   # a caption is one block

    # ---- figure at the template's text width -----------------------------
    # Pandoc sized it from the section; 6.60 in keeps a margin inside the
    # 6.79 in the template's asymmetric pgMar leaves (8.5 - 0.89 - 0.82).
    for shp in d.inline_shapes:
        ratio = shp.height / shp.width
        shp.width = Inches(6.60)
        shp.height = int(shp.width * ratio)

    # ---- tables ---------------------------------------------------------
    cells = 0
    for ti, t in enumerate(d.tables):
        widths = COLUMN_WIDTHS.get(ti)
        if widths and len(widths) == len(t.columns):
            t.autofit = False
            set_table_layout_fixed(t)
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            repeat_header_row(t)
            for idx, w in enumerate(widths):
                t.columns[idx].width = Inches(w)
            for row in t.rows:
                for idx, c in enumerate(row.cells):
                    if idx < len(widths):
                        c.width = Inches(widths[idx])
        for ri, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            if trPr.find(qn("w:cantSplit")) is None:
                trPr.append(OxmlElement("w:cantSplit"))   # keep one row on one page
            for ci, c in enumerate(row.cells):
                for p in c.paragraphs:
                    p.paragraph_format.line_spacing = 1.0
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(1)
                    if ri > 0 and ci in NUMERIC_COLS.get(ti, []):
                        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    for r in p.runs:
                        r.font.size = Pt(9)
                        r.font.name = "Times New Roman"
                cells += 1

    # ---- drop the template's even-page footer ---------------------------
    # It carries the instruction "This is a provisional file, not the final
    # typeset article"; leaving it would print a false statement on every even
    # page. With the reference gone, the default footer (page number) applies.
    sectPr = d.sections[0]._sectPr
    for ref in list(sectPr.findall(qn("w:footerReference"))):
        if ref.get(qn("w:type")) == "even":
            sectPr.remove(ref)

    d.save(str(OUT))
    strip_template_footer_text(OUT)
    s = d.sections[0]
    print(f"wrote {OUT}")
    print(f"page {s.page_width.inches:.2f} x {s.page_height.inches:.2f} in, "
          f"margins {s.left_margin.inches:.2f}/{s.top_margin.inches:.2f} in")
    print(f"paragraphs {len(d.paragraphs)}, tables {len(d.tables)}, cells {cells}")


if __name__ == "__main__":
    main()
