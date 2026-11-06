# For reviewers: five checks, five minutes

No installation beyond Python 3.10. Each command prints the value the manuscript reports; if
one does not, the defect is ours, not a difference of interpretation. Run the commands from the
repository root.

## 1. Do the shipped files match their manifest?

```sh
python tools/verify_bundle.py
```

Expected: `[bundle] 26 listed, 26 on disk`, `[sheet ] 588 data rows`, `0 missing`, then
`all checks passed`. This re-hashes every supplementary file, checks the sheet's row count
against the manifest, and confirms that every product path a `numbers.csv` row names resolves
inside the repository.

## 2. Are Table 3's two precision columns what is claimed?

```python
import json
d = json.load(open("supplementary/analysis/e12_commodity_precision.json", encoding="utf-8"))
v = [i["verdict"] for i in d["items"]]
print(len(v), sum(x == "S" for x in v) / len(v), sum(x != "F" for x in v) / len(v))
```

Expected: `270 0.3851851851851852 0.9296296296296296` — that is subject-matter precision
**0.3852** and any-mention precision **0.9296** over the 270 adjudicated hits. The verdicts are
`S` (subject), `I` (ingredient list), `T` (quoted statute), `F` (false match); every verdict in
the table is one line of this file, so the columns can be recomputed row by row rather than
taken on trust.

## 3. Did the three automated attempts really fail the same gate?

```python
import json
def load(name, sub=None):
    d = json.load(open(f"supplementary/analysis/{name}.json", encoding="utf-8"))
    return d[sub] if sub else d
for label, d in (("E13", load("e13_commodity_subject", "s1_validation")),
                 ("E15", load("e15_validation")),
                 ("E16", load("e16_validation"))):
    print(label, d["n_items"], d["kappa"], d["balanced_accuracy"],
          d["gate_kappa_min"], d["gate_ba_min"], d["gate_passed"])
```

Expected:

```
E13 270 0.3241 0.6519 0.6 0.75 False
E15 270 0.4885 0.739 0.6 0.75 False
E16 270 0.3888 0.6766 0.6 0.75 False
```

The thresholds live **inside** each product (`gate_kappa_min`, `gate_ba_min`), so the gate cannot
be quietly moved after the fact: the value stored with the result is the value that was applied.
The register entries D-117, D-121 and D-124 record the thresholds as written before the first
call.

## 4. Is the 586/896 denominator right?

```python
import json
d = json.load(open("supplementary/analysis/e16_denominator.json", encoding="utf-8"))
print(d["n_named"], d["n_declined"], d["n_unmapped_of_named"],
      round(d["share_unmapped_of_named"], 4), d["n_unmapped_of_named"] + d["n_declined"] == d["n_unmapped_all"])
```

Expected: `896 232 586 0.654 True`. The product recomputes the denominator from the frozen
per-document predictions (`analysis/e16_preds.jsonl`, sha `ccd766f1…`) with the rule stated in
the file: `phrase == 无` is a decline, and *unmapped* means the mapping assigned category 0.
In v3.0 of the manuscript the same 818 documents were divided by 1,128; the corrected
denominator divides the 586 named-but-unbound documents by the 896 the model actually named,
with the 232 declines reported separately.

## 5. Can any number in the manuscript be traced to a file?

```python
import csv
rows = list(csv.DictReader(open("numbers.csv", encoding="utf-8-sig")))
r = [x for x in rows if x["id"] == "e12.prec.subj"][0]
print(r)
```

Expected: one row naming `0.3852`, its product, the JSON path inside it, the product's UTC
timestamp and the product's sha256. Every numeric token in the manuscript either matches a row
of this sheet or is on the explicit structural list (section numbers, protocol constants,
calendar years).

## The full re-derivation

`supplementary/scripts/verify_numbers.py` resolves **every** row against the product it names.
It expects the products on a host at `/opt/foods`; against the frozen corpus release it
re-derives **534 of 584** rows of the v3.0 sheet, and against v3.1 **538 of 588**, with **0
mismatches** (the extra 4 rows point at `analysis/e16_denominator.json`, which ships here). The
remaining 50 rows are enumerated by class in `supplementary/MANIFEST.md`: 27 composite paths,
11 serialised tables, 10 deliberate arithmetic combinations, and 2 rows pointing at the
register itself, which is a text product and has no JSON path to resolve.

## Where to look when you disagree

`DEVIATIONS.md` is the right place to start. It is append-only, it records the design changes
that affected reported numbers, and it records the decisions that **stopped** analysis — for
example the cancellation of the manual commodity mapping before any zero-hit document was read
(D-126), and the rule that keeps the deterministic layer's output labelled as instrument output
rather than as prevalence (D-92). If a reviewer's objection is about what the record cannot
measure, the answer is more likely to be in the register than in the manuscript.
