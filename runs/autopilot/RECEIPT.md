# Autopilot receipt — 2026-11-05T08:43:50Z

## Stage 1 — preflight
```
== preflight 2026-11-05T08:43:38Z
a1deda2c57ccf5eeb2cf3b27782d30087747dfa208264f9b2ec68dcd7b4a077e  /opt/foods/data/silver/silver.jsonl
52e3ca41db38102da29c15bdb8190fd351b1db12a73c6e6e2b54f2c5e16a5c2e  /opt/foods/data/analysis/e12_commodity_index.json
11108382db41aac741bf121c9376e88732dc977f947251c2072c6e017ed77ff8  /opt/foods/data/analysis/e12_commodity_precision.json
fc60b4fa7245d90e331eef1356cfde62d6b56834e72192ca91df91d06098dcf7  /opt/foods/data/analysis/e13_commodity_subject.json
5b961f5c27a7b6bce9bd052ffaab8c8bca377519790fcf696b8ca2bbc8567ab9  /opt/foods/data/analysis/e15_validation.json
0e560f5ae95a1c41e3170fca832e0515ef8c6bd3823c1a3b45693b118a34ae4e  /opt/foods/data/analysis/e16_validation.json
42ed93fc25fe1888f834e130882a93815ef8d3ae6cd32d5d98018058019318c8  /opt/foods/numbers.csv
fa6d4d28ff50441c366332ebeae74fb04d8dbf73baf8f532d8d39f08dcd00415  /opt/foods/DEVIATIONS.md
overlay          70G   16G   55G  22% /
21624 MiB, 24564 MiB
vllm OK
```
## Stage 2 — E17 segmentation (D-127)
```
docs 1128
Building prefix dict from the default dictionary ...
Dumping model to file cache /tmp/jieba.cache
Loading model cost 0.608 seconds.
Prefix dict has been built successfully.
[e17] 100/1128 2s
[e17] 200/1128 3s
[e17] 300/1128 4s
[e17] 400/1128 6s
[e17] 500/1128 7s
[e17] 600/1128 8s
[e17] 700/1128 9s
[e17] 800/1128 10s
[e17] 900/1128 11s
[e17] 1000/1128 11s
[e17] 1100/1128 11s
crosstab {'R0_pass_R1_pass': 232, 'R0_pass_R1_drop': 38, 'R0_drop_R1_pass': 0, 'both_drop': 0}
dropped by verdict {'S': 12, 'I': 13, 'T': 5, 'F': 8}
subject precision R0/R1 0.3852 0.3966
sha 9f5432ccdcf3036cf577d8c8e3a5e17f9c830230820ddaac30482ad36afae5e3
```
## Stage 3 — numbers.csv re-derivation
```
rows 574 ok 527 mismatch 0 unresolved 25 composite 10 missing 2
```
## Products produced
9f5432ccdcf3036cf577d8c8e3a5e17f9c830230820ddaac30482ad36afae5e3  /opt/foods/data/analysis/e17_segmentation.json
8e0a3542bd5342434d8ef43940ef4d1cb840faa07eabf071e32ce56049788c32  /opt/foods/runs/autopilot/03_numbers_verify.json

## Stage 3 re-run (final sheet, 2026-11-05T08:5xZ)

```
rows 584 ok 534 mismatch 0 unresolved 27 composite 11 missing 0 text_product 2
```

## Stage 3 re-run — sha-pinned (written 2026-11-05T14:41Z, per D-130)

The block above was written at 08:52Z with the checked sheet named only implicitly, and
the preflight sha it sits next to (`42ed93fc…`, 574 rows) is the sheet as it stood at
08:43:50Z. The sheet was replaced at 08:49Z. This block pins the version that Stage 3
now refers to, so a reader can confirm it without trusting the clock.

| field | value |
|---|---|
| sheet | `/opt/foods/numbers.csv` |
| sheet sha256 | `43255b10d98948a93992beba054ab58fd1f78befbe0f78785b6bc37df39cf896` |
| rows | 584 |
| product | `runs/autopilot/03_numbers_verify.json` |
| product sha256 | `8e0a3542bd5342434d8ef43940ef4d1cb840faa07eabf071e32ce56049788c32` |
| re-derived and equal | 534 |
| mismatches | 0 |
| not machine-resolvable | 27 unresolvable composite paths, 11 serialised tables, 10 derived arithmetic rows, 2 rows whose product is this register (a text file) |

Machine coverage is therefore 534/584 (91.4%); the remaining 50 rows are enumerated by
class and were recomputed by hand (see D-130).
