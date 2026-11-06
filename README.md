# foods-penalty-measurability

Code, products and pre-registration register for a measurement audit of **1,128
food-safety documents** — 875 Chinese administrative penalty decisions and 253 US
recall records — treated not as a sample to be described but as an **instrument to be
tested**.

The study asks one question: *what can this record support?* The answer is a ladder.
Agreement between two independent annotation channels is measurable; the composition of
the corpus within its sampling frame is reportable **with the instrument attached**;
prevalence, trend and case-chain structure are not.

## What is in here

| path | what it is |
|---|---|
| `manuscript/` | `manuscript_submission.md` (the submission source, v3.1), the built `.docx`, the estimability-ladder figure, and the three adjudication records behind v3.1 (`CONFLICT_REVIEW_v3.md`, `HUMAN_DECISIONS_v3.md`, `EDIT_LOG_v3.md`) |
| `supplementary/` | the 26 files shipped with the paper, plus `MANIFEST.md` — every file with its sha256 and a self-checking verification block (26/26) |
| `numbers.csv` | provenance sheet: **588 rows**, each naming the product file, the JSON path inside it, the UTC timestamp and the product's sha256 |
| `DEVIATIONS.md` | the append-only pre-registration register, **D-1 … D-131** (129 distinct numbers in 137 headings; `D-111`/`D-112` are canonical labels assigned by `D-110`, and a few numbers appear twice because renumbering would break existing citations) |
| `data/analysis/`, `data/metrics/`, `data/reports/`, `data/events/` | every product file the manuscript cites |
| `data/silver/silver.jsonl` | the frozen corpus index (sha256 `a1deda2c…`) — the file every reported count is computed from |
| `state/foods.sqlite` | crawl and extraction state for all 3,540 documents seen, including those excluded |
| `scripts/`, `foods_pipeline/`, `config/`, `tests/` | the pipeline that produced the products |
| `human/` | three-reader coding files and the coder manual |
| `runs/autopilot/` | receipt of the unattended run of 2026-11-05 |
| `docs/PIPELINE_OPERATIONS.md` | how the pipeline runs, and the invariants that must not be changed silently |
| `PREREG_20261105_rescue.md`, `DECISIONS.md`, `AUDIT_2026-11-04_round2.md` | pre-registration plan, decision log, and an independent audit of the round before it |

## What is deliberately **not** in here

- **The corpus itself.** `data/raw/` holds 3,545 government PDFs (446 MB) and is not
  redistributed: the documents are public records, but bulk re-publication is a
  different act from citing them. Every document in `silver.jsonl` carries the agency,
  date and identifier needed to retrieve it from the publishing portal.
- **Model weights.** Everything here was produced with `Qwen2.5-7B-Instruct` served by
  vLLM under greedy decoding; the weights are public and are not vendored.
- **The virtualenv.** Recreate it from the pinned versions in the register.

## How to check the numbers

Nothing in the manuscript is asserted from memory. Each reported value appears in
`numbers.csv` with the product file it came from, and the product files are here.
`scripts/verify_numbers.py` resolves each row against the product it names: on the final
sheet it re-derives **538 of 588 rows exactly, with 0 mismatches**. The remaining 50 are
enumerated by class — 27 composite paths, 11 serialised tables, 10 deliberate arithmetic
combinations, 2 rows pointing at a markdown file — and were checked by hand. (Of the 538,
534 were re-derived against the corpus snapshot and 4 against
`supplementary/analysis/e16_denominator.json`, which is in this repository.)

Read the register before reading any result. Where a claim was withdrawn, the entry says
so and gives the measurement that withdrew it. The three attempts to automate the
commodity role all failed the same gate, fixed before the first API call, and are
reported as failures: gate, numbers, and the cap that stopped further attempts.

## Status

Prepared for submission to *Foods* (MDPI). Current manuscript: **v3.1** (2026-11-06) —
7,200 words of prose, a 199-word abstract, 29 references, and a 588-row provenance
sheet. The register is append-only: entries are never edited after the fact, including
the ones that record mistakes.
