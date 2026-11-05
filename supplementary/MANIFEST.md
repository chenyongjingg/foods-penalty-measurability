# Supplementary material — manifest

Manuscript: *What Chinese Food-Safety Penalty Records Measure: An Audited Baseline, a Commodity-Term Audit, and an Estimability Ladder*
Article type: Article (Foods)
Bundle assembled: 2026-11-05 ｜ **revised 2026-11-05** (see Revision below)

## Revision

One file was replaced after assembly: `refs_crossref.json` grew from 3,896 to 6,311
bytes (seven DOIs → twelve; sha `081823a4…` → `0d970111…`) when five references were
added to the related-work subsection of the manuscript. The added records were fetched
from the Crossref API on 2026-11-05 and appended; **no existing record was rewritten**.
Nothing else in this bundle changed, and no analysis product, script, threshold or
number was touched. This note is written into the manifest rather than into the
deviation register because it changes a shipped file's content and its recorded sha,
not the design or any reported measurement.

This bundle exists because Section 2.7 of the manuscript states that the deviation
register is **published with the supplementary material** and that every quoted
statistic is traceable to a machine-readable sheet, and because Sections 3.3 and 3.4
report a commodity audit and three failed attempts to automate it, whose products are
not in the corpus release. Those statements are only true if these files ship, so they
ship here.

## Files

