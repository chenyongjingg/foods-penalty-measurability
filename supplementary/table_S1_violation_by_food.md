# Supplementary Table S1 — coarse violation category × food category

Companion to Section 3.5 of the manuscript. This is the deterministic layer's joint
distribution over the 875 Chinese documents: the coarse violation category (columns)
against its 15-category food vocabulary plus an unmatched bucket (rows).

**Read this table as instrument output, not as a population estimate.** The layer's
negative control is 14 of 50 documents at fine and at coarse granularity alike
(D-92), and the six-category typology behind the columns is not jointly recoverable
by three human readers (Fleiss' κ 0.0881, D-102/D-106). Row order is the instrument's
own emission order and has **not** been sorted: D-115 forbids ranking this table.

| Food category (deterministic layer) | n | DATA_FALSIFICATION | MARKET_ORDER | UNLICENSED | PROCEDURAL | UNDETERMINED |
|---|---:|---:|---:|---:|---:|---:|
| UNMATCHED | 272 | 108 | 48 | 7 | 19 | 90 |
| FOOD_ADDITIVE | 85 | 57 | 0 | 2 | 8 | 18 |
| PREPACKAGED_FOOD | 74 | 46 | 4 | 2 | 7 | 15 |
| MEAT_PRODUCT | 66 | 41 | 2 | 2 | 5 | 16 |
| ALCOHOL | 63 | 9 | 24 | 1 | 7 | 22 |
| GRAIN_BAKERY | 61 | 38 | 3 | 2 | 0 | 18 |
| CONDIMENT | 44 | 19 | 5 | 0 | 3 | 17 |
| EDIBLE_AGRICULTURAL | 42 | 21 | 4 | 1 | 5 | 11 |
| BEVERAGE | 36 | 15 | 1 | 3 | 2 | 15 |
| DAIRY | 28 | 13 | 3 | 1 | 4 | 7 |
| OIL | 28 | 17 | 0 | 2 | 1 | 8 |
| HEALTH_FOOD | 22 | 5 | 3 | 0 | 0 | 14 |
| FROZEN | 18 | 9 | 0 | 1 | 1 | 7 |
| CATERING_RAW_MATERIAL | 17 | 5 | 2 | 2 | 3 | 5 |
| TEA | 12 | 5 | 0 | 0 | 1 | 6 |
| INFANT_FOOD | 7 | 4 | 1 | 0 | 0 | 2 |
| **All rows** | **875** | **412** | **100** | **26** | **66** | **271** |

Of the 875 documents, 603 (0.6891) matched at least
one of the 15 food categories; the rest fall in `UNMATCHED`.

*Source: `analysis/table1_coarse_by_food.json` (at 2026-11-05T04:22:13Z, sha256 `6ba11dc8309f3d386e7bf0aea97214f79b3c606697db7ecb386b7c47c2b043a3`).
Each cell is copied from that product's `rows[]`; row totals and column totals are
the product's own fields, not recomputed here.*
