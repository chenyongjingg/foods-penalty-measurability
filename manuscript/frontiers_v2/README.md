# Frontiers submission build (v2)

The manuscript as it is prepared for **Frontiers in Public Health** (Original Research),
laid out on the publisher's own Word template. This folder is self-contained: the two gate
scripts run here without any other path in the repository.

```sh
python check_v2.py        # content gate C1-C11
python check_docx_v2.py   # layout gate D1-D10
```

Both print every measured count and end with `ALL CHECKS PASS`. They exit non-zero on
failure, so they can be used in CI as they stand.

## Files

| file | what it is |
|---|---|
| `manuscript_frontiers_v2.docx` | **the submission file** — Frontiers Word template, Letter page, single-spaced, tables at the end |
| `manuscript_frontiers_v2.pdf` | the same file exported for reading; not an attachment |
| `manuscript_frontiers_v2.src.md` | working source, citation markers unresolved (`{key}`) |
| `manuscript_frontiers_v2.md` | resolved markdown: 29 references, `[1]`–`[29]` in first-appearance order |
| `manuscript_frontiers_v1.src.md` | the baseline the gates compare against; shipped so `check_v2.py` runs here |
| `figure1_estimability.png` | Figure 1 as a standalone high-resolution file (2,280 × 1,950 px) |
| `COVER_LETTER.md` | cover letter, 129 words |
| `CHANGES_frontiers_v2.md` | the change log: every edit with its measured effect, including the edits that turned out to be no-ops |
| `SHA256SUMS` | digests of every file in this folder except this list itself |
| `check_v2.py`, `check_docx_v2.py` | the two gates |
| `build_docx_template_v2.py` | lays the resolved markdown into the template with pandoc `--reference-doc` |
| `resolve_refs_v2.py` | substitutes `{key}` markers for `[n]` and emits the reference list |
| `move_tables_to_end.py` | lifts Tables 1–4 to the end, as the template asks, without touching a byte inside them |

## What the gates actually assert

- **C1** every numeric token in the v1 body survives in v2. The only permitted losses are the
  local parts of the two removed authors' e-mail addresses, and each one is printed by name.
- **C2** Tables 1–4 are byte-identical to v1 (1,634 / 678 / 1,285 / 419 characters).
- **C4** abstract ≤ 250 words with all 15 mandated numbers.
- **C9/D5** no single numeric token is wider than the column it sits in at 9 pt.
- **D1/D2/D3** Letter page with the template's own margins, single spacing, template styles.
- **D7** exactly one image in the document body, ≥ 300 dpi at its printed width.
- **D10** the template's "provisional file" footer sentence appears nowhere in the package.

## What changed from the shipped v3.1

- **Authors**: three (Ziying Xue, Yongjin Chen, Songze Zhu) rather than five; Chenrui Yang and
  Xiyuan Wang were removed on instruction. Affiliations and addresses follow the people, and
  the Methodology role removed with them was assigned to Z.X. and S.Z.
- **Layout**: the publisher's template replaces the previous A4 build — Letter page, single
  line spacing, template heading styles, tables at the end of the manuscript.
- **Numbers**: unchanged. C1 is the proof; the tables are byte-identical.

No numeric value in the manuscript changed, so the provenance chain recorded in `numbers.csv`
is untouched by this build: the counts, denominators, p-values and intervals are the same
values, and the four tables are byte-identical.

## Rebuilding

`build_docx_template_v2.py` expects the Frontiers template at `../../_frontiers_template/`.
It is not redistributed here; it is the file inside
`https://www.frontiersin.org/Design/zip/Frontiers_Word_Templates.zip`
(`Frontiers_Template.docx`, 695,612 B). The build also needs `pandoc` and `python-docx`.

The `.docx` digest changes on every rebuild because the zip stores timestamps. **Judge
freshness by the markdown digest in `SHA256SUMS`, not by the docx digest.**