| File | Bytes | sha256 | What it is |
|---|---:|---|---|
| `DEVIATIONS.md` | 251972 | `11bd5349ca6a3c7cebe3a1aa0e78fe6d18e5227dc663e7349a1b1c5f5e8821c9` | Append-only register. **129 unique entry numbers** (`D-1 … D-131`, with `D-111` and `D-112` existing only as canonical labels assigned by D-110) in **137 headings**. Byte-identical to the register on the compute host at transfer time (`sha256sum` compared, not eyeballed). Numbering irregularity is disclosed in full below. |
| `numbers.csv` | 120621 | `43255b10d98948a93992beba054ab58fd1f78befbe0f78785b6bc37df39cf896` | Number provenance sheet: **584 rows**. Each row carries `id,value,description,product,field,at_utc,sha256`. Every numeric token in the manuscript body is licensed by a row here or is explicitly structural (section numbers, protocol constants, calendar years). |
| `refs_crossref.json` | 6311 | `0d970111834274d2b8ff138a6fa4830b279709ee52b3633f5fb566bd046e7ecd` | Crossref records for the **twelve** cited DOIs, retrieved 2026-11-05. The reference list is reprinted from these records, not paraphrased (D-94). Seven records were present at bundle assembly; five were fetched and appended when the related-work subsection was written, and existing records were never rewritten. |
| `analysis/e12_commodity_index.json` | 66971 | `52e3ca41db38102da29c15bdb8190fd351b1db12a73c6e6e2b54f2c5e16a5c2e` | Commodity-term presence index over all 1,128 cleaned full texts (D-111, D-113, D-114). Carries the lexicon, per-category counts, the negative control, the orphan-file list and the input shas. |
| `analysis/e12_precision_sample.json` | 299726 | `85d90fed0b90890e299eb5aabbfa8235ef126ea792f9512f3a016de10f789e55` | The 270-item adjudication sample: 15 documents per category, selected in `sha256(document_id)` order, each with its ±120-character context windows (D-114). |
| `analysis/e12_commodity_precision.json` | 57959 | `11108382db41aac741bf121c9376e88732dc977f947251c2072c6e017ed77ff8` | Per-hit verdicts (`S`/`I`/`T`/`F`) and the two precision columns with Wilson intervals (D-115). Every verdict appears in the per-hit list, so the counts in Table 3 can be re-derived line by line. |
| `analysis/e13_commodity_subject.json` | 40593 | `fc60b4fa7245d90e331eef1356cfde62d6b56834e72192ca91df91d06098dcf7` | Attempt 1 of 3 in Table 4 (D-117, D-118): the forced 18-way choice, validated on the 270 adjudicated items, with every per-item verdict and the gate result (`not_validated`). |
| `analysis/e13_preds.jsonl` | 186211 | `6738e79d9bb07d2a5b41bd46c73b5a6e8bd7298802e29ed5d7cf19ce6677d012` | One line per document for E13's full-corpus pass: 1,128 rows, each with the model's raw output and its parsed category. **These labels are unusable** (the gate failed) and are shipped only so the failure is auditable. |
| `analysis/e15_validation.json` | 35669 | `5b961f5c27a7b6bce9bd052ffaab8c8bca377519790fcf696b8ca2bbc8567ab9` | Attempt 2 of 3 (D-121, D-122, D-123): eighteen per-category binary questions, document first and question last. 270 items, gate result `not_validated`, with the E13 comparison embedded in the product. |
| `analysis/e15_preds.jsonl` | 38567 | `027c897510605244899c271a7052c1f7e14f496f885a52ac8ca2843a0d62dd20` | The 270 raw one-character answers behind the E15 row of Table 4. |
| `analysis/e16_validation.json` | 48993 | `0e560f5ae95a1c41e3170fca832e0515ef8c6bd3823c1a3b45693b118a34ae4e` | Attempt 3 of 3 (D-124, D-125): free-text commodity name, mapped to the 18 categories by the same frozen lexicon. 270 items, gate result `not_validated`. |
| `analysis/e16_preds.jsonl` | 222828 | `ccd766f1d482d74028064fc1dace2079034ac28faaec5c6219a34d03d1738c77` | One line per document for E16: the extracted name, the lexicon term it matched (if any) and the resulting category. The 818 unmapped rows are the evidence for the binding-failure claim in Section 3.4. |
| `analysis/e11c_three_coder.json` | 2233 | `24da181906e149f781c8729e119e51cea69cfaefdc7deb3b2d0e69f62bb763f4` | Three-reader reliability for the violation typology: Fleiss' κ, the three pairwise agreements with Wilson intervals, and the pre-registered verdict (D-102, D-106). |
| `analysis/e11c_decomposition.json` | 1836 | `cf836f4c928d6ab1568648aa446ae53fde519b165c25a528dfffc3161ae135d0` | Abstention decomposition of the pairwise agreements: how many agreements are both-readers-`OTHER`, the substantive rate that remains, and each reader's `OTHER` share (D-106). |
| `analysis/table1_coarse_by_food.json` | 4004 | `6ba11dc8309f3d386e7bf0aea97214f79b3c606697db7ecb386b7c47c2b043a3` | The coarse-violation × food-category crosstab (at 2026-11-05T04:22:13Z), with the frozen mappings it was built from and the document-level totals. Source of Supplementary Table S1. |
| `table_S1_violation_by_food.md` | 2067 | `fc66e45166a06a1f9c1af2e6fdc09daca23dd779618b1f8d0cba0646a5171ce7` | Supplementary Table S1, generated from the product above by `_tools/make_table_s1.py`; row order is the instrument's own emission order and is deliberately **not** sorted (D-115). |
| `scripts/e12_commodity_index.py` | 10082 | `95826e15013bb1c7b5e9f57890980a81935e480c8b8219b3d1cff32edc258f3f` | The index script, with `criterion_register = "D-111"`. Regenerates the index from the frozen corpus. |
| `scripts/e12_commodity_precision.py` | 9101 | `d10123d25099d714a3c4a79d52f8b818a93781add6f0c4b4a30a0306165ce900` | The adjudication script. The per-hit verdict table is a source literal (positional, 18 categories × 15 positions), so a verdict outside range aborts rather than silently shifting a label. |
| `scripts/e13_commodity_subject.py` | 11189 | `03beae677afe33ec526dde44b94802bed8d53df72375a3d7e499c5f09bd8f474` | E13's instrument and gate, `criterion_register = "D-117"`. Resumable: every answered document is appended before the next request, because an earlier experiment lost 2.3 h of generation to scoring only at the end (D-116). |
| `scripts/e15_binary_format.py` | 9861 | `d9f891f9d93984150f049447a0b703ff9f443e0585e79cc50c4f269500858983` | E15's instrument (`criterion_register = "D-121"`, `secondary = "D-122"`). The document precedes the question so that the eighteen questions about one document share a prefix under the server's prefix cache; the script's docstring records that this is a serving optimisation which cannot change a greedy output. |
| `scripts/e16_extract_commodity.py` | 10318 | `a4d9e2262f9c020eb03e6da6f90dcf9f6ec278239f6a97e9d198dd4aa0e1938f` | E16's instrument (`criterion_register = "D-124"`). Imports the system prompt from `e13_commodity_subject.py` rather than copying it, so the prompt cannot drift between attempts. |
| `analysis/e17_segmentation.json` | 5460 | `9f5432ccdcf3036cf577d8c8e3a5e17f9c830230820ddaac30482ad36afae5e3` | Segmentation sensitivity (D-127, D-129): the same lexicon under a token-boundary rule, both directions. R0 reproduces the frozen counts exactly (the script aborts if it does not); per-category losses and gains, and the 270-item 2×2 with the verdicts of the items each rule loses. |
| `scripts/e17_segmentation.py` | 7340 | `bed9011849d2ffbe9bd24a773445cdd61194c4b1cc1671b1a7a718befd0cea26` | E17's instrument (`criterion_register = "D-127"`). Segments each document once and tests all 18 term lists against the same token boundary set; imports jieba from `/opt/foods/third_party` so the project venv is untouched. |
| `scripts/verify_numbers.py` | 4968 | `e2ab8acf32ea2e886ec4d4a38ad752f9678dfade6665b22e18edf5d29ff9c96e` | Machine re-derivation of every `numbers.csv` row from the product and JSON path it names (D-128 stage 3): **584 rows, 534 re-derived and equal, 0 mismatches**; the remainder are 27 unresolvable composite paths, 11 serialised tables, 2 rows pointing at the register itself (a text product, not resolvable and not a failure) and 10 derived arithmetic rows. |
| `scripts/autopilot.sh` | 3499 | `e5ca89046c31bf5874d50d10c0c95ab2c7a61553130fddab55afc8126fe964ba` | The unattended pipeline (D-128): preflight, E17, provenance verification, receipt, then heartbeat and a vLLM watchdog that restarts the server only after three consecutive failed health checks. |

