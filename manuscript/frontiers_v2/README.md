# Frontiers submission build (v2)

The manuscript as it is prepared for **Frontiers in Public Health** (Original Research),
laid out on the publisher's own Word template. This folder is self-contained: the two gate
scripts run here without any other path in the repository.

```sh
python check_v2.py        # content gate C1-C11
python check_docx_v2.py   # layout gate D1-D11
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
| `figure1_estimability.pdf` | Figure 1 as a standalone **vector** file (4 font objects, no raster objects) |
| `figure1_estimability.png` | Figure 1 as a raster file for systems that will not take a PDF (2,280 × 1,950 px) |
| `manuscript_frontiers_v2.lines.md` | the same text with `<!-- L n-m -->` markers giving the line numbers each block occupies in the docx |
| `COVER_LETTER.md` | cover letter, 206 words of body text, naming the Public Health Policy section |
| `COVER_LETTER.docx` | the same letter as a Word file for upload: Times New Roman 12 pt, Letter page, 1 in margins, one page |
| `CHANGES_frontiers_v2.md` | the change log: every edit with its measured effect, including the edits that turned out to be no-ops |
| `SHA256SUMS` | digests of every file in this folder except this list itself |
| `AI_TELLS_RESIDUAL.md` | measured residual AI-writing patterns, each with the judgement made for it, for a human to overrule |
| `check_v2.py`, `check_docx_v2.py` | the two gates |
| `build_cover_letter_docx.py` | renders `COVER_LETTER.md` to `COVER_LETTER.docx` |
| `ai_tells_v2.py` | produces `AI_TELLS_RESIDUAL.md` (counts are reproducible; the judgements are not) |
| `line_map_v2.py` | produces `manuscript_frontiers_v2.lines.md` from Word's own line count, calibrated against five printed anchors |
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
- **D11** line numbers run continuously (Word reports `RestartMode = 0`), and exactly the six
  substantive sections carry a section number — Appendix A, the statements, References and
  Tables do not.

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

## Latest round (2026-11-11): pre-submission polish

Prose only. The Discussion's four aphoristic openers now start from their own numbers; two of
them were rewritten a second time because the first rewrite reproduced Methods and Results
**verbatim**; and three sentences tie the audit to public-health surveillance. No numeric
token, table cell, p-value or interval changed — C1 (258 tokens, the same two e-mail
exemptions) and C2 (four tables byte-identical) are the proof. Word reports 19 pages and
8,847 words.

Three of the four instructed deletions were **not** carried out as written, because
measurement contradicted their premise; §7.1 of `CHANGES_frontiers_v2.md` records each with
what was found in its place.
`AI_TELLS_RESIDUAL.md` lists what remains and the three items that need an author's decision
(the unstated bold key in Table 3, the 93-word protocol sentence, and the `Three …` repetition).

## Rebuilding

`build_docx_template_v2.py` expects the Frontiers template at `../../_frontiers_template/`.
It is not redistributed here; it is the file inside
`https://www.frontiersin.org/Design/zip/Frontiers_Word_Templates.zip`
(`Frontiers_Template.docx`, 695,612 B). The build also needs `pandoc` and `python-docx`.

The `.docx` digest changes on every rebuild because the zip stores timestamps. **Judge
freshness by the markdown digest in `SHA256SUMS`, not by the docx digest.**
