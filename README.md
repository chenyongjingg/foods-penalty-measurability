# foods-penalty-measurability

**What can a national food-safety penalty record actually measure?** This repository is the
instrument audit, the frozen products and the append-only pre-registration register behind a
manuscript submitted to *Foods* (MDPI). It is built so that every claim in the paper can be
re-derived from a file here, and so that the claims that **could not** be established are
shipped as visibly as the ones that were.

[![verify](https://github.com/chenyongjingg/foods-penalty-measurability/actions/workflows/verify.yml/badge.svg)](https://github.com/chenyongjingg/foods-penalty-measurability/actions/workflows/verify.yml)
![license](https://img.shields.io/badge/license-MIT%20(code)%20%2B%20CC%20BY%204.0%20(text%2Fdata)-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

---

## The study in one paragraph

Administrative penalty decisions are the most abundant machine-readable record of food-safety
enforcement in China, and studies treat them as data without first asking whether they behave
as a measurement instrument. On a frozen corpus of **1,128 documents** — 875 Chinese penalty
decisions and 253 US openFDA recalls — we audit two things: the **agreement channel** that is
used to validate labels, and the **food dimension** that is attached to cases by lexical
matching. Agreement is estimable and moderate; composition within the sampling frame is
reportable with the instrument attached; the food dimension is measurable **in precision
only**; prevalence, trend and case-chain structure are **not estimable**, each for a reason
that is measured rather than asserted. That ordering is the paper's contribution and this
repository's structure: an *estimability ladder*.

## Verify something in 60 seconds

No dependencies beyond Python 3.10:

```sh
git clone https://github.com/chenyongjingg/foods-penalty-measurability.git
cd foods-penalty-measurability
python tools/verify_bundle.py
```

Expected output ends with `all checks passed`; it re-hashes all 26 shipped supplementary files
against `supplementary/MANIFEST.md`, checks that the sheet has the 588 rows the manifest
claims, and confirms that every product path named by a `numbers.csv` row resolves here.

For the two substantive re-derivations a reviewer is most likely to want — Table 3's precision
columns and the gate verdicts — see [`docs/REVIEWER_GUIDE.md`](docs/REVIEWER_GUIDE.md).
Both take a single one-line Python command and print the published value.

## What the record can and cannot support

Every value below is a row in [`numbers.csv`](numbers.csv); that row names the product file,
the JSON field, the product's UTC timestamp and its sha256. Nothing here is quoted from memory.

| claim | value | `numbers.csv` id |
|---|---:|---|
| agreement between two independent annotation channels, pre-registered single pass | 0.6966 | `e1p.mean_agreement` |
| agreement after the reliability ladder (primary result) | 0.7460 | `e1.mean_agreement` |
| agreement on stable violation types only | 0.8610 | `e1.shrunk` |
| anchor micro-F1 over 423 documents | 0.7825 | `anchor.micro` |
| anchor macro-F1 over categories with support ≥ 20 | 0.4195 | `anchor.macro_ge20` |
| documents matched by the 18-category commodity lexicon | 679 / 1,128 | `e12.any_hit` |
| adjudicated hits (15 per category) | 270 | `e12.prec.n` |
| commodity precision, any mention | 0.9296 | `e12.prec.any` |
| commodity precision, subject matter | **0.3852** | `e12.prec.subj` |
| three-reader agreement on the violation typology (Fleiss' κ) | **0.0881** | `e11c.fleiss_kappa` |
| best of three automated attempts on the food role (κ / BA) | 0.4885 / 0.7390 | `e15.kappa`, `e15.ba` |
| free-text extraction: names produced / declines | 896 / 232 | `e16.n_named`, `e16.n_declined` |
| of those names, no lexicon term to bind them to a category | **586 (0.654)** | `e16.n_unmapped_named` |

The negative control is the number to read first: on 50 hand-checked documents the deterministic
layer agrees with a human coding **14 times (0.28)** — at fine and at coarse granularity alike. Everything derived from that layer
is therefore reported as **instrument output, not as an estimate of the underlying conduct**
(register entry D-92).

## Repository map

| path | what it is |
|---|---|
| `manuscript/` | `manuscript_submission.md` (the submission source, v3.1) and the built `.docx`; the estimability-ladder figure; the three adjudication records behind the current revision (`CONFLICT_REVIEW_v3.md`, `HUMAN_DECISIONS_v3.md`, `EDIT_LOG_v3.md`) |
| `manuscript/frontiers_v2/` | the current submission build: Frontiers template, three authors, tables at the end, with its own gates and `SHA256SUMS` (see the README there) |
| `supplementary/` | the 26 files shipped with the paper plus `MANIFEST.md`, which lists each file with its sha256 and a self-checking verification block (26/26) |
| `numbers.csv` | provenance sheet: **588 rows**, each naming the product file, the JSON path inside it, the UTC timestamp and the product's sha256 |
| `DEVIATIONS.md` | the append-only register, D-1 … D-131 (129 distinct numbers in 137 headings; collisions are disclosed and adjudicated in D-104 and D-110) |
| `data/silver/silver.jsonl` | the frozen corpus index, sha256 `a1deda2c…` — the file every reported count is computed from |
| `data/analysis/`, `data/metrics/`, `data/reports/` | every product file the manuscript cites |
| `state/foods.sqlite` | crawl and extraction state for all 3,540 documents seen, including those excluded |
| `scripts/`, `foods_pipeline/`, `config/`, `tests/` | the pipeline that produced the products |
| `human/` | the three-reader coding files and the coder manual |
| `tools/verify_bundle.py` | the repository self-check used by CI |
| `docs/REVIEWER_GUIDE.md` | five checks a reviewer can run in five minutes, with expected output |
| `docs/PIPELINE_OPERATIONS.md` | how the pipeline runs and the invariants that must not be changed silently |
| `PREREG_20261105_rescue.md`, `DECISIONS.md`, `AUDIT_2026-11-04_round2.md` | pre-registration plan, decision log, independent audit of the round before it |

## How the provenance chain works

1. A number enters the manuscript only as a row in `numbers.csv`, which names the product file,
   the JSON path, the timestamp and the product's sha256.
2. The product is a file in this repository (or a member of the shipped release bundle), and it
   records the sha256 of its own inputs — `silver.jsonl` for anything corpus-derived.
3. The supplementary bundle repeats the chain one level up: `MANIFEST.md` lists 26 files with
   sha256 and a verification block, and the whole bundle is also packaged as a single zip for
   journals that accept one attachment only.
4. Design changes are recorded in `DEVIATIONS.md`, which is append-only: a wrong entry is
   corrected by a new `… 更正` entry that names what it corrects, never by editing history.
5. `scripts/verify_numbers.py` re-derives the sheet from the products: on v3.1 it re-derives
   **538 of 588 rows exactly, with 0 mismatches**; the remaining 50 are enumerated by class
   (27 composite paths, 11 serialised tables, 10 deliberate arithmetic combinations, 2 rows
   pointing at a markdown file) and were checked by hand.

## What is deliberately **not** here

- **The corpus itself.** `data/raw/` holds 3,545 government PDFs (446 MB) and is not
  redistributed: the documents are public records, but bulk re-publication is a different act
  from citing them. Every record in `silver.jsonl` carries the agency, date and identifier
  needed to retrieve it from the publishing portal.
- **Model weights.** All generation used `Qwen2.5-7B-Instruct` under greedy decoding; the
  weights are public and not vendored.
- **The virtualenv.** Recreate it from the pinned versions in the register.
- **Any prevalence, trend or coverage estimate.** The portal serves a date-descending window
  of at most four pages per query, so the year distribution is a property of the sampling
  window, not of the world (D-90). Three registered attempts to recover the commodity role
  automatically all failed the same pre-fixed gate, so that axis is reported in precision only,
  and the manual fallback was cancelled before any zero-hit document was read (D-126).

## Rebuild the manuscript

```sh
python manuscript/build_docx_template.py manuscript/manuscript_submission.md manuscript/manuscript_submission.docx
```

The `.docx` is filled into the journal's own template, so styles, headers, the first-page
editorial block and the three-line tables come from the template rather than from Markdown.
The docx sha changes on every rebuild (the zip stores timestamps); **judge freshness by the
markdown's sha and by the template checker, not by the docx hash.**

## Status

Manuscript **v3.1** (2026-11-06): 7,200 words of prose, 199-word abstract, 29 references,
588-row provenance sheet, 26 shipped supplementary files. Prepared for submission to *Foods*
(MDPI) as an Article. The register and the adjudication records are append-only.

**Current submission build (2026-11-11)**: `manuscript/frontiers_v2/` — the same study,
retargeted to *Frontiers in Public Health* (Original Research) and laid out on the publisher's
Word template. Three authors (Chenrui Yang and Xiyuan Wang were removed on instruction),
237-word abstract, tables at the end of the manuscript, all 260 numeric tokens preserved.
`check_v2.py` and `check_docx_v2.py` in that folder re-verify both layers.

## Citation

`CITATION.cff` is the machine-readable form. Until the article is published, cite this
repository:

> Chen, Y.; Yang, C.; Xue, Z.; Wang, X.; Zhu, S. *foods-penalty-measurability: instrument
> audit, products and pre-registration register for a measurement audit of Chinese food-safety
> penalty records* (v3.1). 2026. https://github.com/chenyongjingg/foods-penalty-measurability

## License

Code (`scripts/`, `foods_pipeline/`, `tools/`, `tests/`) is released under the **MIT License**
(see `LICENSE`). The manuscript, the register, the documentation and the data products are
released under **CC BY 4.0**. The corpus originals remain with the publishing agencies and are
not redistributed here.

## Contact

Songze Zhu (corresponding author), People's Public Security University of China —
20196846@ppsuc.edu.cn. Issues and pull requests about reproducibility are welcome; if a number
here does not re-derive, that is a defect in this repository, not a matter of interpretation.