The frozen corpus itself (1128 records, sha256
`a1deda2c57ccf5eeb2cf3b27782d30087747dfa208264f9b2ec68dcd7b4a077e`), the derived
metrics, and the pipeline source are distributed as the separate release bundle
`foods_silver_20261105` (built 2026-11-05T03:57:03Z; 25 files, verified **25/25** by
`sha256sum -c` after transfer). The thirteen `analysis/` products and eight `scripts/` here
post-date that bundle (produced 07:50–08:46Z) and are therefore shipped with this
supplementary material rather than inside it.

## How to verify

```sh
sha256sum -c <<'EOF'
11bd5349ca6a3c7cebe3a1aa0e78fe6d18e5227dc663e7349a1b1c5f5e8821c9  DEVIATIONS.md
43255b10d98948a93992beba054ab58fd1f78befbe0f78785b6bc37df39cf896  numbers.csv
0d970111834274d2b8ff138a6fa4830b279709ee52b3633f5fb566bd046e7ecd  refs_crossref.json
52e3ca41db38102da29c15bdb8190fd351b1db12a73c6e6e2b54f2c5e16a5c2e  analysis/e12_commodity_index.json
85d90fed0b90890e299eb5aabbfa8235ef126ea792f9512f3a016de10f789e55  analysis/e12_precision_sample.json
11108382db41aac741bf121c9376e88732dc977f947251c2072c6e017ed77ff8  analysis/e12_commodity_precision.json
fc60b4fa7245d90e331eef1356cfde62d6b56834e72192ca91df91d06098dcf7  analysis/e13_commodity_subject.json
6738e79d9bb07d2a5b41bd46c73b5a6e8bd7298802e29ed5d7cf19ce6677d012  analysis/e13_preds.jsonl
5b961f5c27a7b6bce9bd052ffaab8c8bca377519790fcf696b8ca2bbc8567ab9  analysis/e15_validation.json
027c897510605244899c271a7052c1f7e14f496f885a52ac8ca2843a0d62dd20  analysis/e15_preds.jsonl
0e560f5ae95a1c41e3170fca832e0515ef8c6bd3823c1a3b45693b118a34ae4e  analysis/e16_validation.json
ccd766f1d482d74028064fc1dace2079034ac28faaec5c6219a34d03d1738c77  analysis/e16_preds.jsonl
24da181906e149f781c8729e119e51cea69cfaefdc7deb3b2d0e69f62bb763f4  analysis/e11c_three_coder.json
cf836f4c928d6ab1568648aa446ae53fde519b165c25a528dfffc3161ae135d0  analysis/e11c_decomposition.json
6ba11dc8309f3d386e7bf0aea97214f79b3c606697db7ecb386b7c47c2b043a3  analysis/table1_coarse_by_food.json
fc66e45166a06a1f9c1af2e6fdc09daca23dd779618b1f8d0cba0646a5171ce7  table_S1_violation_by_food.md
95826e15013bb1c7b5e9f57890980a81935e480c8b8219b3d1cff32edc258f3f  scripts/e12_commodity_index.py
d10123d25099d714a3c4a79d52f8b818a93781add6f0c4b4a30a0306165ce900  scripts/e12_commodity_precision.py
03beae677afe33ec526dde44b94802bed8d53df72375a3d7e499c5f09bd8f474  scripts/e13_commodity_subject.py
d9f891f9d93984150f049447a0b703ff9f443e0585e79cc50c4f269500858983  scripts/e15_binary_format.py
a4d9e2262f9c020eb03e6da6f90dcf9f6ec278239f6a97e9d198dd4aa0e1938f  scripts/e16_extract_commodity.py
9f5432ccdcf3036cf577d8c8e3a5e17f9c830230820ddaac30482ad36afae5e3  analysis/e17_segmentation.json
bed9011849d2ffbe9bd24a773445cdd61194c4b1cc1671b1a7a718befd0cea26  scripts/e17_segmentation.py
e2ab8acf32ea2e886ec4d4a38ad752f9678dfade6665b22e18edf5d29ff9c96e  scripts/verify_numbers.py
e5ca89046c31bf5874d50d10c0c95ab2c7a61553130fddab55afc8126fe964ba  scripts/autopilot.sh
EOF
```

