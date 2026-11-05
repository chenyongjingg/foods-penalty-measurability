# foods-penalty-audit

Code, products and pre-registration register for a measurement audit of **1,128
food-safety documents** — 875 Chinese administrative penalty decisions and 253 US
recall records — treated not as a sample to be described but as an **instrument to be
tested**.

The paper asks one question: *what can this record support?* The answer is a ladder.
Agreement between two independent annotation channels is measurable; the composition of
the corpus within its sampling frame is reportable **with the instrument attached**;
prevalence, trend, and case-chain structure are not.

## What is in here

| path | what it is |
|---|---|
| `manuscript/` | `manuscript_submission.md` (the submission source), the built `.docx`, and the estimability-ladder figure |
| `supplementary/` | the 25 files shipped with the paper, plus `MANIFEST.md` — every file with its sha256 and a self-checking verification block |
| `numbers.csv` | provenance sheet: **584 rows**, each naming the product file, the JSON path inside it, the UTC timestamp and the product's sha256 |
| `DEVIATIONS.md` | the append-only pre-registration register, **D-1 … D-131** (129 distinct numbers in 137 headings; `D-111`/`D-112` are canonical labels assigned by `D-110`; a few numbers appear twice because a renumbering would break existing citations) |
| `data/analysis/`, `data/metrics/`, `data/reports/`, `data/events/` | every product file the manuscript cites |
| `data/silver/silver.jsonl` | the frozen corpus index (sha256 `a1deda2c…`) — the file every reported count is computed from |
| `state/foods.sqlite` | crawl and extraction state for all 3,540 documents seen, including those excluded |
| `scripts/`, `foods_pipeline/`, `config/`, `tests/` | the pipeline that produced the products |
| `human/` | three-reader coding files and the coder manual |
| `runs/autopilot/` | the receipt of the unattended run (2026-11-05) |

## What is deliberately **not** in here

- **The corpus itself.** `data/raw/` holds 3,545 government PDFs (446 MB) and is not
  redistributed. The documents are public records, but bulk re-publication is a
  different act from citing them, and it would make this repository unusable. Every
  document in `silver.jsonl` carries the agency, date and identifier needed to retrieve
  it from the publishing portal.
- **Model weights.** Everything here was produced with `Qwen2.5-7B-Instruct` served by
  vLLM with greedy decoding; the weights are public and are not vendored.
- **The virtualenv.** Recreate it from the versions recorded in the register.

## How to check the numbers

Nothing in the manuscript is asserted from memory. Each reported value appears in
`numbers.csv` with the product file it came from, and the product files are here. A
re-derivation script (`scripts/verify_numbers.py`) resolves each row against the product
it names: on the final sheet it re-derives **534 of 584 rows exactly, with 0
mismatches**; the remaining 50 are enumerated by class (27 composite paths, 11
serialised tables, 10 deliberate arithmetic combinations, 2 rows pointing at a
markdown file) and are checked by hand.

Read the register before reading any result. Where a claim was withdrawn, the entry says
so and gives the measurement that withdrew it. The three attempts to automate the
commodity role all failed the same gate fixed before the first API call, and the paper
reports them as failures — with the gate, the numbers, and the cap that stopped further
attempts.

## Status

Prepared for submission to *Foods* (MDPI). The register is append-only: entries are
never edited after the fact, including the ones that record mistakes.
