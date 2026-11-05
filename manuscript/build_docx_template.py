#!/usr/bin/env python3
"""Fill the MDPI *Foods* Word template with the manuscript.

Why this exists: `foods-template.dot` (the file MDPI ships) is an OOXML *template*
package. python-docx refuses to open a package whose main part is
`wordprocessingml.template.main+xml`, so the build first copies the package and
rewrites that one content-type string to `document.main+xml`. Nothing else in the
package is touched, which means every style, the headers, the footers, the theme,
the numbering definitions and the first-page editorial block (Academic Editor /
Received-...-Published / copyright) are the template's own, not a look-alike.

Content still comes from `manuscript_submission.md`, which remains the single source
of truth, through a small block parser:

    ## heading          -> MDPI_2.1_heading1
    ### heading         -> MDPI_2.2_heading2
    paragraph           -> MDPI_3.1_text
    **Table N.** line   -> MDPI_4.1_table_caption
    pipe table          -> three-line table (top/bottom rules, rule under the header)
    ![Figure 1. ...]    -> MDPI_5.2_figure + MDPI_5.1_figure_caption
    ## Statements block -> MDPI_6.2_back_matter
    References          -> MDPI_8.1_references

Fenced blocks (```{=latex} \\newpage ```) are LaTeX-only and are skipped.
The front matter is parsed out of the markdown's own title block and asserted, so a
change to the author list cannot silently leave the Word file behind.

Output: manuscript_submission.docx
"""
from __future__ import annotations

import copy
import re
import sys
import zipfile
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = ROOT / "foods-template.dot"
SRC = HERE / "manuscript_submission.md"
OUT = HERE / "manuscript_submission.docx"
FIG = HERE / "figure1_estimability.png"

# text width of the template's page (twips): A4 minus its 0.5 in side margins.
TEXT_WIDTH = 10466

CT_TEMPLATE = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
CT_DOCUMENT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


# --------------------------------------------------------------------------- package