Four claims in the manuscript can be checked with nothing but these files:

1. **"every statistic carries product, denominator and timestamp"** — every number in
   the manuscript body either matches a `value` in `numbers.csv` or is structural, and
   every `numbers.csv` row names the product file, the JSON field, the product's
   `at_utc` and the product's sha256. The check is mechanical: every numeric token in
   the body is either licensed by a row or on the explicit structural list.
2. **"deviations were not selected after the fact"** — `DEVIATIONS.md` is append-only:
   where an entry was later found wrong it is corrected by a new `… 更正` entry that
   names the number it corrects, rather than by rewriting the original. Every attempt in
   Table 4 has a pre-registration entry that **precedes** its result entry, and the third
   registration (D-124) contains a cap that the paper then obeys.
3. **"the commodity table is measured, not asserted"** — Table 3's two precision columns
   are re-derivable from `analysis/e12_commodity_precision.json` by counting `verdict`
   over `items`: `(S+I+T)/n` and `S/n`, per category and overall.
4. **"three attempts failed one gate, and the best is not the one reported"** — Table 4's
   four statistics per attempt are recomputed from the `items` array of
   `analysis/e1{3,5,6}_*.json` by treating the human `verdict == "S"` as positive; the
   gate (`κ ≥ 0.60`, `BA ≥ 0.75`) is the one written in D-117 before the first call and
   repeated verbatim in D-121 and D-124. The attempts are reported in the order they were
   run, not by score.

## Register numbering: what is irregular and why

Entry numbers are **not** clean, and the irregularity is disclosed rather than hidden.
There are 137 `## D-` headings carrying 129 distinct numbers, so **eight numbers appear
twice**:

| number | why it repeats | status |
|---|---|---|
| D-84, D-86, D-88, D-89 | a later `… 更正` correction of that entry | intentional; the correction names the entry it corrects |
| D-90 | same, plus a second `D-90 更正` | intentional |
| D-101 | **genuine collision**: two different entries, the inter-coder agreement result and the note that its raw per-document coding files are not on disk | resolved by **D-104**; where the manuscript writes `D-101` unqualified it means the inter-coder agreement entry |
| D-108, D-109 | **second collision**, same cause: a third entry was appended using the heading count instead of the numeric maximum | resolved by **D-110** |

D-110 is the adjudication: it assigns canonical numbers by line, so that the entry at
line 2290 is **D-111** (the commodity lexicon and its rules, written before any count
was taken) and the entry at line 2307 is **D-112** (the numbering-discipline note, whose
own `D-108a`/`D-108b` labels it voids). **There is no heading literally reading
`## D-111` or `## D-112` on disk** — a reader searching for them finds D-110's table, and
`D-113`, `D-114` and `D-115` all cite D-111 by that number. This is also why the register
has 137 headings but only 129 distinct numbers with a maximum of 131: two numbers in the
range exist only as canonical labels. The cause is stated in D-110 and again here: a
heading count is not a number maximum, because correction headings repeat numbers. Every
entry from D-113 onward was therefore numbered from `max + 1`, computed by sorting the
numbers numerically rather than by counting headings.

## Things a reader should know before trusting any number here

- The corpus is a **sampling frame**, not a census: the source portal returns results
  sorted by publication date descending and serves at most four pages of fifty rows per
  query, so the year distribution is a property of the window (D-90). No trend claim is
  made anywhere in the paper.
- The deterministic layer's **negative control is 0.28 at fine and at coarse
  granularity alike** (14 of 50 documents). Every categorical distribution derived
  from it is therefore reported as **instrument output**, not as an estimate of the
  underlying conduct (D-92). This is the single most important caveat in the paper.
- **The commodity index is a presence test, not a classifier and not a prevalence
  estimate** (D-111, D-115). A hit means "this term occurs in this document", never
  "this case concerns this food". Measured on 270 adjudicated hits: any-mention
  precision **0.9296**, subject-matter precision **0.3852**. Two categories in the table
  (health food, foods for special dietary uses) are **statute-text dominated** — 4 of 15
  and 13 of 15 sampled hits occur only inside quoted provisions — so those rows should be
  read as a record of which decisions quote the statute, not of products. Condiments show
  the analogous ingredient-list effect (subject precision 0.1333). No recall is measured,
  so **no absence statement is supported**: a document with no match may still be about
  that food.
- **Recall is not estimable, and that is a result, not an omission.** Three constructs
  were registered in advance and run against the same gate; all three failed, with the
  best (E15) reaching κ 0.4885 and balanced accuracy 0.7390 against thresholds of 0.60
  and 0.75 (D-123, D-125). The gate was never moved. The comparison across constructs is
  the substantive part: converting the forced choice into per-category binaries raised
  sensitivity from 0.4423 to 0.6346 while specificity stayed near 0.85, and free-text
  extraction failed instead at the binding step (818 of 1,128 extracted names contain no
  lexicon term). **No share, coverage or "X% of cases about food C" statement may be
  derived from these files.** The manual fallback that D-121 and D-124 had held in
  reserve was cancelled by D-126 before any zero-hit document was read: a single reader
  on a task where three readers reached Fleiss' κ 0.0881 would produce a number whose
  error is unmeasured.
- The six-category typology **fails an inter-coder check**: three readers working from
  the same 80 documents produced **Fleiss' κ = 0.0881** and a minimum pairwise agreement
  of **0.1375** (B↔C), inside the negative region pre-registered in D-102. The three
  pairwise figures must be read together, because they are not homogeneous:

  | pair | agreement | Wilson 95% | Cohen's κ | of the agreements, both `OTHER` |
  |---|---|---|---|---|
  | A↔B | 13/80 = 0.1625 | [0.0975, 0.2584] | 0.0019 | 2 |
  | A↔C | 64/80 = 0.8000 | [0.6995, 0.8730] | 0.6371 | **42** |
  | B↔C | 11/80 = 0.1375 | [0.0785, 0.2297] | −0.0353 | 2 |

  Readers A and C both retreat to `OTHER` on the majority of documents (57.5% and
  61.25%), while B almost never does (3.75%); **42 of A↔C's 64 agreements are the pair
  jointly declining to classify**. Setting those aside, A↔C agree on 22 of 38 documents
  (0.5789). A temporary sentence in the pre-registration that would have reported all
  three readers as "at chance" was therefore **withdrawn after the data were in**, because
  it is false for the A↔C pair (D-106); so was any reading of A↔C's κ = 0.6371 as
  evidence that the typology is usable.
- The check licenses **no ranking** of human against instrument: agreement between A and B
  (0.1625) is lower than either reader's agreement with the instrument (0.5250 and
  0.3375), and the instrument-side attribution test is not satisfied. What survives is
  narrower and harder: the six-category label is **not jointly recoverable** by three
  readers working from the same codebook and the same documents. All three readers were
  administered through the same session channel (D-100): `n_coders = 3`, **not** three
  independent research teams.
- The register and the scripts' comments are in Chinese, as they were written during
  execution; the manuscript's English text states the same constraints.