def make_openable_copy(src: Path, dst: Path) -> None:
    """Copy the .dot package, rewriting only the main part's content type."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        patched = 0
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                text = data.decode("utf-8")
                if CT_TEMPLATE not in text:
                    raise SystemExit("template content type not found — is this the MDPI .dot?")
                text = text.replace(CT_TEMPLATE, CT_DOCUMENT)
                data = text.encode("utf-8")
                patched += 1
            zout.writestr(item, data)
    if patched != 1:
        raise SystemExit("content-type part missing from the template package")


# ------------------------------------------------------------------------ md parsing

def read_source() -> dict:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    if not lines[0].startswith("# "):
        raise SystemExit("first line is not the title")
    title = lines[0][2:].strip()

    # the front-matter block sits between the title and the first '---'
    fm = [l.strip() for l in lines[1:12] if l.strip()]
    authors = next(l for l in fm if l.count("^") >= 2 and not l.startswith("^"))
    affiliation = next(l for l in fm if l.startswith("^1^"))
    correspondence = next(l for l in fm if l.startswith("\\*"))
    article = next(l for l in fm if l.startswith("**Article type:**"))
    for probe in ("Public Security University", "ppsuc.edu.cn", "Article"):
        if probe not in " ".join(fm):
            raise SystemExit(f"front matter no longer contains {probe!r}")

    def section(name: str) -> list[str]:
        start = next(i for i, l in enumerate(lines) if l.strip() == f"## {name}")
        out = []
        for l in lines[start + 1:]:
            if l.startswith("## "):
                break
            out.append(l)
        return out

    abstract_lines = [l.strip() for l in section("Abstract") if l.strip() and l.strip() != "---"]
    kw_line = next(l for l in abstract_lines if l.startswith("**Keywords:**"))
    abstract = " ".join(l for l in abstract_lines if not l.startswith("**Keywords:**"))

    body = section("1. Introduction")
    body = lines[lines.index("## 1. Introduction"):lines.index("## Statements")]
    statements = section("Statements")
    references = section("References")

    return dict(title=title, authors=authors, affiliation=affiliation,
                correspondence=correspondence, article=article,
                abstract=abstract, keywords=kw_line[len("**Keywords:**"):].strip(),
                body=body, statements=statements, references=references)


def parse_blocks(lines: list[str]) -> list[tuple]:
    blocks: list[tuple] = []
    i = 0
    boundary = ("## ", "### ", "|", "![", "```")
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):                       # LaTeX-only fence: drop it whole
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            continue
        if s == "---":
            i += 1
            continue
        if s.startswith("### "):
            blocks.append(("h2", s[4:].strip()))
            i += 1
            continue
        if s.startswith("## "):
            blocks.append(("h1", s[3:].strip()))
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", rows))
            continue
        if s.startswith("!["):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", s)
            if not m:
                raise SystemExit(f"unparsable figure line: {s[:80]}")
            blocks.append(("figure", m.group(1), m.group(2)))
            i += 1
            continue
        if s.startswith("**Table "):
            blocks.append(("table_caption", s))
            i += 1
            continue
        buf = [s]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith(boundary) or nxt == "---":
                break
            buf.append(nxt)
            i += 1
        text = " ".join(buf)
        # an italic "Source:" note directly under a table is that table's footer
        kind = "table_footer" if (blocks and blocks[-1][0] == "table"
                                  and text.startswith("*Source:")) else "p"
        blocks.append((kind, text))
    return blocks


# ------------------------------------------------------------------------- rendering

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)")


def add_runs(par, text: str, bold: bool = False, italic: bool = False) -> None:
    """Render the markdown inline subset the manuscript actually uses.

    Code spans are printed without a monospace font on purpose: they are file names
    and hashes, and the journal sets them in body text. Nothing is dropped — the
    backticks go, the identifier stays.
    """
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            add_runs(par, part[2:-2], bold=True, italic=italic)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = par.add_run(part[1:-1])
            r.bold, r.italic = bold, italic
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            add_runs(par, part[1:-1], bold=bold, italic=True)
        else:
            r = par.add_run(part)
            r.bold, r.italic = bold, italic


def add_paragraph_text(par, text: str) -> None:
    """Whole-line emphasis first, because the table notes are '*... **...** ...*'.

    A line wrapped in single asterisks is italic as a whole; the bold spans inside it
    stay bold and are also italic, which is what the markdown means. Splitting on the
    bold tokens first would leave the outer asterisks as literal characters.
    """
    if text.startswith("*") and not text.startswith("**") and text.endswith("*") \
            and len(text) > 2 and not text.endswith("**"):
        add_runs(par, text[1:-1], italic=True)
    else:
        add_runs(par, text)


def para(doc, style: str, text: str = "", bold: bool = False, italic: bool = False):
    p = doc.add_paragraph(style=style)
    if text:
        add_runs(p, text, bold=bold, italic=italic)
    return p


def superscript_runs(par, text: str, trailing_star: bool = False) -> None:
    """'Yongjin Chen^1^, ...' -> text runs with superscript markers."""
    for part in re.split(r"(\^[^\\^]+?\^)", text):
        if not part:
            continue
        if part.startswith("^") and part.endswith("^") and len(part) > 2:
            r = par.add_run(part[1:-1])
            r.font.superscript = True
        else:
            par.add_run(part)
    if trailing_star:
        par.add_run("*")


def set_table_frame(table, ncols: int, widths: list[int]) -> None:
    tblPr = table._tbl.tblPr
    for tag in ("w:tblW", "w:tblBorders", "w:tblLayout"):
        old = tblPr.find(qn(tag))
        if old is not None:
            tblPr.remove(old)
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(TEXT_WIDTH))
    w.set(qn("w:type"), "dxa")
    borders = OxmlElement("w:tblBorders")
    for edge, val, sz in (("top", "single", "8"), ("left", "none", "0"),
                          ("bottom", "single", "8"), ("right", "none", "0"),
                          ("insideH", "none", "0"), ("insideV", "none", "0")):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), val)
        e.set(qn("w:sz"), sz)
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "auto")
        borders.append(e)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(w)
    tblPr.append(borders)
    tblPr.append(layout)
    table.autofit = False
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = width


def header_rule(table) -> None:
    for cell in table.rows[0].cells:
        tcPr = cell._tc.get_or_add_tcPr()
        old = tcPr.find(qn("w:tcBorders"))
        if old is not None:
            tcPr.remove(old)
        b = OxmlElement("w:tcBorders")
        for edge in ("top", "left", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "none")
            b.append(e)
        e = OxmlElement("w:bottom")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "auto")
        b.append(e)
        tcPr.append(b)


def split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def add_table(doc, lines: list[str]) -> None:
    rows = [split_row(l) for l in lines]
    rows = [r for r in rows if not is_separator(r)]
    ncols = len(rows[0])
    for r in rows:
        if len(r) != ncols:
            raise SystemExit(f"ragged table row ({len(r)} vs {ncols} cells): {r}")
    # column widths proportional to the longest cell, floor 8 characters
    weights = []
    for c in range(ncols):
        longest = max(len(re.sub(r"[*`]", "", r[c])) for r in rows)
        weights.append(max(longest, 8))
    scale = TEXT_WIDTH / sum(weights)
    widths = [int(w * scale) for w in weights]
    widths[-1] += TEXT_WIDTH - sum(widths)

    table = doc.add_table(rows=len(rows), cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_frame(table, ncols, widths)
    header_rule(table)
    for r, cells in enumerate(rows):
        for c, text in enumerate(cells):
            cell = table.cell(r, c)
            par = cell.paragraphs[0]
            par.style = doc.styles["MDPI_4.2_table_body"]
            add_runs(par, text, bold=(r == 0))
    return


def add_figure(doc, caption: str, image: Path) -> None:
    p = doc.add_paragraph(style="MDPI_5.2_figure")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(image), width=Inches(6.3))
    para(doc, "MDPI_5.1_figure_caption", caption)


# ----------------------------------------------------------------------------- main

def main() -> int:
    for need, why in ((TEMPLATE, "the MDPI Foods template"), (SRC, "the manuscript"),
                      (FIG, "Figure 1 (run make_figure1.py)")):
        if not need.exists():
            raise SystemExit(f"missing {why}: {need}")

    src = read_source()
    make_openable_copy(TEMPLATE, OUT)
    doc = docx.Document(OUT)
    body = doc.element.body

    # keep the template's first-page editorial block and its disclaimer, then clear
    editor_block = copy.deepcopy(doc.tables[0]._tbl)
    disclaimer = copy.deepcopy(
        next(p._p for p in doc.paragraphs if p.style.name == "MDPI_6.3_notes"))
    sectPr = body.find(qn("w:sectPr"))
    if sectPr is None:
        raise SystemExit("template has no section properties")
    for child in list(body):
        if child is not sectPr:
            body.remove(child)

    # ---- front matter -----------------------------------------------------
    para(doc, "MDPI_1.1_article_type", "Article")
    para(doc, "MDPI_1.2_title", src["title"])

    p = doc.add_paragraph(style="MDPI_1.3_authornames")
    superscript_runs(p, re.sub(r"\\\*$", "", src["authors"].rstrip()), trailing_star=True)

    body.insert(list(body).index(sectPr), editor_block)

    p = doc.add_paragraph(style="MDPI_1.6_affiliation")
    superscript_runs(p, src["affiliation"])
    p = doc.add_paragraph(style="MDPI_1.6_affiliation")
    p.add_run("*").bold = True
    add_runs(p, " " + src["correspondence"].lstrip("\\*,").strip())

    para(doc, "MDPI_1.7_abstract", "Abstract", bold=True)
    para(doc, "MDPI_1.7_abstract", src["abstract"])
    p = doc.add_paragraph(style="MDPI_1.8_keywords")
    p.add_run("Keywords: ").bold = True
    add_runs(p, src["keywords"])
    doc.add_paragraph(style="MDPI_1.9_line")

    # ---- body -------------------------------------------------------------
    for block in parse_blocks(src["body"]):
        kind = block[0]
        if kind == "h1":
            para(doc, "MDPI_2.1_heading1", block[1])
        elif kind == "h2":
            para(doc, "MDPI_2.2_heading2", block[1])
        elif kind == "p":
            p = doc.add_paragraph(style="MDPI_3.1_text")
            add_paragraph_text(p, block[1])
        elif kind == "table_footer":
            p = doc.add_paragraph(style="MDPI_4.3_table_footer")
            add_paragraph_text(p, block[1])
        elif kind == "table_caption":
            para(doc, "MDPI_4.1_table_caption", block[1])
        elif kind == "table":
            add_table(doc, block[1])
        elif kind == "figure":
            add_figure(doc, block[1], FIG)
        else:
            raise SystemExit(f"unknown block {kind}")

    # ---- back matter ------------------------------------------------------
    for line in src["statements"]:
        s = line.strip()
        if not s or s == "---":
            continue
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)$", s, re.S)
        if not m:
            raise SystemExit(f"statement without a bold label: {s[:60]}")
        p = doc.add_paragraph(style="MDPI_6.2_back_matter")
        p.add_run(m.group(1) + ":").bold = True
        add_runs(p, " " + m.group(2))

    # ---- references -------------------------------------------------------
    para(doc, "MDPI_2.1_heading1", "References")
    for line in src["references"]:
        s = line.strip()
        if not s or s == "---":
            continue
        p = doc.add_paragraph(style="MDPI_8.1_references")
        add_paragraph_text(p, s)

    body.insert(list(body).index(sectPr), disclaimer)

    doc.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
