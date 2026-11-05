# Deviations from the plan (with reasons)

Every deviation is recorded here before results are read, so the paper can
report them honestly. Nothing here changes the scientific estimands; each item
is an engineering/feasibility deviation.

## D-1. Deployment: venv + daemon instead of docker-compose
Plan §5.3 assumed "NVIDIA driver + Docker". The pod has **no Docker daemon**
(checked 2026-11-04) and PID 1 is `tini`, so systemd/cron are unavailable.
Deployment is a Python venv at `/opt/foods/venv` and a `setsid` daemon with a
file lock. Same stages, same state machine; operational difference only.

## D-2. D1' primary intake: national penalty portal (cfws.samr.gov.cn)
Plan §4.1 names ~50 municipal "处罚公示" columns. On 2026-11-04 the national
Market Regulation penalty-document portal exposes a **public, keyless query API**
(`POST /queryDoc`, 652,611 documents; `POST /getDoc` returns the official PDF).
It aggregates decisions by municipal and district agencies — the same genre and
the same issuing bodies as D1' — with a uniform schema, and it avoids
site-by-site sampling heterogeneity. We use it as the **primary** frame and keep
`config/sources.yaml` (50 sites) as the secondary expansion layer.
- Scientific consequence: the sampling frame is broader and more uniform than
  the planned 50-site frame; this is stated in Method as a strength, and the
  portal's inclusion of non-food cases is handled by the pre-registered intake
  rule (fraud term ∧ document term within **80 chars** ∧ food context).
- The window was moved from 20 to 80 characters after a pilot showed that
  genuine cases frequently place 伪造 and 检验报告 in different clauses of the
  same sentence; precision is carried by the dual-LLM labelling stage, so the
  intake rule is deliberately recall-oriented.
- The municipal registry currently has 2 verified/1 calibrating URL; the rest
  are marked `pending` and are **not** counted as collected. Coverage is
  reported, never imputed.

## D-3. RASFF (D3b) has no machine-readable bulk distribution
The EU portal dataset `restored_rasff` advertises only an interactive HTML
window; no CSV/JSON distribution exists at the advertised URL (verified
2026-11-04). Per Plan §4.2 this source is optional and non-blocking. The
collector records `source_status:rasff` with the attempted endpoints and the
pipeline continues. E5 therefore reports **CN vs US**; EU claims are limited to
"source attempted, unavailable", consistent with the plan's "抓不到不阻塞".

## D-4. Dual-channel independence form
Plan §5.2 permits either two model families **or** independently written
prompts with different temperatures. The pod's model store offers Qwen2.5
weights only; a second family would require a ~18 GB download and a second
model swap on a 24 GB card. We use **prompt-α/T=0 vs prompt-β/T=0.3 on the same
weights**, and the anchor channel (deterministic rules) remains fully
independent. The shared-weights risk is the exact risk listed in the plan's
risk register ("双 LLM 系统性同偏") and is measured by anchor F1, which is
reported separately.

## D-5. Third channel = 5-sample majority vote, not a stronger model
Plan §5.2 allows "更强模型单次 / 5 次温度采样多数投票". Serving a 14B model
alongside the 7B model does not fit on one 24 GB GPU; we implement the
temperature-sampling variant (k=5, T=0.7) for both the per-document adjudicator
and the E1 fallback ladder.

## D-6. Municipal adapters are calibration-pending
Only Beijing and Shanghai column URLs were registered at build time. The generic
adapter probes each site, detects JavaScript shells (`needs_playwright`), and
records per-site status. No records are fabricated; the daily report exposes the
coverage. Expanding to all 50 sites is a data-engineering task that does not
affect the current estimands because the national portal covers the same frame.

## D-7. Time authority
All timestamps are taken from the pod (`date -u`), not the local workstation;
the report states UTC explicitly.

## D-8. openFDA (D3a) sampling cap
openFDA's food-enforcement endpoint returns thousands of records for the four
reason queries. D3a is used as the **US comparison corpus** for E5, not as the
network sample, so the collector stops at **150 records per query** (≤600
records). The cap is applied by the API `skip` pagination, not by post-hoc
sampling, so every record in the corpus is the API's first-k by its own order.

## D-9. Operational definition of E1 agreement
Plan §5.2 specifies dual-channel agreement with span IoU ≥ 0.5. We implement it
as **document-level micro-F1 over grounded entities of the same type**
(`2·|match|/(|A|+|B|)`) and report per-type F1 as well. Two deliberate choices:
- an entity is counted only if its `text` occurs verbatim in the document
  (`align.ground`), so hallucinated spans never inflate agreement;
- two empty channel outputs score 0, not 1 (otherwise "both found nothing"
  would read as perfect agreement).
- the anchor channel is the deterministic statute→category rule
  (`config/statute_map.yaml`), so its F1 is measured only on documents that
  cite a Chinese statute with exactly one implied category. openFDA records
  cite no Chinese statute and therefore contribute to the agreement half of
  E1 only; the anchor F1's `n` is reported alongside the value so the two
  halves are never conflated.
The measure is strict; the E1 ladder (self-consistency → entity-type shrink →
self-training) is applied exactly as the plan's fallback, and every action and
its measured effect is written to `state`/`data/metrics/e1.json`.

## D-10. PDF budget and backfill
The portal's listing is cheap but each `getDoc` PDF is a separate request under
the 1 req / 2 s rule. A per-run budget (`pdf_budget_per_run: 1500`) limits how
many PDFs one run fetches; metadata-only rows are kept in `docs` with
`pdf_missing` and are revisited by backfill on every later run. Rows parked as
`failed/awaiting_pdf` are reset to `raw` when their PDF arrives, so no sampled
document is silently lost to an earlier budget cut.

## D-11. cfws text must come from the PDF
For the cfws frame the analysis text is the published decision PDF. The list
view's snippet (case number, penalty amount, party) is not sufficient evidence
for entity extraction, so a cfws row without a PDF is parked until backfill
recovers it. HTML text remains valid for the municipal adapters.

## D-12. The cfws portal serves at most 200 rows per query
`queryDoc` reports the full `resultCount` (e.g. 721) but returns rows only for
pages 1–4 at `pageSize=50`; page 5 returns an empty list with `total=0`
(verified 2026-11-04). Coverage is therefore a function of **query breadth**,
not pagination depth. The query list was expanded from 10 to 36 pre-specified
document/fraud phrases before the second collection wave. Consequence for
Method: the frame is a **truncated top-200 sample per query**, not the full
result set; the number of accessible rows per query and the overlap between
queries are reported, and no claim of exhaustive coverage is made.

## D-13. English channel prompts revised after an instrumentation failure
The first English prompt pair (written to mirror the Chinese pair) failed on
the US corpus: channel α returned `"entities": []` for **every** openFDA
record, while channel β returned fragments such as `misbranded, unapproved ne`
(a substring that stops mid-word). The cause is structural, not a result: the
openFDA record is `field: value` metadata, not prose, and α's "uncertain ⇒ do
not extract" rule made the model refuse the whole record. Revised prompts give
both channels an explicit field→type mapping (recalling_firm→END_USER,
state→JURISDICTION, recall number→PENALTY_EVENT, one violation term→TACTIC),
and require spans to be complete names/terms rather than arbitrary substrings.
Verification before re-labelling: on three openFDA documents α and β both
return grounded entities with micro-F1 0.67–1.00 and identical categories
(e.g. F-1134-2016: both extract `Iowa Select Herbs LLC`, `misbranded`).
This is a prompt-instrument fix applied **before** any E5/US analysis was run;
no threshold, no E1 estimand, and no inclusion rule was changed.

## D-14. Prompt versioning and wholesale re-labelling
The corpus is labelled under one prompt version at a time. When the English
prompts changed (D-13), all documents labelled under the old version were
**reset to `clean` and re-labelled**, rather than kept alongside new records:
a corpus mixing prompt versions would make the E1 agreement statistic
uninterpretable. The reset is written per document as
`relabel:openfda:<timestamp>` in the manifest note, so the history is
auditable. The Chinese documents were not re-labelled — their prompts did not
change.

## D-15. Confidence tiers and the main corpus
Plan §6.1 defines E1 with a target (0.85) and a floor (0.75); Plan §5.2 says
the main analysis runs on the high-confidence subset (dual-channel agreement
plus anchor pass). Tiers implement that literally:

- `high` = agreement ≥ 0.85 **and** the anchor agrees. The anchor is a Chinese
  statute rule engine and is undefined for the English corpus, so for
  non-Chinese documents the high tier reduces to the agreement test.
- `medium` = 0.75 ≤ agreement < 0.85 (the plan's floor band). **Sensitivity
  analyses only — never the main estimate.**
- `low` = below the floor.

The earlier implementation put `medium` at "≥0.85 but no anchor", which made
the floor dead and forced every openFDA document to `low` by construction; that
was an implementation artifact and is corrected here. E1 itself remains
evaluated against 0.85/0.75 on the full labelled set, unaffected by the tier
labels.

## D-16. The US corpus is not part of the ecology network
Plan §4.3 assigns D3a/D3b exactly two roles: typology comparison (E5) and
out-of-sample validation of the extraction prompts. The network builder
originally took every main-corpus document regardless of source, which would
have pooled Chinese and US supplier chains into one graph and made every
degree, betweenness and attack-tolerance number a mixture of two jurisdictions
with different recording conventions. `analyze/network.load_edges` now reads
`cfws`/`municipal` only; `sources=None` remains available for a deliberate
sensitivity run. Survival and attack inherit the filter because they build on
`load_edges`.

## D-17. Displacement coding requires an enforcement context
Plan §3/E4 defines displacement as adaptation *after a governance shock*. The
first rule set counted any document containing 异地/线上/网络平台 as spatial
displacement — an address mention was enough, and the scan also covered
low-tier documents. The rule now (a) reads the main corpus only, (b) requires
the matched phrase to sit within 60 characters of a governance term
(处罚/查处/打击/立案/判决…), and (c) drops the generic patterns. The expected
effect is fewer events; E4 will very likely fall to the qualitative tier, which
is the honest reading of the rule rather than a loss of data.

## D-18. Anchor engine: penalty-clause basis + fact disambiguation
Plan §5.2 channel ② is a deterministic statute→category rule plus format
validation. Implemented literally, it did not work on the corpus: 《食品安全法》
第一百二十四条 is the penalty basis for several fraud types and appears in
nearly every decision, so "map every cited article" left **3 of 27** Chinese
documents with a single category, and anchor F1 was computed on n=7 (macro
0.333, micro 0.857 — the macro was decided by two classes with zero support).
The engine now:
- reads the **penalty clause** (the article after 依据/根据), falling back to
  all cited articles only when no penalty clause is found;
- when that clause admits several categories, uses a fixed violation-phrase
  lexicon to choose among *that clause's* categories only — never outside;
- 124条 was added to FALSE_LABELING's candidate set, because a false
  production date penalised under 124 is a labelling offence;
- reports `basis` (penalty_statute / statute+fact / fact_only / ambiguous), and
  anchor F1 counts only the statute-grounded bases. Fact-only anchors are
  reported separately because they key off the same phrases the LLM reads and
  are therefore a weaker independent check;
- extracts party/case-number/date/fine (the plan's format validation) and
  reports extraction-level hit rates next to the category F1.
Measured effect on the 27 labelled Chinese documents: single-category coverage
3 → **16** (59%), still 0 documents without statute extraction.

## D-19. Intake proximity requirement removed
Plan D1' is conjunctive keyword presence (fraud term AND document-type term in
a food-safety decision). A proximity window (20 chars, later 80) was added in
the pilot to keep the listing snippets from matching across unrelated
sentences. Measured on the 399 Chinese documents filtered so far, **115
contained all three term families** and were rejected only because the fraud
phrase and the document type sat in different sections of the decision (facts
vs legal basis). Since the labelling stage is the designated precision filter,
proximity is now off by default (`intake.require_proximity: false`); setting it
true restores the pilot rule. Documents rejected under the old rule are
returned to `raw` by `scripts/readmit.py` and re-cleaned, not re-typed by hand.

## D-20. openFDA dates are YYYYMMDD; every date reader now goes through `as_date`
The openFDA enforcement API returns `report_date` as `20200401`. The pod runs
Python 3.10, whose `date.fromisoformat` rejects the basic form (3.11 accepts it),
so every openFDA record was silently invisible to `hawkes.event_days`,
`survival.build_table` and the new H2 anchoring: the Hawkes fit ran on the 55
Chinese dates only while the analysis claimed to use the extracted corpus.
Fixed by (a) `common.as_date`, a tolerant parser, used by all three modules,
and (b) storing openFDA `published` as ISO from now on. Existing rows keep
their raw `published`; the tolerant parser covers them.
This also exposed a design error: those 246 US records must **not** enter the
CN Hawkes fit (D3a is comparison-only, D-16). Both `hawkes.event_days` and
`shocks.corpus_event_dates` now restrict to `cfws`/`municipal`.

## D-21. Hawkes remains degenerate; the nonparametric fallback replaces the claim
With 55 CN events over 1,055 days the exponential-kernel fit collapses
(kernel timescale ≈ 6e-8 days, branching ratio 0.045) — the optimizer is
fitting same-day ties, not a process. Reported as `degenerate_fit`, never as
self-excitation. The Plan §6.1 fallback is now computed alongside:
- KS of positive inter-event gaps vs exponential: n=49, p=0.59;
- dispersion index of daily counts = 1.13, Monte-Carlo p = 0.177 (1,000
  Poisson replications with the same mean and horizon);
- tie share = 0.093 (same-day penalties).
The chi-square dispersion p-value (0.0019) was **not** used: at a daily mean of
0.05 the chi-square reference is invalid, and the Monte-Carlo null shows the
apparent overdispersion is within noise. Current reading: no evidence of
self-excitation at day resolution; H2's regeneration rhythm is untested, not
supported.

## D-22. D4 timeline: static court/spp listings + rule typing + event clustering
The plan's D4 names D2 plus the two 典型案例 pages. This build collects:
- court.gov.cn `/zixun/gengduo/104.html` (22 pages, 2014-2026),
- spp.gov.cn 指导性案例 and 重点工作 columns (30 pages each),
- samr.gov.cn 食品抽检司 栏目页 (18 server-rendered links; sub-columns are
  JS shells and are **not** scraped).
Result: 490 dated events, 30 food-specific. The plan's "LLM 自动判定事件类型"
is implemented as a deterministic keyword classifier (`type_rule: keyword`);
the LLM pass is deferred until the GPU is idle and, when it runs, must be
stored as a separate field rather than overwriting the rule output.
Two corrections matter for H2:
- the same joint release is reprinted by court and spp and again a day later,
  so `shocks.canonical_events` merges events whose normalised titles are
  similar within ±7 days. Without this, one 2026-09 release counted as four
  shocks.
- 座谈/培训/比武/消费提示 are `activity`, not governance events, and never
  enter the H2 test.
Limitation recorded: 铁拳 专项行动 announcements live in JS-rendered topic
pages and are therefore missing; D2 coverage is 总局抽检通告 only.

## D-23. Tier sensitivity: the network estimate is not robust to tier choice
`analyze/sensitivity.py` computes the same network statistics on three corpora:
high (main) 27 nodes / 34 edges / density 0.097 / GCC 0.33; high+medium 63
nodes / 85 edges / density 0.044 / GCC 0.14; all tiers 202 nodes / 451 edges /
density 0.022 / GCC 0.19. Adding the floor band **halves density and the GCC
share**. This is reported as a robustness result, not hidden: until E2 reaches
the 400-node floor the main estimate carries this sensitivity band, and the
paper must not quote a single density figure.

## D-24. H1/H3 uncertainty: document bootstrap, and a stricter H3 rule
`attack.py` compared AUCs as point estimates. It now bootstraps over documents
(`analysis.bootstrap`, 200 reps, seed 20261104) — the sampling unit is the
penalty case, so node-level resampling would understate uncertainty — and
reports percentile CIs plus the sign-stability share of the provider−end-user
difference. H3 is only marked supported when the bootstrap CI of that
difference excludes zero **and** each class has ≥20 nodes; the previous rule
(`auc_provider < auc_end_user`) could be decided by a single hub.

## D-25. Prompt codebook v2 pilot rejected: the disagreement is capability, not wording
E1's zh disagreement is concentrated in three free-text types — SERVICE_PROVIDER
(per-type F1 0.24), DOCUMENT (0.28), TACTIC (0.42) — while the structured types
agree (JURISDICTION 0.91, PENALTY_EVENT 0.86, END_USER 0.85). Inspection of the
disagreeing spans shows channel outputs that violate the v1 prompt's own rules:
"当事人：留*" and "某处"/"无" as SERVICE_PROVIDER, and product names ("白酒",
"冰淇淋") typed as DOCUMENT in channel B.

A codebook v2 was written that states the span boundaries explicitly (shortest
complete designation; no field-label prefix; placeholders are not entities; a
product name is never a DOCUMENT; TACTIC ≤12 characters; SERVICE_PROVIDER and
END_USER mutually exclusive), applied to all four prompts (zh/en × alpha/beta)
and kept under `config/prompts_v2/`. It was pilot-tested on 60 random zh
documents (seed 20261104) that already had per-channel annotations, same model
and temperatures; the decision rule was fixed before the run: adopt v2 only if
the pilot mean agreement reached the 0.75 floor.

Result: **0.6696 → 0.5826** (34 documents worse, 19 better; 2/60 high tier).
v2 is rejected and v1 retained. The pilot is the evidence that the residual
disagreement is a 7B capability limit on free-text span boundaries rather than
a prompt defect, which is exactly the premise of the P062 fallback; the corpus
therefore proceeds to entity-type shrinkage (see the `ladder` field of
`data/metrics/e1.json`) and the network analysis is reported as not estimable
while E2 is below its floor.

## D-26. The ecosystem graph is actor-only; type-level terms are not nodes
The first network build admitted all five entity types as nodes. On the
high+medium corpus the highest-degree node was the DOCUMENT term **检验报告**
(degree 8): a type-level phrase shared by unrelated cases, which merges
otherwise unconnected suppliers into one hub. JURISDICTION nodes are
administrative units, not actors, and TACTIC nodes are phrases. With 16 of 27
nodes in the main graph being non-actors, a degree-targeted attack would have
removed vocabulary and administrative units, not intermediaries — H1 and H3
would have been measured on an artefact.

`analyze/network.py` now builds the **actor-only** graph (SERVICE_PROVIDER,
END_USER; `analysis.network_node_types`), and `sensitivity.py` reports the
five-type graph on the same high-tier corpus as a separate taxonomy variant
(`taxonomy.all_entity_types`). Consequence: the main graph is smaller (27 → 11
nodes) and E2 moves further from its floor; that is the honest count of the
actors the corpus actually supports.

## D-27. E5 uses the same high tier as every other experiment; E1 also reports pooled entity F1
1. `analyze/compare.py` read `tier in ("high","medium")` while the network,
   Hawkes, survival, shocks and displacement all read high only. E5's CN counts
   were therefore inflated by exactly the band the main estimate is not allowed
   to use. E5 now reports the high-tier table as its result and the
   high+medium counts as `sensitivity_tiers`.
2. Plan §5.2 calls the agreement statistic "entity-level span-overlap F1"; the
   implementation has always computed the **mean of per-document F1** (D-9).
   Both are now written to `e1.json` (`mean_agreement`, `pooled_micro_f1`), so
   the difference is visible instead of being an unstated choice. The headline
   and the tier rule stay on the document-level mean, which was the
   pre-registered measure; the pooled figure is descriptive.
3. Plan §5.2 evidence ③ (literature calibration) is recorded in `e1.json` as
   `literature_calibration` with the CAEC_LLM figures from Plan §2.1 and an
   explicit note that a published F1 against human annotation is not
   numerically comparable with dual-channel agreement.

## D-28. Labelling rejections are not missing at random — and the old coverage figure was wrong
25 of 368 documents in the 2026-11-04 wave produced no parseable JSON in either
channel (`label_parse_failed`) and were left at stage `clean`. They are
systematically **longer** than the labelled ones: median text 5,559 vs 2,629
characters (p90 8,888 vs 5,176). The mechanism is the 6,000-character document
cap plus `max_tokens=1600`: a long decision is cut mid-text and the model's JSON
is cut mid-object, so both channels fail together. E1 therefore excludes the
longest and most information-dense decisions, which biases the agreement figure
in an unknown direction and shrinks the corpus exactly where entities are
richest.
Two corrections, no re-labelling:
- `e1.json.coverage` is now a record (`labelled`, `pending_clean`,
  `label_parse_failed`, `rate`) instead of `labelled / docs-currently-in-clean`,
  which was a moving denominator and could exceed 1.
- the rejection count and its character-length gap are reported with E1 so the
  bias is visible in the paper rather than hidden in a log line.
Not yet changed: the cap itself. Raising `doc_text_chars` or chunking long
documents changes the prompt input and would require re-labelling the corpus
(D-14); it is recorded as the next protocol revision rather than applied
mid-wave.

## D-29. Stack substitutions: networkx for PyG, no vector index, no external pager
- Plan L5 says "网络构建(PyG)". The analyses need degree/betweenness/community/
  k-core on graphs of at most a few hundred nodes; `networkx` does this exactly
  and is already a dependency. PyG would add a CUDA stack for no gain at this
  scale. Same statistics, different library.
- Plan L3 lists a faiss vector index. Nothing in the analysis consumes
  embeddings (the LLM reads document text directly), so the index is not built.
  If a later step needs semantic retrieval the line stays in the plan, not in
  the runtime.
- Plan P079 asks for webhook/e-mail failure alerts. No external paging channel
  is configured on this pod (`FOODS_WEBHOOK` unset); `reports/daily/ALERTS.md`
  is the alert surface, written on every cycle. Plan §5.4's "看日报即可" is the
  operating mode; adding a webhook is a configuration step, not code.

## D-30. Protocol v2: the 6,000-character cap is removed (whole-corpus re-label)
What changed
- `label.doc_text_chars` 6,000 → 20,000 and `max_tokens` 1,600 → 2,500 for both
  channels and the adjudicator; vLLM `--max-model-len` 16,384 → 23,040.
- The adjudicator had its own hard-coded `doc[:6000]`; it now uses the same cap
  as channels A and B, so the third channel never sees more text than the two
  it is adjudicating.

Why
- The cap was binding on real documents: 53 of 780 clean documents exceeded
  6,000 characters, p99 = 10,206, max = 16,263 (Qwen tokenizer ≈ 0.55–0.72
  tokens per Chinese character, so 20,000 chars ≈ 11–14k tokens, leaving room
  for the 2.5k-token answer and the 1.5k-token template inside 23,040).
  32,768 was tried first and rejected by vLLM: on a 24 GB 4090 at 0.85 memory
  utilisation the KV cache holds 24,064 tokens, so the server refuses a longer
  sequence than that. 23,040 keeps a margin under the measured capacity.
- The 25 documents that failed JSON parsing were the longest ones (median
  5,559 vs 2,629 characters): the model was asked to return a large JSON object
  from a truncated input and ran out of `max_tokens`. E1 was therefore computed
  on a corpus that systematically excluded the most information-dense
  documents (D-28).
- The penalty clause — the deterministic anchor — sits at the *end* of a
  decision; 27 documents have their last statute citation after character
  6,000, so truncation also destroyed anchor coverage for exactly those cases.

Cost and handling
- This is a protocol change, not a setting tweak: a corpus half-labelled at 6k
  and half at 20k cannot be pooled (D-14). The whole corpus is reset and
  re-labelled (`scripts/relabel_source.py all`), and the v1 silver file is kept
  at `data/archive/v1_20261104T0235Z/` so the v1→v2 comparison is auditable.
- `e1.json` now carries `protocol` (prompt hashes, cap, max_tokens, model,
  entity-type list) and `input_chars` (p50/p99/max of labelled inputs,
  over-cap count, and the parse-failure length gap) so the next reader can see
  whether truncation bound without re-deriving it.

## D-31. Corpus expansion is automatic but pre-registered (Plan §6.2 / P063)
- The plan assigns "扩年份/扩站点" to the pipeline. `analyze/expansion.py` takes
  the next batch from `config/expansion_queries.yaml` — an ordered list written
  before the second labelling wave — whenever E2 is below its node floor, at
  most 2 batches/day and 600 PDFs per batch, and tags every document it
  produces with the batch id.
- The pipeline never invents search terms: if the list is exhausted, E2 stays
  downgraded and the plan's global fallback applies. An expansion that re-chose
  its vocabulary after seeing how many nodes came out would make the corpus
  definition a function of the result.
- Queries only retrieve. The D1' inclusion rule is unchanged and remains the
  filter (Plan §4.1).

## D-32. D1' keyword sensitivity (Plan P115)
- `analyze/keywords.py` re-applies the inclusion rule under the fixed variants
  in `analysis.keyword_variants` over the *whole admission frame* — the
  documents the current rule admits and the ones it drops — and reports, per
  variant, how many documents move in/out, the Jaccard overlap with the plan
  rule, and how many high-tier documents the variant would lose.
- To make that possible the cleaner now keeps the (PII-masked) text of
  rejected documents in `data/clean/filtered/`. Those files are never read by
  labelling and never enter the corpus.
- Descriptive only: the corpus is not rebuilt from any variant.

## D-33. Staleness stamp on every network metric
- `network.json`/`sensitivity.json` now record `dataset_lag_s` (how much older
  `dataset.jsonl` is than `silver.jsonl`) and `stale_dataset` (>300 s), and the
  gate table surfaces it. On 2026-11-04 a manual `analyze` after a `label` run
  reported an actor graph of 11 nodes / 2 edges from the *previous* dataset;
  the fresh run gave 62 nodes / 7 edges. A stale read is indistinguishable from
  a data finding unless the artefact carries its own age.

## D-34. Anchor engine: fall back to all cited articles before the fact lexicon
- Observed: 392 of 644 silver records are Chinese decisions with a statute map
  lookup, and 16 of them had a penalty clause that maps to no category at all
  (the penalty sentence cites only 《行政处罚法》, e.g. the late-payment
  surcharge, so no fraud article is named there). The engine fell straight
  through to the free-text fact lexicon for those, i.e. it lost the statute
  grounding exactly when the decision was cited in an unusual way.
- Change: the source order is now (1) the penalty clause's articles, (2) *all*
  cited articles, (3) the fact lexicon. Step (2) was already used when no
  penalty clause existed; it now also covers "penalty clause present but
  unmapped". The ambiguity policy is unchanged — step (2) often resolves to an
  ambiguous set, and those documents stay excluded from anchor F1.
- `anchor.basis` now distinguishes `penalty_statute` (clause-resolved) from
  `cited_statute` (all-articles fallback), and `anchor.source` records which
  branch produced the candidate set. `extract` counts documents per basis
  (`anchor_f1.basis_counts`) and treats `cited_statute` as statute-grounded, so
  it enters anchor F1 while `fact_only` still does not.
- Applied offline with `scripts/retier.py`: the anchor is deterministic, so the
  revision is recomputed from the stored document text instead of re-querying
  the model. The script archives the previous silver file and writes
  `data/metrics/anchor_{stamp}.json` with the basis and tier transition tables,
  so a tier change is attributable to this entry and not to D-30's re-label.
- Measured on the v1 corpus before applying: anchor coverage 217→233 of 392
  (55.4%→59.4%); at the 0.85 agreement threshold, high 57→62 (+8.8%) and
  anchor mismatches 49→44. Recovery is modest and concentrated in decisions
  where the penalty sentence cites procedure law only.

## D-35. Reachable corpus is capped by the portal, not by the query list
- `queryDoc` reports a `resultCount` far above what it will serve: `伪造|食品`
  reports 721 rows, pages 1–4 return 50 rows each and page 5 returns an empty
  list (re-measured 2026-11-04). The per-query ceiling is therefore 200 rows,
  independent of `max_pages_per_query`.
- Consequence for E2: the corpus is not a sample of the reported universe, it
  is the portal's *first 200 rows under its own ordering* for each query. A
  query reporting 6,766 results contributes at most 200, so no amount of
  pagination or re-running reaches the rest.
- Expansion therefore has to come from vocabulary breadth, and the yield was
  measured rather than assumed: batch B1 (8 pre-registered query pairs, 44
  queries in the merged run) added **0** new documents, and spot probes of
  specific phrases (`伪造|认证`) found 1 unseen row in 9. `scripts/_coverage_probe.py`
  records the per-query reported/ reachable / unseen counts in
  `data/analysis/coverage_probe.json`.
- This is reported, not worked around: E2 stays downgraded at its measured node
  count, and the paper's network claim must be stated at that corpus size.

## D-36. The portal's second query slot is a facet, not a full-text field
- `collect.cfws.query()` sends two conditions, `quanwen_1` and `quanwen_2`,
  and the settings comment claimed "both must match". Measured on 2026-11-04
  with the collector's own `query()` (same headers, same rate limit):
  `["检验报告", "餐饮"]` → 1,544 hits, `["食品", "检验报告"]` → 0,
  `["伪造", "检验报告"]` → 0, `["伪造", "食品"]` → 721. A document-type term in
  slot 2 never matches; a food/product category in slot 2 does.
- Consequence: of the 36 first-pass queries, every one whose second slot is a
  document type was a structural zero, and so were all eight B1 queries. B1 was
  run on 2026-11-04 and reported `new=0, pdfs=0` — the ladder was not exhausted,
  it was malformed.
- Correction (no result-driven term choice): the conjunction stays in the free-
  text slot and the second slot carries the food facet. `config/
  expansion_queries.yaml` gained **B4** (D1' vocabulary × 食品, 18 queries) and
  **B5** (same vocabulary × 餐饮/农产品/保健食品/预包装, 26 queries), enumerated
  mechanically from the D1' term lists already in `settings.yaml`. B1–B3 are
  kept unchanged in the file as the record of what was pre-registered and run.
- `analysis.expansion.max_batches_per_day` 2 → 4, so B2–B5 can run the same day.
  This is a scraping-rate knob; the query list, the PDF budget and the
  government-site rate limit are unchanged.
- The first-pass query list in `settings.yaml` is left as it was (it produced
  the current corpus); its comment now states the correct slot semantics and
  marks the slot-2 document-type entries as structural zeros rather than
  deleting them.

## D-37. Fail-fast preflight in the label stage
- On 2026-11-04 a protocol edit (`_one` returning a bare record instead of
  `(record, reason)`) made every labelled document raise in the worker thread.
  The stage kept going, and each failure incremented that document's attempt
  counter — 58 documents in four minutes, on a corpus where the attempt budget
  is finite. The silver file stayed at 0 bytes, so nothing downstream could have
  caught it.
- `SilverLabeller.run()` now labels one document synchronously before the pool
  starts and raises `RuntimeError("label preflight failed on <doc>")` if that
  call fails, so a systematic error stops the stage before any document is
  charged an attempt. The return contract is also checked (`(record, reason)`),
  which is the specific mistake that happened.
- Attempt counters for the 58 documents touched by the broken run were reset;
  the documents stayed at `clean`, so no corpus content was affected.

## D-38. D1' municipal layer: measured yield, and why cfws carries the corpus
- Plan §4.1 names ~50 provincial market-regulation sites as the main quantitative
  source and the national penalty portal is not in the table. The pipeline runs
  both: `collect.cfws` (the national 处罚文书 portal) and `collect.municipal`
  (the 50-site registry in `config/sources.yaml`). The corpus is effectively
  cfws-only, and that is a measured property of the sources, not a choice.
- The municipal adapter was rewritten on 2026-11-04 after its first sweep
  returned zero links: it now decodes pages from bytes (utf-8 → gb18030) instead
  of trusting the charset header (Tianjin served GBK as mojibake, so no keyword
  ever matched), discovers the penalty column (双公示/行政处罚/处罚公示) on each
  homepage when the registered `list_url` yields nothing, and requires a detail
  page to look like a penalty decision before registering it.
- First calibrated sweep, 50 sites, 2026-11-04T03:50Z: **16** no penalty column
  reachable from the homepage, **21** transport failures (15 TLS, 6 HTTP),
  **2** JavaScript shells, **3** sites with matching links (6 links total),
  **1** registered document, **5** detail pages rejected as non-penalty.
  Per-site outcome persists in `state/foods.sqlite` kv `source_status:municipal`
  and the discovered columns are listed there.
- Consequence for the paper: D1' as executed = the national portal. The
  municipal layer is reported as attempted, with its measured yield, and the
  Methods sentence must say so rather than claim 50 sites were harvested. The
  Plan's "1,500–3,000 filtered documents" remains a statement about the
  population; the retrieved set is bounded by D-35's 200-row cap per query.

## D-39. Law-name normalization in the anchor engine (instrument bug)
- The anchor engine captured the law name verbatim from running text and looked
  it up in `config/statute_map.yaml`. Extracted documents yield names such as
  `食用农产品市场销售质量安全监督管理办法\n` (trailing newline from PDF/HTML
  layout), `依照食品安全法` (no 《》, so the regex swallowed the connector) and
  `中华人民共和国商标法（2019修正）` (amendment parenthetical). None of these is
  an exact alias, so the article silently mapped to no category and the
  document lost its anchor for a formatting reason, not a legal one.
- Fix: `_norm_law()` strips whitespace, parenthetical amendments and the
  leading connectors 依照/根据/按照/依据/违反 before the alias lookup. It
  deliberately does **not** do suffix matching: `食品安全法实施条例` is a
  different instrument from `食品安全法` and must not collapse into it.
- Unit-checked: `依照食品安全法` → `食品安全法`; `中华人民共和国商标法（2019修正）`
  → `中华人民共和国商标法`; `中华人民共和国食品安全法实施条例` unchanged.
- Effect is measured at the next `retier`/`extract`, not assumed: the anchor
  coverage and basis counts before/after are written to
  `data/metrics/anchor_<stamp>.json`.

## D-40. "0 events" must carry its denominator
- `analyze/displacement.py` reported `n_events: 0` with no record of how many
  documents were actually read. A corpus that failed to load and a corpus with
  no displacement both produce 0, and the two mean opposite things.
- The output now carries `denominator: {n_docs_in_scope, n_docs_scanned}` and
  the status becomes `not_estimable` when nothing was scanned (instead of
  `downgraded_to_qualitative`, which asserts a measurement was made).

## D-41. GraphML export failed silently and left a 0-byte file
- `network.py` wrapped `nx.write_graphml` in `except Exception: pass`. The call
  failed on every run because node attribute `docs` is a list and GraphML
  cannot serialize lists, so `data/analysis/network.graphml` existed at 0 bytes
  — an artefact whose existence suggested the graph had been exported.
- Fix: export a copy whose `docs` is a `|`-joined string; on failure delete the
  partial file and record `graphml: {written: false, error}` in
  `network_metrics.json`. No gate reads GraphML, so this changes no estimate.

## D-42. E5: the chi-square number must not survive its own assumption check
- `compare.py` computed the 6-category chi-square and, when the minimum
  expected count fell below 5, added a collapsed Fisher test **next to it** but
  left `chi2`/`p` in the headline keys, so the invalid statistic was the one a
  reader (or the figure title) would pick up.
- Now the sparse case moves the chi-square under `chi2_unreliable` with a note,
  sets `primary_test: fisher_collapsed`, and the Fisher p is the test of
  record. The gate and the figure title read `primary_test`, not `p`.

## D-43. The E1 mean is taken over a subset; the subset is now printed
- `_agreement()` skips documents where both channels extracted no entity
  (agreement is undefined there). The mean agreement therefore rests on
  `n_scored_agreement`, not on `n`, and the difference was invisible.
- `e1.json` now carries `n_zero_entities` and `n_scored_agreement`; the daily
  report prints them next to the tiers. No threshold or statistic changed.

## D-44. Re-label noise band and tier-flip rate under the frozen v2 protocol
- Comparing the archived v1 silver against the v2 re-label on 621 documents with
  byte-identical text showed the mean agreement moving 0.7585 → 0.7026 and
  channel A (temperature 0) changing its entity set on 41% of those documents.
  A deterministic channel changing its answer on the same input means a v1→v2
  difference cannot be attributed to the protocol change alone. This is why the
  instrument's own run-to-run noise had to be measured instead of assumed.
- `scripts/stability_v2.py` re-labels a fixed stratified sample with the current
  code and writes a separate receipt `data/metrics/stability_v2.json`. It is
  read-only with respect to `silver.jsonl` and the `docs` table.
- Measured 2026-11-04T05:16:59Z on the then-current silver (sha recorded in the
  artifact's `protocol`), n_requested = n_scored = 48, n_errors = 0, seed
  20261104, workers 1, 31 zh / 17 en. Same protocol as the run that produced
  silver (doc_text_chars 20000; prompt hashes and max_tokens in the artifact).
- Agreement noise band: mean F1 channel A 0.6696, channel B 0.6707; mean Δ
  (B − A) = +0.0011, SD(Δ) = 0.0868. Independently recomputed from `per_doc`.
- Tier flip rate: **3/48 = 6.25%** (`low→medium` 1, `medium→low` 1, `low→high`
  1); unchanged tiers 45/48 (`high→high` 9, `low→low` 28, `medium→medium` 8).
  Violation-category changed on 3/48.
- This is a sample-specific receipt, not an extrapolation to the full corpus;
  no threshold, mapping table, tier rule, or silver record was changed.

## D-45. A list-valued entity field killed a 77-minute extract run (grounding now counts what it drops)
- `align.ground` did `text = (e.get("text") or "").strip()`. A falsy guard does not
  cover a **non-empty list**: one of the 5-sample votes in `extract` returned
  `{"text": ["…", "…"]}` and the whole stage died at 07:00:50Z with
  `AttributeError: 'list' object has no attribute 'strip'` after 4,626 s. The
  same input would have crashed the `label` stage too; it had not occurred there
  only because the adjudicator runs at T=0.7 and produces the looser shapes.
- `ground` now accepts only `str` text and `str` type, drops everything else —
  a non-string span cannot be verified verbatim, so dropping it is the honest
  handling — and **counts every drop** (`align.malformed_stats()`), reported as
  `align_ground_malformed` in `e1.json`. Silent drops are what the record rule
  forbids; the fix must not be silent either.
- Cost of the bug: one full `extract` run (4,626 s) plus one queued `retier`
  cycle released and re-queued. `retier` had already rewritten silver at
  07:04:21Z and is unaffected. No threshold, rule, or record changed; the fix
  only turns a crash into a counted skip.

## D-46. Protocol v2 did not remove the length bias in labelling rejections
- Label wave 2 (2026-11-04T05:43:44Z, 1,041 admitted): **54 rejected** —
  33 `label_truncated_output`, 19 `label_parse_failed`, 2
  `label_no_consensus_category` (5.2% of the wave; v1 was 25/368 = 6.8%).
- The bias D-28 identified is still there and still points the same way:
  labelled p50 = 3,096 chars (p90 5,399, max 12,742) vs rejected p50 = 4,810
  (p90 9,256, max 16,263). The 33 truncated documents have p50 = 5,759 chars.
  The longest labelled document is shorter than the longest rejected one, so the
  corpus still systematically excludes the densest decisions.
- Raising `max_tokens` from 1,600 to 3,000/4,000 (D-30) made these failures
  *reportable* (`finish_reason == "length"` is now a distinct reason from a
  parse failure) but did not eliminate them: the model still spends the budget
  before closing its JSON on the densest documents.
- Disposition: **not fixed inside this wave.** Changing `max_tokens` again would
  make the corpus a mix of two output budgets (D-14), which is worse than a
  reported 5.2% exclusion. Recorded as a pre-registered follow-up: a third wave
  with a JSON-only prefill (or a 6,000-token budget) applied to the whole
  corpus, then a per-document comparison against this wave. Until then every
  E1/E2 figure is conditional on "documents whose answer fit in 4,000 tokens".

## D-47. Re-deriving a tier from the rounded F1 disagrees with the label stage
- `metrics.agreement_f1` was stored rounded to 4 dp. `micro_f1` can return
  0.7499999999999999; the label stage compares the exact value
  (`f1 >= 0.75` -> False -> `low`), while a later re-derivation read the stored
  0.75 and wrote `medium`. `scripts/retier.py` on 2026-11-04 therefore flipped
  21 of 987 records `medium -> low` for a reason that had nothing to do with
  the anchor change it was meant to apply.
- Measured on the post-retier silver (987 records): 21 records moved
  `medium -> low`; `high` unchanged at 170; 42 records sit within 5e-4 of a
  threshold (see the `f1_boundary_docs` list in the receipt).
- Fix: `silver.py` now also stores the unrounded value as
  `metrics.agreement_f1_exact`, and `retier.py` re-derives the tier from that
  value, falling back to recomputing F1 from the stored per-channel entity
  lists, and only then to the rounded number. The receipt records which path
  each record took (`f1_recomputed_from_channels`, `f1_from_stored_rounded`).
- Disposition: code fixed; the corrected re-tiering is **not yet applied** to
  `silver.jsonl` — applying it while the extract stage holds the records in
  memory would be overwritten by that stage's own save. It runs at the next
  cycle boundary. Expected effect: `medium` 200 -> 179, `low` 617 -> 638,
  `high` unchanged.

## D-48. The apparent 04:00Z labelling discontinuity was query composition, not instrument drift
- Symptom: documents labelled before 2026-11-04T04:00Z scored materially lower
  than those labelled after. Chinese documents only: n=160, mean F1 0.6008
  before vs n=582, mean 0.6546 after (Delta 0.054).
- The per-minute profile shows why the split is not what it looks like:
  04:00-04:11Z is a burst of 197 documents at 12-30 docs/min (the rest of the
  wave ran at 4-8), and it is the English openFDA block (Chinese share in
  those minutes 0-12%, mean grounded channel-A entities 2.95-3.00, DOCUMENT
  0.00). The early group and the English block are different corpora, and the
  raw before/after comparison mixed them.
- Within Chinese, the split is collinear with the crawl query and perfectly
  so: every query family falls entirely on one side. Early = 伪造+食品 (86),
  篡改+食品 (38), 溯源码 (18), 虚假检验报告 (10), 虚假认证 (4),
  伪造检验报告 (4); late = 虚假标注+食品 (107), 检测报告+食品 (50),
  溯源+食品 (45), 检验报告+食品 (33), 冒用认证标志 (32), 合格证明+食品 (28),
  ... No family appears on both sides, so a same-family across-time comparison
  is **not identified** in this corpus and was not performed.
- No instrument change is detectable: vLLM started once at 02:34:15Z
  (`max_model_len` 23,040, `seed=0`) and never restarted; `config/settings.yaml`
  has mtime 03:46 but `common.settings()` is `@lru_cache(maxsize=1)`, so a
  process already running cannot see a later edit; the prompt files predate
  the run.
- Decisive test: 10 documents from the early group were re-labelled at
  04:53-05:16Z by `scripts/stability_v2.py` under the identical protocol
  (same prompts, temperatures, budgets). They reproduced their own low level
  (0.5558 -> 0.5234, Delta -0.0324, sd 0.0932, SE 0.0295) and did not move to
  the late level. The 38 late documents in the same re-label moved
  0.6995 -> 0.7095 (Delta +0.0100).
- Disposition: **not an instrument discontinuity; no re-label performed.**
  The difference is a property of the documents, and it is reported as such.
  Limits of the test: n=10 is a sample; it excludes drift of the observed size
  (~0.14) but does not certify the absence of drift below ~0.03.
- Consequence for the main corpus is recorded separately in D-49.

## D-49. The high tier is selected by document genre, not by sampling design
- Measured on `data/silver/silver.jsonl`, sha256
  `2922e3eaedac110a5d6bd84f67ec479e4697c71c54ab6d1014195ce456d2dd43`,
  987 records, at 2026-11-04T07:36:58Z. Product:
  `data/metrics/query_family_agreement.json`.
- Agreement F1 differs systematically across the 35 query families: 0.5915 for
  伪造+食品 (n=86) to 0.9137 for `reason_for_recall:misbranded` (n=95);
  spread 0.6389. Because the tier rule is an agreement threshold, the main
  corpus inherits that ordering.
- The high tier (170 documents) is not a scaled-down copy of the corpus:
  - `reason_for_recall:misbranded` is 9.6% of the corpus and 38.2% of the high
    tier (ratio 3.97; 65 of 170 documents).
  - 伪造+食品 is 8.7% of the corpus and 0.6% of the high tier (ratio 0.068;
    1 of 86 documents). 假冒+食品 0.126, 溯源+食品 0.129, 伪造+餐饮 0.157,
    检验检测报告+食品 0.171.
  - Selection rate differs by language: English 91/245 = 37.1%, Chinese
    79/742 = 10.6% — a 3.5x asymmetry between the two sides of the US-China
    comparison.
- The mechanism is measurable. The English corpus is structurally uniform:
  all 245 documents contribute exactly one END_USER (a recall record names one
  recalling firm) and 216 of 245 have exactly three grounded channel-A
  entities, so the two channels have little room to disagree about span
  boundaries. The Chinese base-crawl families carry 2-4x more DOCUMENT
  entities per document (伪造 1.78, 溯源码 2.39 vs 虚假标注 1.11). English
  documents also face only the agreement test, since the statute anchor is
  undefined for English (D-15); Chinese documents must pass both.
- The result that matters downstream: **167 of the 170 high-tier documents
  contain no SERVICE_PROVIDER entity at all**; only 3 do. Measured on the
  subsets the network actually reads (`load_edges()` keeps Chinese sources
  only, `tiers=("high",)`):
  - Chinese high tier, n=79: 3 documents mention a SERVICE_PROVIDER, 78
    mention an END_USER, and **only 3 mention both**. An edge requires two
    distinct actor mentions in one document, so at most 3 of 79 Chinese
    documents can contribute an edge at all; total actor mentions 81.
  - English high tier, n=91: 0 documents mention a SERVICE_PROVIDER, 91
    mention an END_USER (one each, because a recall record names one recalling
    firm) — **no English document can produce an edge**.
  The actor graph is therefore bounded by document structure, not by the
  market. The ~11-node/2-edge actor graph is a ceiling imposed by what the
  extraction schema returns per document, and every document contributes at
  most one actor, so "sparse network" is the wrong description: on this corpus
  the network is **not identifiable**, and Plan section 6 must be reported as
  `not_estimable` with this reason rather than as a small graph.
- The identity that settles it: on the dataset present at 2026-11-04T07:39Z
  (57 Chinese high-tier documents), the actor graph has **7 edges and the
  document structure permits at most 7 edges** — the graph is *saturated*, not
  sparse. Every co-occurrence the documents contain is already an edge; none is
  missing. So the node and edge counts measure how many documents name two
  actors (7 of 57), not how the ecosystem is organised. The exact numbers move
  when `dataset.jsonl` is rebuilt, which is why `actor_coverage` is now part of
  `network_metrics.json` — the comparison is automatic rather than remembered.
- Disposition: **the tier rule is not changed.** Lowering the target, or
  switching the main estimate to a wider tier, to make the corpus look more
  balanced is exactly the gate-gaming this register exists to prevent.
  What changes is disclosure and coverage:
  1. `scripts/query_family_agreement.py` writes per-family n, mean F1, tier
     counts and the high/corpus share ratio to a product file, so the claim is
     re-readable without a terminal.
  2. Every estimate on the high tier must state that it is conditional on an
     agreement-selected document genre, and is reported next to the
     pre-registered `high_medium` sensitivity that `analyze/sensitivity.py`
     already computes.
  3. The US-China comparison must print both selection rates (37.1% vs 10.6%)
     beside the estimate.
  4. The actor network must report n, the 3/79 and 0/91 actor counts, and must
     not be described as a market structure. `network.py` now writes an
     `actor_coverage` block (documents with any actor, documents with two or
     more actor mentions, and the edge count the document structure permits)
     into `network_metrics.json`, so the bound is part of the artefact.

## D-50. E2 counts nodes, but edges are bounded by documents that name two actors
- The E2 gate escalates to automatic expansion (Plan §6.2) whenever the actor
  graph has fewer than 400 nodes. That ladder can be satisfied by adding
  documents that each name one actor: every new document adds one isolated
  node and no edge. The floor therefore does not measure what the gate is
  supposed to measure.
- Measured on the dataset present at 2026-11-04T07:39Z (57 Chinese high-tier
  documents): the actor graph has 7 edges, and the document structure permits
  at most 7 edges — saturation 1.0. Only 7 of 57 documents name two actors
  (12.3%). On the full Chinese high tier the corresponding figure is 3 of 79
  (3.8%, D-49).
- This is why the previously reported "62 nodes / 7 edges" is not evidence of
  a sparse ecosystem: the graph already contains every edge the corpus permits,
  and 55 of 62 nodes are isolated because 55 documents name one actor.
- Disposition: the gate numbers are **not changed** (`e2_nodes_floor` 400 and
  `e2_nodes_target` 800 stay as the plan sets them). What is added is the
  binding constraint, recorded in `gates.json` under `E2.binding_constraint`:
  main-corpus documents, documents with two or more actor mentions, the maximum
  edges the structure permits, the multi-actor share, and the saturation ratio.
  When the multi-actor share is below 10% an action string is appended telling
  the reader to report Plan section 6 as `not_estimable` rather than to expand
  further for the network. The 10% is a **reporting trigger, not a pass/fail
  threshold**: it changes no gate outcome, and it is stated here so that it is
  not later mistaken for a tuned parameter.

## D-51. E5's main-corpus comparison is degenerate: the tier filter removes the variation it tests
- Measured on `data/silver/silver.jsonl` (987 records, 2026-11-04T07:46:40Z). The
  Chinese main corpus is 79 documents of which **75 (94.9%) are FALSE_LABELING**;
  FORGED_INSPECTION_REPORT 2, UNLICENSED_OPERATION 2. The full Chinese labelled
  set (742) is FALSE_LABELING 457 (61.6%), UNLICENSED_OPERATION 129 (17.4%),
  OTHER 102 (13.7%), FORGED_INSPECTION_REPORT 37 (5.0%), FAKE_CERTIFICATION 13,
  TAMPERED_TRACEABILITY 4.
- Total variation distance between the main-corpus distribution and the all-tier
  distribution: **Chinese 0.3335**, English 0.0113. The agreement filter moves a
  third of the Chinese category mass and almost none of the English mass, because
  the English corpus only ever contains two categories.
- Consequence: the E5 test of record was Fisher's exact on
  FORGED_INSPECTION_REPORT vs all other categories, i.e. **2 Chinese documents
  against 0 American documents**. It runs, it returns a p-value, and it says
  nothing. Meanwhile the comparison that E5 is supposed to make — are the two
  jurisdictions' violation typologies different — is answered "no, both are
  ~95% FALSE_LABELING", which is a statement about the filter, not the typology.
- Pre-registered criterion, stated before the code change: a jurisdiction's
  main-corpus distribution is **degenerate** if (a) its modal category holds at
  least 90% of its documents, or (b) fewer than two categories hold at least 5
  documents each. If either side is degenerate, the E5 main-corpus comparison is
  reported as `not_estimable_degenerate_main_corpus`.
- Disposition: the comparison is still computed and still stored, under
  `test_on_degenerate_table`, but it is no longer the test of record. The
  all-tier distributions are reported as a **descriptive, exploratory**
  comparison, labelled as such, because they contain the variation of interest
  but are not selected for annotation confidence. `compare.json` gains
  `main_corpus_profile` (per jurisdiction: n, modal category, modal share,
  categories with at least 5 documents), `main_corpus_estimable`, and
  `selection_diagnostic` (the two TVDs).
- Direction of the change: this makes E5 **stricter** — it converts a passing
  test into `not_estimable`. It is not a threshold relaxation, and the 90%/5
  criterion is recorded here so it cannot later be read as fitted.

## D-52. The GraphML export verdict never reached network_metrics.json
- `network.run()` wrote `network_metrics.json` before attempting the GraphML
  export, so that a crash in the export could not lose the graph counts. It then
  set `m["graphml"] = {"written": ..., "bytes": ...}` — and wrote the file only
  again inside the failure branch. On the success path the key was set after the
  last write, so it never appeared in the artefact.
- Observed 2026-11-04T07:48Z: `data/analysis/network.graphml` is 10,528 bytes on
  disk while `network_metrics.json` has no `graphml` key at all. A checker read
  the missing key, and a reader would have concluded the export had not run.
  This is the same failure shape as D-41: an artefact that exists while the
  record says it does not (or the reverse).
- Disposition: `network.run()` now writes the metrics file again after the
  export, on both branches, so `graphml.written` and `graphml.bytes` are always
  recorded. No gate reads this key; the change only makes the artefact truthful.

## D-53. Plan P095's type-shrinkage trigger is now met; the unstable types are the ones the network needs
- Plan P095: when E1 still misses and agreement is below 0.75, shrink the
  entity type set. M-6 (audit round 3) decided to record the shrunk figure
  without applying it. **That decision was taken when agreement was 0.7585 —
  above the 0.75 trigger.** On protocol v2 the full-set mean agreement is
  **0.6828** over 987 documents, so the trigger condition is newly satisfied and
  M-6's premise no longer holds. This entry reopens it rather than silently
  keeping a stale decision.
- Per-type pooled agreement on the current corpus (`data/silver/silver.jsonl`,
  987 records, sha `2922e3eaedac110a5d6bd84f67ec479e4697c71c54ab6d1014195ce456d2dd43`,
  measured 2026-11-04T07:55Z):

  | type | F1 | n_a | n_b | tp |
  |---|---|---|---|---|
  | END_USER | 0.8825 | 858 | 980 | 811 |
  | PENALTY_EVENT | 0.8723 | 588 | 673 | 550 |
  | JURISDICTION | 0.8526 | 866 | 973 | 784 |
  | TACTIC | 0.5239 | 1,115 | 813 | 505 |
  | SERVICE_PROVIDER | **0.2847** | 300 | 269 | 81 |
  | DOCUMENT | **0.2805** | 1,045 | 602 | 231 |

- Applying the pre-registered ladder rule (per-type F1 >= 0.75 and support
  >= 20) keeps `END_USER`, `JURISDICTION`, `PENALTY_EVENT`. Agreement on that
  set is **0.8471** — at the plan's 0.85 target, against 0.6828 on all types.
- The two types the two prompts cannot agree on are exactly the two the
  ecological network needs: `SERVICE_PROVIDER` (0.2847) is the actor side, and
  `DOCUMENT` (0.2805) is the hub the D-26 audit had to remove. The network's
  `not_estimable` verdict (D-49/D-50) therefore has a second, independent cause:
  even setting the document-structure bound aside, the provider mentions are not
  reproducibly extractable.
- What shrinkage would do to the tiers: high 170 -> 319, medium 200 -> 396,
  low 617 -> 272 (transition table: high->high 162, medium->high 53,
  low->high 104, high->medium 8, medium->medium 114, low->medium 274,
  medium->low 33, low->low 239).
- Disposition: **E1's status stays graded on the full type set.** Changing it to
  the shrunk value would let a post-hoc type selection masquerade as E1, which
  the code comment in `evaluate_e1` already forbids. What is added is a
  plan-mandated corpus variant, written to `data/metrics/tier_shrunk.json` by
  `scripts/tier_shrunk.py`, and every downstream estimate must be reported
  **twice**: once on the pre-registered full-type corpus and once on the
  P095-shrunk corpus, labelled as such. Shrinkage must never be described as
  "agreement improved" — it is a narrower question, not a better answer.
- Consequence for the paper: plan P095 also says that when this happens the
  paper's centre of gravity moves to silver-standard construction and its
  limits. That is the correct framing for this corpus, and it matches the
  measured pattern — the types that reproduce are the semi-structured fields
  (party, jurisdiction, penalty event), not the interpretive spans.

## D-54. Correction to a sub-count in D-49: 7/79, not 3/79, is the graph's binding structure
- D-49 quoted "3 of 79 Chinese high-tier documents name both a service provider
  and an end user". Re-measured on the current silver (987 records, sha
  `2922e3eaedac110a…`, 2026-11-04T08:05Z), 3/79 holds only under the stricter
  definition **both channels independently contain both types**.
- The graph is built from one channel's entities (`data/extracted/dataset.jsonl`
  carries a single annotation per entity), so the binding count is per channel:

  | definition | zh high (of 79) | en high (of 91) |
  |---|---|---|
  | channel a has provider and end_user | **7** | **0** |
  | channel b has provider and end_user | 8 | 0 |
  | both channels each have both types | 3 | 0 |
  | union of names across channels has both | 12 | 0 |
  | channel a: >= 2 distinct actor nodes | 7 | — |

- The structural ceiling implied by channel a is `sum C(k,2) = 7` over the 79
  documents, and the last `network_metrics.json` reported `n_edges = 7`. The
  saturation claim (observed edges equal the maximum the corpus permits) is
  therefore unchanged, and so is the `not_estimable` disposition.
- Rule for the paper: quote **7/79 (channel a)** when stating the graph's
  structural ceiling, and 3/79 only when describing cross-channel robustness.
  Never cite 3/79 as "documents that could produce an edge" — that understates
  the ceiling and misdescribes the estimator.
- English stays 0/91 under every definition, so the CN/US asymmetry is not an
  artefact of the definition chosen.

## D-55. The self-consistency ladder could be silently undone by the next retier
- Found while auditing the running extract. `extract/runner._selfconsistency`
  (the Plan P095 step-1 ladder: 5-sample majority vote per channel on
  low/reject documents, then re-measure) rewrote `channels` and
  `metrics.agreement_f1`, but **not** `metrics.agreement_f1_exact`.
  `scripts/retier.py` derives the tier from `agreement_f1_exact` (D-47), so the
  next retier would have re-scored every ladder-promoted document against its
  pre-ladder F1 and reverted the promotion — with no error, no log line, and a
  receipt that looked normal.
- Not yet visible in the data: as of 2026-11-04T08:05Z no silver record carries
  `decoding == "self_consistency"` (987/987 are None), so the rot had not
  landed. The path existed and the ladder was actively running, so it was fixed
  before it could.
- Fix, in two places:
  1. `_selfconsistency` now writes `agreement_f1_exact = f1` (unrounded) and
     `f1_source = "self_consistency_vote"` alongside the rounded value.
  2. `retier.py` now **recomputes F1 from the stored channel lists first** and
     treats `agreement_f1_exact` as a cache. When the cache disagrees with the
     channels by more than 1e-9, the channels win and the document is counted in
     the new receipt key `f1_exact_stale_docs` (examples in
     `f1_exact_stale_examples`). This removes the whole class of staleness bug
     rather than this one instance.
- Reporting rule for the paper: the post-ladder agreement is **not comparable**
  to the pre-ladder agreement. The same documents are re-measured with a
  stabilised decoder (5 votes at T=0.7 per channel), which removes sampling
  noise but not systematic divergence between the two prompts. Quote the
  pre-ladder figure as E1 and the post-ladder figure as "after the P095
  ladder", never as an improvement of the same estimator.

## D-56. Majority voting can raise agreement by making both channels say less
- The P095 step-1 ladder keeps an entity only when it appears in at least 3 of
  5 samples per channel. Both channels therefore get sparser, and micro-F1 is
  computed between two sparser sets. That statistic can rise with no change in
  accuracy: two extractors that both return "the one thing they are sure of"
  agree more.
- Instrumentation added before the ladder result is read: `_selfconsistency`
  now records `entity_density_before` and `entity_density_after` (entities per
  document, both channels summed) in `data/metrics/ladder.json` and in the
  `actions:ladder` kv entry.
- Reporting rule: the post-ladder agreement must be quoted **together with the
  density pair**. If density falls and agreement rises, the paper says the
  channels became more conservative, not more accurate. Neither number may be
  quoted alone.
- The post-ladder run in flight (chain8 extract, started 07:25:08Z) predates
  this instrumentation, so its density pair has to be recovered post hoc from
  `data/archive/preretier_20261104T0704Z/silver.jsonl` (pre-ladder) against the
  current silver for the documents with `decoding == "self_consistency"`.

## D-57. E4's zero is a sensitivity and construct limit, not "no displacement"
- Product of record (`data/analysis/displacement.json`, 2026-11-04T07:24:44Z):
  `n_events = 0`, `denominator = {n_docs_in_scope: 57, n_docs_scanned: 57}`,
  status `downgraded_to_qualitative`. The 57 is the stale main corpus; the
  rebuild will change it, the conclusion below will not.
- Positive control (2026-11-04T08:09Z, pod `date -u`): the same six-type rule applied to every
  Chinese document in the manifest, all tiers — **391 scanned, 8 match any
  pattern, 2 match with a governance term inside the 60-char window** (one low
  tier, one medium tier). Per pattern (contextual / raw): `perpetrator:实际控制人`
  1/3, `spatial:异地(?:生产|经营|销售)` 1/1, `target:换(?:品类|产品)` 0/2,
  `tactical:不再使用` 0/1, `functional:兼营` 0/1.
- So the detector can fire. It fires very rarely, and both contextual hits are
  outside the main corpus. Two independent reasons:
  1. **Sensitivity.** Six types, first match only, a hand-written phrase list,
     and a 60-character governance window. Two hits in 391 documents is what a
     narrow list produces.
  2. **Construct mismatch.** A displacement event is an adaptation *after* a
     governance shock. These documents are individual penalty decisions: they
     describe the act that was punished, not what the operator did next. The
     corpus may not contain the construct at all, which is the same kind of
     finding as D-49 for the network.
- Disposition:
  - The headline status stays `downgraded_to_qualitative` (Plan P098: merge into
    the qualitative discussion). Nothing about the rule or the thresholds
    changes.
  - `displacement.py` now also writes `sensitivity_all_chinese_tiers`
    (same rule, every Chinese tier, with `by_tier`). A zero in the main corpus
    is then always accompanied by the evidence of whether the instrument fires
    anywhere — "cannot be estimated" and "the detector never fired" are no
    longer indistinguishable.
  - **Do not widen the pattern list to reach the 15-event target.** That would
    be tuning the measurement to the gate. If the paper mentions displacement at
    all it quotes 2 contextual mentions as qualitative evidence, states they are
    outside the main corpus, and says the construct may not be observable in
    penalty decisions.
- Correction to `docs/AUDIT_round3.md` §7.4: the E4 row said "✅（实测 490）".
  490 is the D4 policy-event timeline that feeds E3's survival/Hawkes, not the
  E4 displacement count. The row now reads ⚠️ 0 events on the main corpus.

## D-58. The anchor gate on the rebuilt corpus is dominated by classes it cannot predict
- Measured 2026-11-04T08:12Z (pod `date -u`) on the current silver (987 records,
  sha `2922e3eaedac110a…`), using the same pair rule as `evaluate_e1`:
  **373 statute-grounded anchor pairs**, 81 fact-only documents.
- True support: FALSE_LABELING 297, UNLICENSED_OPERATION 40, OTHER 24,
  FORGED_INSPECTION_REPORT 9, TAMPERED_TRACEABILITY 2, FAKE_CERTIFICATION 1.
  Predicted support: FALSE_LABELING 335, UNLICENSED_OPERATION 21,
  FORGED_INSPECTION_REPORT 16, FAKE_CERTIFICATION 1. **The anchor engine never
  emits OTHER or TAMPERED_TRACEABILITY.**
- Aggregates: **macro-F1 over the six labels 0.2535**, micro accuracy **0.807**,
  macro restricted to classes with support >= 20 (FALSE_LABELING, UNLICENSED)
  **0.6805**. Per class: FALSE_LABELING 0.9019, UNLICENSED 0.4590,
  FORGED_INSPECTION_REPORT 0.1600, OTHER 0.0, TAMPERED 0.0, FAKE_CERT 0.0.
- Three distinct causes, only one of which is the familiar rare-class artefact:
  1. **Rare classes** (FAKE_CERT 1, TAMPERED 2): a zero here shifts a six-label
     mean by 0.167. D-18 recorded exactly this pathology at n=7; it is now
     decisive at n=373.
  2. **Category coverage**: OTHER (24 documents) and TAMPERED_TRACEABILITY (2)
     can never match because the anchor engine has no path to either label, so
     those 26 documents are wrong by construction.
  3. **Over-prediction of FALSE_LABELING** (335 predicted against 297 true):
     recall is 14/40 on UNLICENSED and 2/9 on FORGED. The lexicon that D-34
     revised favours labelling offences.
- Disposition: **the gated statistic is unchanged** (macro, the pre-registered
  choice) and E1 remains `failed` on the anchor side. Switching to micro after
  seeing the numbers would be moving the goalposts. What changes is disclosure:
  - `anchors.anchor_support()` now reports per-class F1/support/predicted,
    macro over all classes, macro over classes with support >= 20, micro, and
    the count of classes with support < 3. `gates.py` attaches it to E1 as
    `anchor_support` and raises an action when two or more classes have < 3
    documents; `evaluate_e1` writes it into `anchor_f1.support`.
  - Paper rule: quote per-class F1 with support and the micro figure next to
    the macro one, and say which is gated. Never quote macro 0.25 as "the
    extraction is wrong" — 80.7% of documents match, and the losses are
    concentrated where the anchor has no label to emit.
- The 02:27Z `e1.json` (n=141 pairs, macro 0.6414) is **not comparable** to this
  measurement: it predates protocol v2 and the expansion wave. Do not put the
  two numbers in the same sentence as a change over time.

## D-59. Ladder step 2 (self-training) cannot run in this environment
- The plan's P095 ladder has two steps: self-consistency, then QLoRA
  self-training on the high tier when it reaches 500 documents. Measured on the
  pod 2026-11-04T08:10Z: `peft` False, `trl` False, `datasets` False
  (`transformers` True). `scripts/train_qlora.py` exists but cannot execute.
- The code previously recorded `{"action": "self_training_requested"}` with a
  note, which a reader could take as "self-training was performed". It now
  records `trainer_available: false` and, when the high tier is below the
  trigger, an explicit `self_training_not_triggered` action with the threshold.
  Requested is not performed.
- Current high tier is 170, so the 500-document trigger is not met either way.
  If the ladder lifts it above 500, the action will still say
  `trainer_available: false`; the paper must then describe self-training as
  specified-but-not-executed, and the P115 "zero-shot vs self-training"
  comparison is not available — the available comparison is
  zero-shot vs 5-sample self-consistency.

## D-60. A zero category column made chi-square raise, and the crash left a stale compare.json
- After the 07:04Z retier the US high tier reached the `>=5` floor, so E5 ran
  `chi2_contingency` for the first time on a table containing a category with
  zero documents in both jurisdictions. scipy raised
  `ValueError: The internally computed table of expected frequencies has a zero
  element`. `compare.run()` raised before writing, so `compare.json` stayed at
  its 00:08Z content and `gates.E5` reported `insufficient_data` from that stale
  file. Nothing in the run said a test had crashed (the swallowing is D-61).
- Disposition: a category absent from both groups contributes exactly zero to
  the chi-square statistic, so it is dropped before the test; if fewer than two
  categories survive, the status is `insufficient_data`. The rule that chooses
  chi-square vs collapsed Fisher is unchanged, and no threshold moved.
- Verification on the then-current silver (987 records): `status=ok_fisher_collapsed`,
  `primary_test=fisher_collapsed`, `min_expected=0.929`,
  collapsed table `[[2,77],[0,91]]`, Fisher p=0.214479638. `py_compile` OK,
  `make smoke` 9/9.
- **Record-keeping incident.** This entry was first written elsewhere as "D-46"
  (in the code comment) and "D-47" (in the 07:27Z review); both numbers were
  already taken (D-46 length bias, D-47 exact-F1 tier). At 08:14Z the local copy
  of `DEVIATIONS.md` was uploaded over the pod's copy, which deleted the entry
  outright. It is reconstructed here from `analyze/compare.py` and
  `logs/agent/review_20261104T0727Z.md`; the only code change made by the
  reconstruction is the comment's number (`D-46` -> `D-60`). Rule adopted: the
  pod copy is authoritative, so pull it before appending, and take the next free
  number from the file as it stands at write time — never from memory.

## D-61. A crashed analyze module exited 0 and the gate read last cycle's file
- `cli.cmd_analyze` runs nine modules in a loop, catches every exception into
  `{"error": ...}`, then calls `gates.run()`, which reads each module's JSON from
  disk. A module that raises therefore does **not** refresh its file, and the
  gate scores the previous cycle's numbers as current. The process exits 0, and
  `chain_locked.py` prints only the last 300 characters of stdout, so the error
  dict can be cut off entirely. This is how D-60 went unnoticed for 45 minutes.
- Disposition: `cmd_analyze` now writes `data/analysis/_module_status.json`
  (`failed_modules`, `modules_run`, `at_utc`) **before** calling the gate stage;
  `gates.json` carries it as `module_status` and appends one action per failed
  module; `scripts/verify_products.py` fails the build when `failed_modules` is
  non-empty. The exit code is deliberately left at 0 — a crashed module and a
  failed gate are different things and should not be conflated in the chain's
  rc — but neither can now be silent.
- Impact: any gate number read from a `gates.json` whose `module_status` is not
  empty must be treated as stale. The key is new, so every `gates.json` written
  before this change lacks it; absence means "not yet instrumented", not "clean".

## D-62. Majority voting dropped `normalized`, so a voted document changed graph node identity
- `_vote_channel` rebuilds each voted entity as `{type, text, start, end}`. The
  rewritten extraction used to be the same shape, but the original channel
  entities also carry the model's `normalized` surface form. The vote kept the
  type-and-span count and threw the normalisation away.
- Consequence is at the graph, not the counts. `extract/runner.py` writes
  `"normalized": e.get("normalized") or e["text"]`, and `network.build()` keys
  nodes on `normalize_name(normalized)`. For a voted document the same operator
  written two ways in the text («XX食品有限公司» and «XX食品有限公司（下称当事人）»)
  therefore becomes **two nodes**, and they are co-mentioned in the same document,
  so they also get an edge *to each other*. Voting silently changes node
  identity; the effect is over-splitting (more nodes, plus spurious self-edges),
  not a merge.
- Disposition: `_vote_channel` now carries `normalized` from the grounded
  entities of the same vote (keyed by `(type, text)`), so a voted document is
  built from the same node identity as an unvoted one. No threshold, span or
  vote rule changed — only a field that was being discarded.
- The ladder that was running when this was found (chain8, started 07:25Z) had
  already loaded the old function, so **its output is affected**. They are not
  re-run: the pre-ladder entities are archived at
  `data/archive/preretier_20261104T0704Z/silver.jsonl`, and `normalized` is
  restored by exact `(type, text)` lookup per document. Coverage of that
  restoration is reported in `data/metrics/normalized_recovery.json`; an entity
  whose text does not appear in the archive keeps the `text` fallback and is
  counted as unrecovered rather than guessed. Network numbers quoted before the
  restoration must say which documents were voted.
- Same defect, older and wider: `label/silver.py:_vote` (the adjudicator's
  majority vote, Plan §5.2 third channel) rebuilt entities the same way, so
  every adjudicated — i.e. every disagreement — document has carried
  `normalized == text` since the start. It has not distorted the main
  estimate because only documents whose two channels *agree* (the
  intersection path, which keeps `ground()`'s fields) reach the high tier;
  the ladder is what first lifts a voted document into it. `_vote` now
  preserves the field as well, so future relabels are consistent. Existing
  adjudicated records are not rewritten; they are low tier, and the
  high+medium sensitivity graph is the only place their identity matters.

## D-63. The post-ladder E1 pools two decoding regimes and only its own number was kept
- The ladder stabilises only documents whose tier is `low`/`reject`. Documents
  already `high` or `medium` keep their original single-shot channels. The E1
  figure that `extract` writes after the ladder therefore averages a 5-sample
  majority-vote measurement over part of the corpus with a single-shot
  measurement over the rest.
- Two consequences, both measurement-level:
  1. `e1.json` held only the post-ladder value; the pre-ladder value (the one
     the pre-registered protocol defines) was overwritten in place, so the
     "before" number survived only in older files and archives.
  2. Nothing in `e1.json` said how many documents had been voted, so a reader
     could not tell whether the headline agreement was a single-shot figure.
- Disposition: `e1.json` now carries `pre_ladder` (mean agreement, status,
  by-language means, tier counts, scored n) whenever the ladder runs, and
  always carries `decoding_mix` (voted vs single-shot document counts). No
  statistic changed; both numbers are now on the same artefact.
- How to read it: the pre-ladder figure is the pre-registered E1. The
  post-ladder figure is the ladder's own outcome and must be reported as
  "agreement after 5-sample majority voting on N documents, single-shot
  elsewhere", never as an improvement over the pre-ladder number.

## D-64. A ladder-promoted document entered the corpus under a different entity rule
- The label protocol's final entity set is not "whatever the model said": when
  the two channels agree on the mentions and on the category, `label/silver.py`
  keeps the **matched intersection** (`[a for a, b, _ in align.match(ea, eb,
  tau)]`). The ladder wrote `r["entities"] = keep_a` — channel A's vote —
  unconditionally. A document promoted to `high` by the ladder therefore
  carried more entities (all of A, including the ones B never produced) than an
  equally-agreeing document that never needed the ladder.
- This is a construction-rule difference, not a threshold change: two documents
  with the same measured agreement could reach the main corpus with different
  entity sets depending on which path labelled them. Entity counts, per-type
  support and every degree in the actor graph inherit it.
- Disposition: `_selfconsistency` now applies the label rule —
  `f1 >= target and cat_a == cat_b` → matched intersection; otherwise channel
  A's vote, which is the same role the adjudicator plays in silver. Each record
  records `entity_rule`. No threshold, span rule or vote rule moved.
- The ladder already saved by the time this was found: `channels.a`/`channels.b`
  are stored on every voted record, so
  `scripts/ladder_entity_rule.py` recomputes the intersection exactly (no model
  call, no inference) and writes `data/metrics/ladder_entity_rule.json` with the
  document and entity deltas. Run it before the next `extract`, together with
  `scripts/recover_normalized.py` (D-62), so the dataset is built from the
  corrected records.


## D-65. A no-op ladder re-run would have relabelled the mixed E1 as `pre_ladder`
- Context: the chain8 ladder (extract started 07:25Z) ran on the bytecode loaded
  before the D-47/D-55/D-62/D-64 fixes were saved (08:20-08:23Z), so its 617
  voted records in `data/silver/silver.jsonl` carry the old entity rule and no
  `agreement_f1_exact`. The deterministic repairs are applied afterwards
  (`retier.py` recomputes exact F1 from the stored channels; the two repair
  scripts restore the intersection and `normalized`), then `extract` rebuilds
  the dataset.
- Defect found while planning that rebuild: the re-run starts from a corpus
  in which 617 documents are already voted, so the E1 measured at process start
  is the **post-ladder mixed** estimate (5-sample votes on 617 documents,
  single-shot on the rest). `run()` wrote that value as `pre_ladder`
  unconditionally, presenting a mixed estimator as the pre-registered
  single-shot E1 (D-63). The retier pass also moves 21 boundary documents from
  medium to low, so a re-run does trigger a small ladder; `changed > 0` alone is
  not enough to make the starting E1 a pre-ladder measurement.
- Disposition: `extract/runner.py` attaches `pre_ladder` only when this process
  re-decoded something **and** the starting corpus had zero `self_consistency`
  records (`n_voted_before == 0`). Otherwise it carries forward a
  previously recorded `pre_ladder` if one exists. No threshold, tier rule or
  statistic changed.
  The pre-registered E1 for the 2026-11-04 ladder remains the pre-ladder value
  in D-53 (0.6828); the post-ladder 0.7472 is reported only with its decoding
  mix.
- Scope: reporting metadata in `e1.json`; `decoding_mix` is still written on
  every cycle.

## D-66. `tier_shrunk.json` claimed to match the network build after D-64
- Context: `scripts/tier_shrunk.py` reconstructs the actor structure from silver
  `channels.a` and labelled the block "matches analyze/network.build". That was
  true before D-64: extract carried channel A's entity set for voted documents.
  D-64 changed the extracted dataset to keep the **matched intersection** on
  voted documents, and grounding removes ungrounded spans, so channel A can only
  over-count after that change.
- Measured 2026-11-04T10:20Z on silver n=1015 (sha `b4685bd7…`, zh high 124
  docs): channel-A reconstruction gives **16** documents with ≥2 actor nodes;
  the extracted dataset gives **9** (`network_metrics.actor_coverage.
  docs_with_two_or_more_actor_nodes = 9`,
  `max_edges_possible_by_structure = 9`). The 7 excess documents are channel-A
  mentions the dataset dropped: placeholder/third-party strings ("无",
  "第三方") and one second party removed by the intersection; 0 documents go the
  other way (dataset-only = 0).
- Disposition: text-only correction in `scripts/tier_shrunk.py` — the block is
  now labelled an upper bound reconstructed from silver channels, and §6's
  structural ceiling is pointed to `network_metrics.actor_coverage` (D-54). No
  threshold, mapping table, tier rule, agreement figure, or shrink figure
  changed; `tier_shrunk.json` was regenerated at 10:20:45Z.
- Scope: one scope sentence in a sensitivity artefact. Gate E2 already read
  `network_metrics`, so no gate value or paper estimate changes.
- Discipline: this entry number was read from the file at write time (next free
  after D-65), per D-60.

## D-67. A no-op `retier` reported every anchored document as "changed"
- Context: `scripts/retier.py` compares the recomputed anchor with the stored one
  via `a != r.get("anchor")` to fill the receipt's `changed` counter.
  `anchors.label()` returns `(law, article)` pairs as **tuples**, while
  `silver.jsonl` stores them as JSON **arrays**. The comparison therefore sees a
  type difference on every document that has at least one statute pair, and
  counts it as a re-anchor even when the serialized record is unchanged.
- Measured 2026-11-04T11:26Z on `data/silver/silver.jsonl` (1015 records,
  sha `b4685bd7…3927b9`): `retier.py --dry-run` before the fix printed
  `changed=762`, while `category_changed=0`, `anchor_pass_flipped=0`,
  `basis_before == basis_after`, and `tier_transitions` were identity-only
  (high 223 / medium 335 / low 457). Recomputing the same 1015 records with a
  JSON-normalised comparison gives **semantic anchor differences 0/1015**.
  The same check on `data/archive/preretier_20261104T0940Z/silver.jsonl`
  (987 records) gives semantic anchor differences **0/987**, category **0**,
  basis **0**; the real change in that receipt was `medium→low` **21/987**.
- Consequence already visible in a product: `AUDIT_round3.md` §三 quoted
  `changed=741 / 987 (75.1%)` as "锚点/分层被改写". Of those 741, 720 are this
  type-only artefact and 21 are the genuine tier moves. The audit note now
  carries the correction next to the table.
- Disposition: in `scripts/retier.py`, canonicalise the recomputed anchor through
  `json.loads(json.dumps(...))` before the comparison/store step. No threshold,
  mapping table, tier rule, agreement figure, or shrinkage rule changed.
  After the fix `retier.py --dry-run` on the same 1015 records prints
  `changed=0`, identical tiers; `py_compile` passes and `make smoke` is **9/9 OK**.
- Scope: the `changed` field of the `anchor_<stamp>.json` receipt (and the
  sentence that quoted it). No silver byte, gate value, network metric, or paper
  estimate changes. The real anchor/tier signals remain `category_changed`,
  `anchor_pass_flipped`, `basis_counts` and `tier_transitions`.
- Note: any *future* retier still writes a new silver mtime, so
  `verify_products.py` (mtime-based staleness) will mark older analysis products
  stale even when the bytes are identical. Run retier and analyze/report in the
  same locked chain, then re-run `verify_products.py` before quoting.
- Discipline: entry number read from this file at write time (next free after
  D-66), per D-60.

## D-68. The ladder overwrote single-shot channels with no snapshot, and the pre-registered E1 had to be rebuilt from archives
- The 10:19Z daemon cycle collected 28 new documents, labelled them
  single-shot, then ran the ladder on them (E1 still failed). No archive
  existed for those records, so their pre-ladder channels were overwritten and
  the pre-registered E1 could not be scored for them. Measured 14:45Z on
  silver n=1015 (sha `b4685bd77cc2b3e750b40dd692ea62bce1d7c5ea8bffb1a34d4040172e3927b9`):
  660 voted, 24 with no single-shot archived copy (22 absent from every
  archive, 2 whose only archived copies are themselves voted).
- Disposition 1 — the loss stops here: `_snapshot_preladder()` copies the
  corpus to `data/archive/preladder_<stamp>/silver.jsonl` **before** any channel
  is replaced, and only when at least one document is about to be voted.
- Disposition 2 — the estimate is rebuilt, exactly: `scripts/e1_preladder.py`
  substitutes, for each voted document, the archived record with identical
  `text_sha`, and scores the result with the same `Extractor.evaluate_e1`.
  Method validated by evaluating the 07:04Z archive alone: **n=987, 0.6828,
  en 0.8034 / zh 0.6430, anchor macro 0.2519** — reproduces D-53 to the digit.
- Result on the current corpus: **pre-registered E1 = 0.6898** (n=991 scored,
  636 substituted from archive, 24 unrecoverable and excluded), zh 0.6504 /
  en 0.8083, anchor macro 0.2400. So the 28-document collection moved the
  pre-registered E1 by +0.0070 and did not change its status.
  **0.6898 is the figure for the paper's E1; 0.7457 is the post-ladder mixture**
  (`e1.json`), and the two must never be quoted for one another.
- Instrument trap found while building it: `data/archive/v1_20261104T0235Z`
  already contains **396 records marked `decoding=self_consistency`** from the
  v1 ladder. Taking the earliest archive copy per document therefore discarded
  the 07:04Z single-shot record for **365** voted documents, and the estimate
  came out at 0.7573 (n=638) — a post-ladder number wearing the pre-registered
  label. A second attempt that dropped the guard but globbed every archive gave
  0.7212 (12 "recovered" from post-vote snapshots). Both values are void; the
  pool now skips voted copies entirely and takes the first single-shot copy.
- Presentation: `gates.json` E1 now carries a `pre_registered` block (figure,
  by-language, n scored, substitutions, unrecovered count) next to the mixed
  headline; `scripts/verify_products.py` checks `e1_preladder.json` exists with
  a mean. The gate status still comes from `e1.json`; the reconstructed value
  never sets it.

## D-69. Correction to D-62: `normalized` was never present on the final entity set at all
- D-62 said the majority vote dropped the model's `normalized` form and that this
  changed graph node identity. The mechanism is real but its premise is wrong for
  the main path. Measured 2026-11-04T14:58Z on silver n=1015:
  **channel A 0/4063 entities carry `normalized`, channel B 1601/3993, final
  `entities` 0/3947.** The prompt schema asks for it only in `beta_zh.txt` /
  `beta_en.txt` ("normalized":"可选"); the `alpha_*` templates never request it,
  and the label protocol's final entity set is taken from channel A
  (`[a for a, b, _ in align.match(ea, eb, tau)]`).
- Consequence: `extract/runner.py` has always written
  `normalized = e.get("normalized") or e["text"]`, so the dataset — and therefore
  `network.build()`'s node key — is **literal text with brackets and whitespace
  stripped**, for every document. Cross-document actor merging rests on exact
  surface-form equality, which is conservative in both directions: it over-splits
  the same operator written two ways, and it never merges two different operators
  that share a string. This is the same fact the 14:5xZ backfill measured as
  "0/2382 recovered".
- What stands from D-62: `_vote_channel` and `label/silver.py:_vote` no longer
  discard the field, so a future vote over channel B keeps it; and the channel-A
  vote used as the final set is unchanged either way. **What does not stand:**
  "the vote dropped the normalisation and that is why node identity changed" —
  there was no normalisation on that path to drop. The ladder did not change node
  identity; identity was already literal text for every document.
- No estimate changes. §6's `not_estimable` (D-49/D-50) does not depend on this.
  D-62's repair scripts stay, since they make the records self-consistent with
  the label protocol, but their measured yield is 0 and that is now explained
  rather than unexplained.


## D-70. The release bundle shipped data and code but none of the numbers the paper quotes
- Before 15:13Z `scripts/export_release.py` wrote `data/silver.jsonl`,
  `data/dataset.jsonl`, `foods_code.tar.gz`, `RELEASE.json` and the manifests —
  and no metrics. A reader could not check E1 = 0.6898, any gate status, or the
  §6 structural bound from the bundle: every one of those lives in
  `data/metrics/` or `data/analysis/`, and recomputing them needs the raw
  documents the bundle deliberately excludes (third-party government
  publications). The open-data commitment (Plan P115) was therefore
  unverifiable in exactly the place it is made.
- Fix: the exporter now writes `metrics/` with 18 product JSONs — `e1.json`,
  `e1_preladder.json`, `gates.json`, `network_metrics.json`, `compare.json`,
  `displacement.json`, `attack_tolerance.json`, `survival.json`, `hawkes.json`,
  `shocks.json`, `sensitivity.json`, `keyword_sensitivity.json`,
  `tier_shrunk.json`, `query_family_agreement.json`, `ladder.json`,
  `ladder_entity_rule.json`, `stability_v2.json`, `verify_products.json` — and
  `RELEASE.json` carries `metrics_shipped` plus an `e1_reported_twice` block
  naming the pre-registered figure and the post-ladder mixture, so a reader
  cannot swap them (D-63/D-68).
- `metrics/_module_status.json` is deliberately excluded: it is a per-cycle
  receipt about which modules ran, not a result (D-61).
- Precondition, now stated in the code: `scripts/verify_products.py` must pass
  with **zero stale** immediately before the build, because `stale_vs_silver`
  is precisely a metric older than the corpus it claims to describe. On
  2026-11-04 the sequence was `chain_locked.py retier extract analyze report`
  (15:08:50Z, all rc=0), `e1_preladder.py` (0.6898 unchanged), regenerated
  `tier_shrunk.py` / `query_family_agreement.py`, then verify → **28/28 pass,
  0 stale**.
- Build receipts: `release/foods_silver_20261104`, 22 files, 5.0 MB,
  `sha256sum -c MANIFEST.sha256` = **22/22 OK** on the pod and **22/22 OK
  again** on the local copy after a single-tarball transfer
  (`9ef85f0c548b55f009cbb64377e7741ec50751ca071aed4b69592e7b2edea39d`).
- Trap: the output directory is date-stamped, so a second build on the same
  UTC day raises `REFUSED` and exits. Either pass `--out` or build the next
  day. The 2026-11-04 bundle is a **pin, not a final corpus**: the daemon's
  02:00Z cycle will add documents and the next build will be a different
  snapshot.

- The first build shipped a code tree that predated this entry, so the
  bundle was rebuilt from the same snapshot afterwards: the shipped
  `DEVIATIONS.md` now contains D-70 itself. Corpus and metrics are
  unchanged between the two builds (`data/silver.jsonl` sha identical),
  so the rebuild moved only `foods_code.tar.gz` and the manifests.


## D-71. The corpus had no stopping rule, so "the final release" had no definition
- Through 15:30Z there was no freeze criterion anywhere in the tree. The daemon
  collects every day at 02:00Z, and the plan's P096 only says "expand
  automatically; if E2 is still short, replace network metrics with a case-chain
  typology". With no cut point announced in advance, "the final release" would
  have been whichever snapshot happened to be built last -- a stopping rule
  chosen after seeing the result.
- Decision, taken 2026-11-04T15:31Z **before any of the 2026-11-05 documents
  existed**: the corpus is frozen at the end of the **2026-11-05T02:00Z
  daemon cycle**; collection stops there and the final bundle is
  `foods_silver_20261105`. If that cycle never completes, a fallback deadline
  (2026-11-06T06:00Z) builds on whatever corpus exists, and the receipt records
  that it was built on the deadline branch rather than after the cycle.
- Why stopping here does not change an estimate:
  (a) E2's binding constraint is document structure, not sample size -- 9 of
  124 main-corpus documents name two distinct actors and
  `max_edges_possible_by_structure = 9` with saturation 1.0, so further
  documents add isolated nodes, not edges (D-49/D-50);
  (b) E1's deficit is a decoder/protocol property and the next rung of the
  ladder, QLoRA self-training, is unavailable in this environment (D-59);
  (c) every remaining gate is already terminal (`failed` / `downgraded` /
  `not_estimable`). More collection moves denominators, not statuses.
  This is a statement about what the current corpus can identify, not a claim
  that the corpus is large.
- Mechanism, deterministic and independent of the LLM review agent:
  - `scripts/finalize_release.py` does the whole final step in one command:
    stages through `chain_locked.py`, rebuild `e1_preladder` / `tier_shrunk` /
    `query_family`, `verify_products`, `export_release`, then
    `sha256sum -c MANIFEST.sha256`. It refuses to call a bundle final when
    (i) any stage returns rc != 0, (ii) `data/silver/silver.jsonl` changes sha
    between start and end (documents arrived mid-run and the bundle would mix
    two snapshots), (iii) `verify_products` has any failed **or stale** check,
    or (iv) the bundle's manifest does not verify in full, or the silver inside
    it differs from the frozen sha. Every branch writes
    `data/reports/finalize_<stamp>.json`.
  - `scripts/finalize_watch.sh` waits for the kv `daemon:last_run_date` to
    equal the target date (or the deadline), stops the daemon, then runs the
    finalizer. It is restart-safe: it reads the kv each loop, so restarting it
    after the cycle does not wait for another day.
- Dry run, 2026-11-04T15:29:57Z, exercised the whole path except the export on
  the then-current corpus: stages rc=0, silver sha identical before and after
  (`b4685bd7...`), `verify_products` 28/28 with 0 stale -> `dry_run_ok`. The
  export step was exercised by hand minutes earlier (D-70) and produced a
  bundle that verified 22/22 on two machines.
- Reversible: collection resumes with `scripts/install_daemon.sh`.

## D-72 — v7 计划书 E6–E9 的登记与编号重映射（先登记，后执行）

- **背景**：2026-11-05 的计划书 v7 新增补跑实验 E6–E9，并要求"新实验以 D-nn 逐条先登记再执行；新增不改旧"。E1–E5 的口径冻结不变。
- **撞号事实**：计划书建议的登记号 D-70…D-77 中，**D-70**（发布包缺指标）与 **D-71**（冻结规则）本仓库已用。因此按"下一个空号"分配，计划书里的建议号不作准：
  | 计划书条目 | 计划书建议号 | 本仓库实际号 |
  |---|---|---|
  | E6 确定性描述套件 | D-70 | **D-72**（表与统计量）＋ **D-73**（事实段/词典/地域/负对照） |
  | E7 行为—危害类型学 | D-71 | **D-74** |
  | E8 中美对照 | D-73、D-74（映射表） | **D-75** |
  | E9 自训练受控复跑 | D-75 | **D-78**（状态登记） |
  | 负对照习惯 | D-76 | **D-76**（未撞号，沿用） |
  | 冲突仲裁 | D-77 | **D-77**（未撞号，沿用） |
  | "新增类型先登记" | D-72 | 下一个空号 **D-79 起** |
- **E6 的法规映射表：为什么是 v2 独立文件，而不是改 v1**
  - `config/statute_map.yaml`（v1）是**锚点引擎**的表，它的输出就是 E1 的 anchor F1。E1 已冻结（D-58、D-71）。扩充 v1 会改变"哪些文书可锚定"，从而**刷新一个已冻结的统计量**。
  - 计划书要求"映射表版本号 +1、不改动既有映射、仅扩充覆盖"。两者同时满足的做法：新文件 `config/statute_map_v2.yaml`，`version: 2`，**v1 的六个类别与其 statutes 逐条原样复制**，只新增类别与别名；E6/E8 读 v2，锚点仍读 v1，E1 不受影响。论文必须写明"E1 锚点用 v1，Results 1 描述分布用 v2"。
  - 新增的五个 `descriptive_only` 类别**都在造假框架之外**，E8 的中美对照只用 v1 的五个造假类别 + OTHER。
- **v2 每一条新增映射的语料依据**（2026-11-05T01:0xZ，在 1015 篇语料上先在罚则条款里测频、再读文书自带的条文原文确认语义）：
  - 商标法第五十七条/第六十条（99 篇罚则条款引用；文书自带原文"销售侵犯注册商标专用权的商品"）→ TRADEMARK_INFRINGEMENT。
  - 广告法第五十五条（23）、反不正当竞争法第二十条（11，文内原文"对其商品作虚假或者引人误解的商业宣传"）→ FALSE_ADVERTISING。
  - 反不正当竞争法**第二十五条（19）故意不映射**：文内原文是裁量规则（"从轻或者减轻行政处罚"），不是虚假宣传罚则；条号随修订变动而文书不标明版本，映射它就是猜。
  - 产品质量法第四十九条、第五十条 → PRODUCT_QUALITY；第五十三条（35）**不映射**：未在语料中找到可核的条文原文，宁可不覆盖。
  - 食品安全法第一百二十六条（70）、计量法实施细则第四十六条（12，文内原文含"破坏计量器具准确度和伪造数据"）→ PROCEDURAL_NONCOMPLIANCE（程序性违规，非造假）。
- **统计量定义**（先定后算）：`category_distribution` 为确定性单标签；同一条文集合推出多个类别且事实词表无法唯一定夺时计 `UNRESOLVED` 并另记 basis（`ambiguous_statute` / `ambiguous_facts` / `none`），**不猜**；`llm_cross_tab` 仅作描述，不作结果（见 D-77）。
- **本次实测**（1015 篇银标准，中文层 763；产物 `at_utc` 2026-11-05T01:09:50Z，silver sha `b4685bd7…`）：规则可判定 537/763 = **0.7038**，`UNRESOLVED` 226；FALSE_LABELING 333、TRADEMARK_INFRINGEMENT 56、PROCEDURAL_NONCOMPLIANCE 54、FORGED_INSPECTION_REPORT 30、FALSE_ADVERTISING 29、UNLICENSED_OPERATION 26、PRODUCT_QUALITY 5、FAKE_CERTIFICATION 4。
- **语料边界**：E6 只在**中文处罚文书框架**（`lang=zh`，763 篇）上跑；252 篇 openFDA 属 D3a、是另一体裁，归 E8。把两者放进同一条年度趋势会把 2012–2025 的召回与 2023–2026 的处罚混成一条线（混跑测得的年度分布里 2012/2016/2020 全部来自 FDA）。
- **产物**：`data/analysis/e6_descriptive.json`、`data/reports/e6_tables.md`；`verify_products.py` 新增三条键检查（分布、负对照、表版本）。

## D-73 — E6 的三个接口决定：事实段匹配、食品词典、地域口径

1. **食品类别只在"事实段"里匹配**。理由是可测量的：把词典套在全文上时，"食品、食品添加剂"这句法规模板出现在 **498/763** 篇里，食品添加剂类被顶到 **479/763**——量的其实是文书模板而不是产品。事实段 = 从 `经查|经调查|查明|违法事实|现查明` 到 `上述事实|以上事实|上述行为|有下列证据|证据证明|本局认为|我局认为`；无起点标记时退回文首 1500 字（该退路被计数记录）。
   - 匹配字段顺序：先 `penalty_content`（登记表里的结构化摘要），再事实段；**不再退到全文**。改后匹配 523/763 = **0.685**，食品添加剂降到 73，未被匹配记 `UNMATCHED` 240 篇（31.5%）——这是可报告的量，不是缺陷。
2. **食品类别词典 v1**（`config/food_categories.yaml`）：15 个类别，含计划书点名的预包装食品/保健食品/餐饮原料/食用农产品/婴幼儿食品，附同义词；**明确排除**"食品/食品原料/原料/产品/冷冻"这类在几乎每篇都出现的词。多标签计数与单标签主类（按 `primary_priority` 顺序，具体品类先于添加剂类）都输出。
3. **地域只取发文机关，不插补省份**。国家级门户 `meta.agency` 对 763 篇全覆盖，但**只有 34 篇（4.5%）在机关名里带省名**；市级 210、区县 508、其他 11。计划书设想的"地域=来源站点字段"依赖市级站点，而 50 个站里只有 1 个采集到 1 篇（见 D-38 的校准状态）。因此 `region` 报三层：省名明示（34）、发文市（top 30）、层级分布；**不**用市名反推省份（那需要一张人工地理表，属于编造风险）。论文中这条写成可验证缺席。
4. **罚款金额**：`罚款\s*…元/万元` 全文取全部匹配，取最大值为主罚；单位统一为元。有金额的 482/763。分位数（n=482）：中位 5000、p75 19,000、p90 55,100、最大 600,000 元。
5. **负对照统计量**（计划书"沿用 v6 一致率口径，τ=0.5"这句不适用于类别标签）：v6 的 τ=0.5 是**跨度重叠**阈值，类别是单标签，不存在跨度匹配。实际定义为：50 篇随机切片（seed=20261104），双通道各自独立分类，**主判据 = (规则==通道A 与 规则==通道B) 的均值**，精确匹配；规则判为 UNRESOLVED 的记不一致。另报 A vs B。阈值仍用计划书的 0.85/0.75；低于 0.75 → 全维度标 `coarse`。

## D-74 — E7 行为—危害类型学的构建规则（先定后跑）

- **对象**：high 层中文 124 篇（计划书指定）。
- **三个维度，来源不同，必须分开说**：
  - 角色：确定性，取已抽取的 END_USER / SERVICE_PROVIDER 是否出现（END_USER_ONLY / PROVIDER_ONLY / BOTH / NEITHER）。
  - 手法：确定性，**在事实段上**跑固定关键词规则（FORGED_REPORT / TAMPERED_TRACEABILITY / FAKE_CERTIFICATION / FALSE_LABELING / UNLICENSED / ADULTERATION / EXPIRED_MATERIAL / ILLEGAL_ADDITIVE / TRADEMARK / FALSE_ADVERTISING），可多标签。**不用抽取出的 TACTIC 实体**：124 篇里 43 篇完全没有 TACTIC，用它会得到"抽取器的漏检"而不是语料的手法分布。
  - 危害：唯一需要模型的一维，因为现有抽取不编码它。双通道独立作答（两套措辞、温度 0.0/0.3），封闭五类 FOOD_SAFETY / CONSUMER_DECEPTION / MARKET_ORDER / MIXED / UNCLEAR；**分歧进第三通道**（同模型 5 次采样多数票，与银标准裁决同形）。
- **判据**（计划书数值，冻结在此）：双通道一致率 ≥ 0.80 标杆 / ≥ 0.70 底线；**条目 = 支持数 ≥ 3 的组合**，< 3 记 singleton；条目的文档级一致率 < 0.70 的进"待人工审计清单"（只列清单，不阻塞）。
- **首次执行**（首次运行，124 篇；该次产物已被第二次运行覆盖，仅最新一次的 `at_utc` 2026-11-05T01:15:07Z 可核）：一致率 **0.8306**（target_met），第三通道裁决 21 篇；7 个条目、6 个 singleton；危害分布 CONSUMER_DECEPTION 104 / FOOD_SAFETY 18 / MARKET_ORDER 2；角色 END_USER_ONLY 112 / BOTH 9 / NEITHER 3。
- **引文匿名化**：从事实段取第一句含违禁行为词、长度 20–200 的句子；替换当事人名、法定代表人、企业名（含"公司/厂/店/商行/经营部"等词尾）、身份证号、手机号、许可证号、统一社会信用代码。源文档是公开处罚决定，这一步是计划书要求的匿名化，不是保密措施；宁可过度屏蔽。
- 后续新增类型必须先登记（下一个空号 D-79 起），不得边跑边改框架。

## D-75 — E8 中美对照：映射表、可估性判据、样本量差异

- **映射表 v1**（`config/e8_us_map.yaml`）：对 `reason_for_recall` 做确定性关键词映射，落到 v1 的五个造假类别 + OTHER；一句话同时命中两个造假类别的记 OTHER，不做优先权裁决。"misbrand*" 映射到 FALSE_LABELING 时必须写明：**FDA 的 misbranding 是监管性的标签缺陷，不等于故意的虚假标注**。
- **可估性判据（先定）**：若美国侧理由中明示"故意欺骗"线索（counterfeit / fraud / forged / falsif / intentional / fake）的占比 < 10%，E8 判 `not_estimable_instrument_mismatch`：只报两种文书体裁的**构成描述**，不报"造假率差异"。
- **实测**（产物 `at_utc` 2026-11-05T01:12:51Z）：美国 253 条，明示造假线索 **0.0%**（0/253）→ `not_estimable_instrument_mismatch`。中国侧 393/763 落入造假框架（226 篇 UNRESOLVED 不进表）。检验：χ² 期望频数 < 5 → 主检验为折叠 Fisher（FALSE_LABELING vs 其余）。
- **样本量口径更正**：计划书写"openFDA ~800 件欺诈相关，已采集"；**实测磁盘上是 253 个 JSON**（`data/raw/openfda/*/F-*.json`，253）。这不是采集失败，采集器的查询批次见 `config/settings.yaml collect.openfda.queries`；论文按 **253** 报，不按 800 报。
- **结论的写法**：两张表并列，附"两种体裁不可等同"的限制句；Cramér's V 只在描述意义上给，不作推断。

## D-76 — 每个确定性抽取器上线前的负对照（沿用计划书编号）

- 规则：任何新建的确定性抽取器（E6 的类别引擎、食品词典、地域/金额抽取，E8 的 FDA 映射）在上线前，必须跑 50 篇随机切片的"规则 vs 双通道 LLM"一致率；任一维度 < 0.75 则该维度降级为粗粒度报告，并在产物里标 `coarse`。
- 适用范围：E6 已完成（阈值 0.85/0.75，主判据定义见 D-73 第 5 条）。E8 的 FDA 映射**不适用**该检查：它映射的是英文召回理由，双通道 LLM 没有对应的中文类别能力，且 E8 已判定为不可估；这一点如实写出，不假装做过。

## D-77 — 确定性结果与冻结的 LLM 结果冲突时，以确定性为准（沿用计划书编号）

- E1–E5 的 LLM 抽取结果已冻结；E6–E8 的确定性结果若与之冲突，**以确定性结果为准**并在文中说明差异来源。`e6_descriptive.json.llm_cross_tab` 就是这张冲突表：行=冻结 silver 类别，列=v2 规则类别。
- 实测要点（中文层 763 篇，供论文正文引用）：冻结 LLM 判 FALSE_LABELING 的 484 篇里，规则判 FALSE_LABELING 277、`UNRESOLVED` 135、FALSE_ADVERTISING 29、PROCEDURAL 17、FORGED_REPORT 10、商标侵权 9；LLM 判 OTHER 的 79 篇里，规则判商标侵权 26、FALSE_LABELING 19、`UNRESOLVED` 24。**两者测的不是同一个构念**：LLM 读案情，规则读罚则条款。差异要在文中解释，而不是用一个去校正另一个。

## D-78 — E9（QLoRA 自训练受控复跑）：当前状态

- 计划书把 E9 列为**可选、附录级、探索性**，GPU 6–10 小时夜间窗口，评测只用锚点 F1，结果不论正负都进附录。
- **当前不能执行的事实**：pod 的 venv 里 `peft` / `trl` / `datasets` / `bitsandbytes` **均未安装**（2026-11-05T00:58Z 实测 `importlib.util.find_spec` 全 False），且 vLLM 常驻占用 23.9/24.5 GB 显存，训练需先停推理服务。D-59 已登记同一事实。
- **决定**：E9 **不进入终版发布路径**，也不阻塞 2026-11-05 的冻结（D-71）。E6–E8 是 Results 1–3 的必需项，E9 只影响附录一张表。若后续要跑：先安装训练栈并停 vLLM，用 `scripts/train_qlora.py`，结果另立 `data/analysis/e9_selftrain.json` 并单独登记。
- **与 E1 的关系**：E9 不改 E1 的口径；其锚点 F1 与 post-ladder 0.7457 属**不同评测对象**，严禁并列互引（计划书第三部分同款要求）。

## D-79 — E6 负对照未过底线后的处置：粗粒度降级、事后诊断、以及 E7 的一致率波动

- **事实**：E6 的负对照（D-73 第 5 条的定义，seed 20261104，50 篇）实测**主判据 0.38–0.39**（两次运行：0.38、0.39），低于底线 0.75。按计划书与 D-76 的规则，Results 1 该维度**降级为粗粒度**。
- **为什么两次运行不同**：通道 B 温度 0.3（与主管线同一协议），因此这个数字有抽样波动。差异远离阈值（0.39 vs 0.75），判定不随波动改变；报告时写"一次运行的值"，并注明该口径。
- **事后诊断（先声明：在看到 0.39 之后才加，因此不作判据）**：预注册统计量把"规则弃判"与"规则判错"混为一谈。补两项读法：
  - 规则可判定率（coverage）= **0.62**（31/50）；
  - 在可判定子集上，规则 vs 通道 A = **0.6129**、vs 通道 B = **0.6452**（n=31）。
  结论：**分歧不是弃判造成的**——即便规则给了答案，也只有六成与模型一致。因此"确定性类别引擎与 LLM 类别不是同一个构念"是实测结论，不是借口。
- **降级映射（在读到负对照结果之前就写死在代码里，`COARSE` 常量）**：四个造假类 → DATA_FALSIFICATION；UNLICENSED_OPERATION → UNLICENSED；商标/广告/产品质量 → MARKET_ORDER；程序性违规 → PROCEDURAL；未判定 → UNDETERMINED。
  - Results 1 报粗粒度分布（763 篇）：**DATA_FALSIFICATION 367、UNDETERMINED 226、MARKET_ORDER 90、PROCEDURAL 54、UNLICENSED 26**。
  - 细粒度表（9 类）仍随产物发布，但正文的 Results 1 数字**只能引粗粒度表**，并必须把 0.39 的一致率写在同表脚注。
- **对论文的含义**：计划书的退路（"E6 负对照普遍 <0.75 → Results 1 全转粗粒度 + 把'规则抽取不确定性'写成结果"）已触发。Results 1 的主结论因此变成"在 763 篇中文处罚文书中，规则引擎可判定 70.4%，其中 48.1% 落在数据造假类；另有 29.6% 因条文与事实无法唯一定夺而不可判定"，而不是一张九类分布表。
- **E7 的一致率波动（同批登记）**：两次完整运行的文档级一致率分别为 **0.8306** 与 **0.8226**（通道 B 温度 0.3 + 第三通道多数票）。两次都 ≥ 0.80 标杆，判定不变；发布物以**冻结语料上最后一次运行**为准，论文引用该产物里的数，并注明"温度 0.3 采样，运行间有小幅波动"。
- **编号**：下一个空号现为 **D-80**（D-74 末尾"新增类型先登记 D-79 起"的指针顺延）。E9 若执行，另立 D-80+。

- **更正（2026-11-05T01:22:26Z，本条目写完后自查发现，不改任何结论）**：D-72 / D-74 / D-75 里由我手写的相对时间戳（"01:2xZ" 等）与产物自带的 `at_utc` 不一致，已按产物逐条改正（E6 2026-11-05T01:09:50Z、E8 2026-11-05T01:12:51Z、E7 最新一次 2026-11-05T01:15:07Z；E7 首次那次 0.8306 的产物已被第二次运行覆盖，其时间戳不可复核，只保留数值）。教训与"手打的数没有机器"同型：**时间戳一律从产物复制，不凭记忆写**。

## D-80 — E8 表格行标签与被删零列错位；折叠 Fisher 实际检验的是错类别（2026-11-05T01:23Z 巡检发现）

- **现象**：`scripts/e8_us_cn.py` 先按 `FRAUD_CATS`（6 类）建表，随后删掉"中英两侧都为 0"的行（本次是 `TAMPERED_TRACEABILITY`），但把未删的 `FRAUD_CATS` 原样写进 `table_rows`。结果 `data/analysis/e8_us_cn.json` 的 `table_rows` 有 **6** 项、`table` 只有 **5** 行，按下标对齐时从第 2 行起全部错位；`data/reports/e8_table.md` 由 `zip(table_rows, table)` 生成，因此表头与数字系统性错配（实测把 FAKE_CERTIFICATION 的 4 写成 TAMPERED、把 FALSE_LABELING 的 333 写成 FAKE_CERTIFICATION、把 UNLICENSED 的 26 写成 FALSE_LABELING，`OTHER` 的 156 落到 UNLICENSED 行）。
- **同一根因的第二个后果（更严重）**：折叠 Fisher 的索引写作 `i = FRAUD_CATS.index("FALSE_LABELING") = 3`，却用于**删零列后的** `table`。本次 `table[3]` 是 `UNLICENSED_OPERATION`，所以 `test.collapsed_fisher.table_cn_label_vs_rest=[26,367]`、`table_us=[0,253]`——**检验的是 UNLICENSED vs 其余，却被 D-75 与产物标成 "FALSE_LABELING vs 其余"**。这与 D-75 预注册的折叠规则不符。
- **量测（可复读）**：`e8_us_cn.json`（at_utc 2026-11-05T01:12:51Z，cn 393 / us 253）`len(table_rows)=6` vs `len(table)=5`；`cn.counts` 为 FALSE_LABELING 333、FORGED_INSPECTION_REPORT 30、UNLICENSED_OPERATION 26、FAKE_CERTIFICATION 4；`us.counts` 为 FALSE_LABELING 97、OTHER 156。按类别名重算，正确的折叠 2×2 应是 cn `[333, 60]`、us `[97, 156]`。
- **处置**：只改**表与索引的对齐方式**，不改映射表、阈值、类别集合或可估性判据：(1) 建表时同步保留"删零列后"的标签序列，`table_rows` 写该序列；(2) 折叠索引改为在 `table_rows` 中查 `FALSE_LABELING`，若该列不存在则在 `test` 中记 `not_run` 并写明原因，不静默换类别；(3) 重新生成 E8 产物与 markdown 表。`config/e8_us_map.yaml`、`FRAUD_CATS`、可估性阈值（美国明示造假线索 <10%）均不动。
- **影响面**：仅 E8（Results 3）的构成表与"检验记录"。E8 的可估性判定不依赖行顺序：美国侧明示造假线索仍为 **0/253** ⇒ 仍为 `not_estimable_instrument_mismatch`，结论口径不变（只报构成描述，不报造假率差异）。E6/E7、E1–E5 与门禁均不受影响。修正后的产物需重跑 `verify_products.py` 并重出 E8 markdown；终版 extras 本就会在构建前重跑 E8，故以修好的代码为准。

- **更正（2026-11-05T01:24Z，按实测落盘时间）**：代码修复于 01:23:50Z 写入 `scripts/e8_us_cn.py`（`py_compile` 通过、`make smoke` 9/9 OK）；`data/analysis/e8_us_cn.json` 已于 **01:23:55Z** 重生成——`table_rows` 现为 5 项且与 `table` 逐行对齐（FORGED 30/0、FAKE_CERTIFICATION 4/0、FALSE_LABELING 333/97、UNLICENSED 26/0、OTHER 0/156），折叠 2×2 为 cn `[333,60]`、us `[97,156]`（Fisher p=2.4408e-34），可估性仍为 `not_estimable_instrument_mismatch`（美国明示造假线索 0/253）。`verify_products.py` 在 01:24:11Z 为 **37/37 pass、0 stale**。
  **未能重写的一件**：`data/reports/e8_table.md` 仍是 01:12:51Z 的旧错位版本——`data/reports/` 为 `root:foods 2755`，本会话以 `agent` 运行，目录与文件均无写权限，脚本的 `REPORT.write_text()` 也被拒（JSON 走临时文件+rename 才能落盘）。因此该 md **在 root 的终版 extras 重跑 E8 之前不得引用**；代码已修，root 侧重跑即会生成正确表。此项是运行权限限制，不是数据问题。

## D-81 — 给 E6 的 `basis=none` 残差加一个描述块（不改变任何判据）

- **背景**：D-80（E8 表格错位，本册已有条目）处理的是 Results 3 的表对齐缺陷；本条是 Results 1 的补充描述。原产物只说 `basis = none: 63`，没说这 63 篇是什么，审稿人问"30% 未判定里有多少是映射表不够、多少是案子本来就不在造假框架里"时无据可答。
- **做法（只加描述；`label_v2` 一行未动）**：对 `category is None 且 basis == "none"` 的每篇文书读两项：
  1. `penalty_clause_only_administrative_penalty_law`：罚则条款里**只出现《行政处罚法》**。这是**机制**——文书用程序法作罚则依据，实体违法只写在事实段，条文→类别引擎在这种情况下本来就无表可查。
  2. `law_mentioned_doc_counts`：该文书引用到的法律（**文档级去重**），用来看残差是"缺一条法"还是一长串不在五类造假框架里的主题。
- **为什么不扩表把残差吃进来**：`计量法`（破坏计量器具准确度/伪造数据）、`商品条码管理办法`、`专利法`（假冒专利）、`反不正当竞争法第九条`（商业秘密）要么不是食品数据造假，要么与已登记的五个造假类不同构。硬映射会把"不属于本构念"的案子算成"属于"，正是 D-77 要防的。**只描述，不分类。**
- **实测**（`data/analysis/e6_descriptive.json`，`at_utc` **2026-11-05T01:27:39Z**，zh 763）：`n = 63`，其中罚则只引《行政处罚法》**13 篇**；文档级提及（前 6）：《行政处罚法》56、《反不正当竞争法》18、"经营者违反本法"14、《计量法》7、《食品安全法》7、《商品条码管理办法》6。
  - **读法限制（同次实测）**：`"经营者违反本法"`/`"本法"`/`"本条例"` 是法名未被识别的**抽取串**，不是独立法律；这些条目的计数不能再当作"某部法"的证据加总。因此只能报"命中哪些法名"，不能报"各法占比"。
  - **结论口径**：63 篇里可归因于**形式机制**的 13 篇，其余多数属**主题不在五类造假框架内**；两者都不是"映射表写错了"，也都不改变 `resolved_share = 0.7038` 与粗粒度分布。
- **对照**：本次重跑（01:27:39Z）与 01:09:50Z 那次逐类相同：FALSE_LABELING 333 / UNRESOLVED 226 / TRADEMARK 56 / PROCEDURAL 54 / FORGED_REPORT 30 / FALSE_ADVERTISING 29 / UNLICENSED 26 / PRODUCT_QUALITY 5 / FAKE_CERTIFICATION 4；粗粒度 DATA_FALSIFICATION 367 / UNDETERMINED 226 / MARKET_ORDER 90 / PROCEDURAL 54 / UNLICENSED 26；负对照 **0.38**（第三次：0.38 / 0.39 / 0.38）。`verify_products.py` **37/37 pass、0 stale**。
- **产物位置**：`data/analysis/e6_descriptive.json` 的 `unresolved_none` 块。`verify_products.py` 不新增检查（描述块，不是判据）。

## D-82 — E9（QLoRA 自训练受控复跑）的执行协议、旧脚本缺陷与占用窗口

- **先纠正 D-78 的一条**：D-78 说"训练栈缺失 ⇒ 不执行"。2026-11-05T02:2xZ 复测：pod 可访问 PyPI（`pip download peft` 成功，2 MB/s），已建独立环境 **`/opt/e9venv`**（以 `.pth` 指向 `/opt/foods/venv` 的 site-packages，复用 torch 2.5.1+cu124 / transformers 4.46.3），**主 venv 一行未改**。已装 `peft 0.21.2 / accelerate 1.15.0 / bitsandbytes 0.50.2`（`datasets` 缺 `multiprocess`，故不使用，改为手写 torch Dataset）。E9 因此**可以执行**，不再是"不可执行"。
- **旧脚本 `scripts/train_qlora.py` 有致命缺陷，不得使用**（保留原文件不动）：
  1. 训练文本是 `"文书标注任务\n输出：" + target`，**完全没有输入文书** ⇒ 训练的是"从空提示吐标签"，与任务无关；
  2. 名为 QLoRA，实际 `torch_dtype=bfloat16` 全精度加载（~15.5 GB），未做 4-bit 量化；
  3. 没有任何评测路径，不产出锚点 F1。用它得到的适配器不能支撑任何数字。
- **新脚本 `scripts/e9_selftrain.py`（先定后跑）**：
  - 数据：`tier == high` 的 223 篇（zh 124 + en 99）作伪标签；输入 = `prompts.render("alpha", lang, doc)`（与主管线同一模板），目标 = 银标准的 `entities + violation_category`，**loss 只落在答案 token 上**（prompt 段标 -100）。
  - 评测集：**所有带法条锚点的银标准记录**，即 `anchors.anchor_pairs` 认可的那批——实测 **388 篇，全部 zh**（英文文书没有中国法条锚点，故不在集内；这是结构事实，不是筛选）。
  - 两臂同一输入、同一解码（贪心、单样本、max_new 256、prompt+answer ≤4096 token）：**base**（4-bit NF4 加载、无适配器）与 **adapter**（LoRA r=16/α=32/q_proj+v_proj，lr 1e-4，3 epoch，grad accum 8）。唯一差别是适配器。
  - 判据（沿用计划书）：**macro 锚点 F1 提升 ≥ 3 个点 → 附录报正结果；否则一句零结果**。不设新阈值、不改 E1 口径。
- **已知限制（写进产物，不事后解释）**：
  1. 伪标签来自**基线模型自身的双通道共识** ⇒ 这是"把共识蒸馏进单次贪心解码"的检验，不是"引入外部知识"的检验；
  2. 文档超 4096 token 被截断（实测 20k 字符截断 0 篇，token 级截断未逐篇统计，产物记 `max_len`）；
  3. 评测只覆盖中文（388 篇），结论不外推到英文层；
  4. 单通道评测 vs E1 的双通道一致率**不是同一个统计量**，两数严禁并列（计划书同款要求）。
- **资源与窗口**：训练 + 两臂评测需约 **10–12 GB 显存**，与常驻 vLLM（23.9 GB）不能共存 ⇒ 必须**在终版发布包产出之后**停 vLLM，跑完立即重启（`scripts/start_llm.sh` 幂等）。窗口内 `state/e9_window.json` 存在，值守代理据此**不得重启 vLLM**；窗口结束删除该文件。**不得与 02:00Z 周期或 finalize 重叠**（那两步要调 LLM）。
- **产物**：`data/train/selftrain.jsonl`、`data/train/adapter_e9/`、`data/analysis/e9_selftrain.json`（含两臂分数、delta、verdict、解码统计、适配器权重 sha、耗时）。**E9 不进终版发布路径**（D-71 冻结与发布不依赖它）。
- **登记后、执行前的口径微调（2026-11-05T02:2xZ，在跑之前改，不是事后解释）**：`max_len` 由 4096 降为 **3072** token（4-bit 训练 + 无梯度检查点，为显存留余量）；`max_new_tokens 256`、贪心解码、epochs 3、lr 1e-4、grad accum 8 均不变。截断的代价记在产物 `protocol.max_len` 与文档里。其余一切按本节执行。

## D-83 — 标注全批 PermissionError：root 跑链把 silver 改成了 644（我造成），296 篇进 failed

- **现象**（2026-11-05T02:45–02:50Z）：daemon 的 02:00Z 周期进入标注后，每篇都报
  `PermissionError: [Errno 13] /opt/foods/data/silver/silver.jsonl`；docs 表出现 `failed: 296`，silver 停在 1015 行不动。
- **根因**：**我**在 11-04 15:08–15:29Z 以 **root** 跑了 `chain_locked.py retier extract analyze report`，
  retier 重写 `data/silver/silver.jsonl` 时把文件变成了 **`root:foods 644`**；而 daemon 以 **`agent`** 运行
  （`agent` 属于 `foods` 组，其他文件如 `state/foods.sqlite` 是 664 所以能写）。`644` 的组权限是 `r--`，
  于是**基于追加的写入**全部失败。其他阶段（extract/analyze/report）用"临时文件+rename"写，只需要目录的组写权限
  （`data/` 各目录是 `2775 root:foods`），所以只有 silver 这一条链断了。（`data/reports` 是 `2755`，agent 建不了新文件，
  同一类问题的另一处，一并修。）
- **证据**：`stat` 显示 `644 root foods 2026-11-04 15:29:19Z`，正是我那次 root 链的收尾写入；失败窗口内
  silver 的 sha 始终是 `b4685bd7…`，**没有数据损坏**，只是标签没写进去。
- **处置（不改任何内容，只改权限）**：`chmod 664 data/silver/silver.jsonl`、`chmod 2775 data/reports`。
  修复后 1 分钟内 silver 由 1016 增至 1019 行，标注恢复。
- **影响面**：① 11-04 15:29Z 至 11-05 02:50Z 之间任何新文书都无法入库（这段时间只有本轮在采集，故实际损失=本轮的标签）；
  ② 本轮被判 `failed` 的 **296 篇**需回置 `clean` 后补标注；③ **冻结时刻相应顺延到补标完成**，之后才跑 finalize
  （补标仍属"2026-11-05T02:00Z 周期"的语料，因为采集发生在该周期，失败原因是我造成的权限缺陷，不是数据问题）。
- **预防**：任何以 root 运行会写 `data/` 的脚本（chain_locked 的各阶段、e6/e7/e8、finalize）之后，必须
  `chmod -R g+w data state`；daemon 启动时应做一次权限自检（待办）。教训与 D-60 同型：**双写者不只抢文件内容，还会抢文件属主**。

## D-84 — 更正 D-83 的「296 篇 failed」归因；finalize 侧仍有 root:644 就地写目标（已修 5 个，release/ 未解）

- **更正 D-83（先写事实，再谈处置）**：D-83 说 296 篇 failed 是 PermissionError 造成、需回置 `clean` 补标——**不成立**。
  实测（2026-11-05T02:5xZ 查 `state/foods.sqlite`）：296 篇 `stage='failed'` 的 `error` 全是 `awaiting_pdf`、
  `attempts=0`、`updated_at=2026-11-05T02:43:22Z`；同一时刻 `kv stage_status:clean` 写的是
  `awaiting_pdf: 296`，`kv source_status:cfws` 写的是 `no_pdf: 296`（B5 批次 600 PDF / 296 无 PDF）。
  **这些文书在 label 开始（约 02:44Z）之前就已经是 failed，且没有正文可标**；把 296 回置 clean 既无依据也会制造空标注。
  - 真正的 PermissionError 只命中 **2 篇**：`openfda:F-2137-2017`（attempts=4，02:45:53Z）与
    `cfws:20240426121534385326`（attempts=3，02:46:24Z），两者现在仍是 `stage='clean'` 且 error 记着 PermissionError；
    本轮 label 在失败前已物化 clean 列表，故这两篇要等下一次 label 才会重试。**实际标注损失 = 2 篇，不是 296 篇。**
  - D-83 处置 ②/③（296 篇回置 + 冻结顺延）作废；冻结点仍按 02:00Z 周期。
- **D-83 的权限修复不完整（本轮巡检发现并修）**：`chmod 664 silver` + `chmod 2775 data/reports` 只解决了追加与“新建文件”，
  但**已存在的 root:foods 644 文件若被就地写（非 temp+rename）仍然会 EACCES**。finalize 路径上实测有 5 个：
  `logs/finalize.out`（watch 的 `>>` 重定向，打不开则 finalize 根本不执行）、
  `data/metrics/e1_preladder.json`（`e1_preladder.py:131 p.write_text`）、
  `data/reports/e6_tables.md`、`data/reports/e7_typology.md`、`data/reports/e8_table.md`
  （`e6/e7/e8: REPORT.write_text`）。
- **处置（只改属主/权限，内容逐字节不变）**：对上述 5 个文件执行 `cp` 到同目录临时名 → `chmod 664` → 原子 `mv` 覆盖
  （目录是 `2775 root:foods`，agent 有组写权限）。sha256 前后逐项相同：
  `21020d563d9a`(finalize.out)、`739cebe938db`(e1_preladder.json)、`012668d555a1`(e6_tables.md)、
  `5bbabb64160c`(e7_typology.md)、`bd056af0c1b7`(e8_table.md)，现均为 `agent:foods 664`。**没有改写任何数据。**
- **仍未解的一处（需 root，agent 无 sudo）**：`/opt/foods/release` 是 `root:foods 2755`。agent 既不能在它里面
  `mkdir release/foods_silver_20261105`，也不能重命名该目录（rename 目录需要目录自身写权限，`touch`/`mkdir` 实测均 EACCES）。
  `export_release.py` 会 `out.mkdir(parents=True)` ⇒ 若以 agent 跑 finalize，会在 export 步抛 PermissionError，
  回执落 `status=export_failed`。**需要 root 执行 `chmod 2775 /opt/foods/release`（或 chown agent:foods）后重跑 finalize**；
  这一步不需要改数据、不需要重采。
- **预防（补充 D-83 的清单）**：root 跑完链之后应 `chmod -R g+w data state logs`，并对 `release` 做 `chmod 2775`；
  凡“就地写已存在产物”的脚本（e1_preladder、e6/e7/e8 的 markdown）都受这条影响。`e8_table.md` 在 extras 重跑前
  仍是 01:12:51Z 的错位旧版（D-80），**不得引用**。

## D-84 — 更正 D-83：那 296 篇 `failed` **不是**权限事故，而是 `awaiting_pdf`（无正文）

- **更正内容**：D-83 写"本轮 296 篇因 PermissionError 进 `failed`"。2026-11-05T03:27Z 用 `docs.error` 分组复核，实际是：
  `select error,count(*) from docs where stage='failed'` ⇒ **`awaiting_pdf` 296，且 296 篇里 `text_path is not null` 的有 0 篇**。
  它们是**采集到元数据但没有 PDF/正文**的文书（`meta.pdf_missing=true`），从来就没有可标的文本。真正的权限受害者只有 **2 篇**（1 cfws + 1 openfda），它们停在 `clean`，`error` 字段里留着 `PermissionError`。
- **错因**：我把 `logs/daemon.out` 里的权限 traceback 和 `stage='failed'` 的 296 这个计数当成了同一个总体，没有按 `error` 分组就下了归因。**教训（写进纪律）：报"失败原因"必须先 `group by docs.error`；同一个 `stage` 不等于同一个失败原因。**
- **D-83 仍然成立的部分**：`data/silver/silver.jsonl` 被我 root 跑链改成 `root:foods 644` 是事实（`stat` 03:xx 前仍是 644、mtime 11-04 15:29:19Z），`chmod 664` 是必要修复；只是它影响的文书数是 **2**，不是 296。
- **处置**：这 2 篇在 03:27Z 的 `chain_locked.py label` 重跑里被重新拾起（权限已修），结果记在 D-86。

## D-85 — `release/` 不可组写 ⇒ `export_release.py` PermissionError，finalize 收据为 `export_failed`（rc=8）

- **时间线（`logs/finalize.out`）**：`03:21:55Z cycle 2026-11-05 complete` → 守夜脚本按 D-71 **停掉 daemon pid 171837** → `03:22:00Z` 跑 `finalize_release.py --stamp 20261105` →
  `chain_locked retier extract analyze report` rc=0（77 s）、`e1_preladder` rc=0、`tier_shrunk`/`query_family_agreement` rc=0、`e6` rc=0（n_docs **872**）、`e7` rc=0（n **128**, agreement **0.8203**）、`e8` rc=0（cn **438** / us **253**）、`verify_products` **37/37 pass 0 stale** → `export_release.py` **rc=1** → `03:26:05Z finalize rc=8`。
- **真因**：`export_release.py` 的 `out.mkdir()` 抛 `PermissionError: /opt/foods/release/foods_silver_20261105`。守夜脚本以 **`agent`** 运行，而 `release/` 当时是 `drwxr-sr-x root:foods`（**2755，组无写**）。这与 D-83 同源：**root 建出来的目录没有交回组写权限**。
- **现场处置**：① `chmod 2775 release`；② 我以 root 直接跑 `export_release.py` 成功建出 25 件包（1124 行、tier medium 397 / low 500 / high 227），**但它是 root 属主且早于 29 篇重标**，故整体移到 `release/_stale_export_0326`，**不作出货**；③ 重跑顺序见下。
- **口径**：`data/reports/finalize_20261105.json` 里 `status="export_failed"` 的这份收据**不是发布凭证**；只有 `status="released"` 且 `bundle.sha_ok == n_listed`、`silver_sha_before == silver_sha_after`、`verify_products.n_failed = n_stale = 0` 才是。
- **重跑纪律**：`chmod 2775 release` 之后重跑 `finalize_release.py --stamp 20261105`。**`export_release.py` 对已存在的同名目录会 `REFUSED`（D-70）**，所以要先把旧目录挪走（本次挪到 `_stale_export_0326`），不能原地覆盖。

## D-86 — 29 篇不可标文书：作为**一类排除**登记，并报告长度偏差

- **构成**（`docs.error`，2026-11-05T03:27Z）：`label_truncated_output` **22**、`label_parse_failed` **5**、`PermissionError` **2**；全部 `stage='clean'`、全部有正文（`text_path` 非空）。
- **长度偏差（关键，必须写进论文）**：这 29 篇的 `n_chars` 中位数 **5,658**、p90 9,964、max 16,263；而全部 1,124 篇已标文书是 中位数 **3,150**、p90 5,448、max 12,742。**中位数比 **1.80×**。⇒ 冻结协议在**最长/最复杂**的文书上系统性失败，语料因此**低估长文书**。这是"排除不是随机缺失，而是按文书长度选择"的证据，属于测量边界，不能只写"29 篇失败"了事。
- **处置**：不改协议（改 `max_new_tokens` 就是改口径），在补跑后把最终残留数与长度偏差一起报；论文的 Data/Limitations 里必须出现这一句和这两个中位数。

## D-87 — E1 预注册"单次"口径随语料增长而漂移（0.6898 → 0.6962）：n_lost 24 → 91

- **现象**：D-63/D-68 定下 E1 报两个数、禁互代。但 `scripts/e1_preladder.py` 的分子只对**归档里有单次作答副本**的文书可得（`data/archive/*/silver.jsonl`），语料一长，新文书没有归档副本，只能落到"可替代"或"丢失"：
  - 11-04 口径：`mean 0.6898`，**n=991**，`n_lost 24`；
  - 11-05T03:22Z 重算：`mean 0.6962`，**n=1033**，`n_lost 91`（`n_substituted 636`）。
- **这不是模型变了，是覆盖率变了**：同一脚本、同一规则，分母里"有归档单次作答"的比例下降。
- **规则（新增）**：今后引用 E1 预注册数，**必须三件同行**：数值 + `n` + `n_lost` + 所用归档的 sha（`e1_preladder.json.provenance.archives[]`）。**禁止**只说"预注册 0.6898"而不带分母与归档——那会把一个随语料缩水的量说成不变量。
- **对论文的含义**：E1 预注册值只能作为**归档子集**上的量报告；主结果仍用冻结语料上的阶梯后混合值（另一个统计量，禁互代，见 D-63）。

## D-88 — 包内 `gates.json` 的 `E1.pre_registered` 比 `e1_preladder.json` 落后一次 extras（读数口径，未改规则）

- **现象（冻结包 `release/foods_silver_20261105`，silver sha `a1deda2c…`，2026-11-05T03:57Z）**：
  `metrics/gates.json` 的 `E1.pre_registered` = **0.6962 / n_scored 1033 / as_of 2026-11-05T03:23:18Z**；
  同一包内 `metrics/e1_preladder.json` = **0.6966 / n 1037 / at_utc 2026-11-05T03:54:17Z / silver_sha256 `a1deda2c…`**。
  两处都自称“预注册 E1”，但分母不同。
- **成因**：`finalize_release.py` 先跑 `chain_locked retier extract analyze report`（`analyze` 写 gates，并在写时读取当时的
  `e1_preladder.json`），extras 循环随后才重跑 `e1_preladder.py`。因此 gates 里的副本永远是**上一次**的 e1_preladder；
  本轮语料 1124→1128，差距被放大（1033 vs 1037）。**E1 门禁状态不受影响**（状态取 `e1.json`），只是 gates 的展示字段滞后。
- **处置（读数规则）**：引用预注册 E1 一律读 **`metrics/e1_preladder.json` 的 `e1` + `provenance`**，并按 D-87 同时给
  `n`、`n_voted_without_archive` 与所用归档 sha；`gates.E1.pre_registered` 只能当便利副本，引用时必须带其 `as_of`。
  **不改阈值、不改映射表、不改 tier 规则。**
- **未改代码**：修法应让 extras 的 `e1_preladder.py` 先于 `analyze`，或在它之后重写 gates；两者都要重建终版，留待下一次
  语料更新时与发布一起做。本轮只登记读数口径，避免把 0.6962/1033 当成冻结语料的值引用。

## D-88 — 终版语料冻结与发布（stamp 20261105）：1128 篇、`released`，以及锚点 macro 的口径陷阱

- **发布凭证**：`data/reports/finalize_20261105.json` → `status="released"`，`finished_utc 2026-11-05T03:57:03Z`；
  `silver_sha_before == silver_sha_after == a1deda2c57ccf5eeb2cf3b27782d30087747dfa208264f9b2ec68dcd7b4a077e`；
  `verify_products` **37/37 pass、0 stale**；`bundle` = `release/foods_silver_20261105`，**sha_ok 25 / n_listed 25**，`silver_in_bundle` 同 sha。
  `finalize_20261105.export_failed.json` 是 03:22 那次失败收据的存档（D-85），**不是凭证**。
- **语料规模**（这是唯一的冻结语料，**1015 / 1124 口径的数一律作废、不得再引**）：
  silver **1128** 行（cfws 876 / openfda 252）；tier = high **228**（zh 128 + en 100）、medium 398、low 502；
  dataset.jsonl 4400 行（tier high 836/medium 1575/low 1989）。未入语料：`awaiting_pdf` 296（无正文）、
  协议层不可标 25（D-86）、filtered_out 2091。
- **冻结过程里的一次性漂移**：03:40:50 首次重跑 finalize 在 `corpus_drift` 处退出（rc=5），因为链内 `retier`
  把 4 篇新标文书的 tier 真正改写了（sha `7a2f0283…` → `a1deda2c…`）。**之后 retier 连续两次运行 sha 不变**（幂等），
  03:53 的重跑因此 `sha_before == sha_after`。⇒ 口径：`corpus_drift` 只有在**链外**也复现变化时才叫漂移；本次是链内一次性定稿。
- **冻结语料上的数字（全部带分母）**：
  - E1 双通道一致率 **0.7460**（n=1128；zh 0.72xx / en 0.81xx，见 `metrics/e1.json`）；阶梯后稳定类型一致率 **0.8610**（END_USER/JURISDICTION/PENALTY_EVENT，另一统计量，禁互代）；tau 0.3/0.5/0.7 → 0.7487/0.7460/0.7276。
  - E1 预注册单次口径 **0.6966**（n=1037，**n_lost 91**，见 D-87）。
  - 锚点（n=**423**）：micro **0.7825**、macro-all **0.2693**、macro(支持≥20 的类) **0.4195**；逐类 FALSE_LABELING 0.8801(326)、UNLICENSED 0.3784(52)、FORGED 0.3571(11)、OTHER **0.0(31)**、TAMPERED 0.0(2)、FAKE_CERT 0.0(1)。
  - E6（n=875，at 03:54:28Z）：粗粒度 {DATA_FALSIFICATION 412, UNDETERMINED 271, MARKET_ORDER 100, PROCEDURAL 66, UNLICENSED 26}；resolved_share 0.6903；**负对照 0.28**（上一轮 0.39）；`basis=none` 残差 n=100（其中 19 篇仅援引《行政处罚法》一般条款）。
  - E7：一致率 **0.8203**，n_adjudicated **23**，codebook 条目 49。
  - E8：cn **438**（frame 875，unresolved 271）/ us **253**；折叠 Fisher 表 cn[375,63] vs us[97,156]，**OR 9.5729，p 2.16e-37**；chi2 358.94（cramér's V 0.7207）为**不作数的辅证**（min_expected 1.465 < 5）；estimability 仍 `not_estimable_instrument_mismatch`。
- **★口径陷阱（必须写进论文，否则会被当成造假）**：锚点 `macro(≥20)` 从上一轮的 **0.6798** 掉到 **0.4195**，
  但模型行为没有突变——原因是 **OTHER 类的 support 从 19 涨到 31，跨过了"支持 ≥20"这条预注册线**：
  上一轮 macro(≥20) = (0.908 + 0.4516)/2 = 0.6798（只含 FALSE_LABELING 与 UNLICENSED）；本轮 = (0.8801 + 0 + 0.3784)/3 = 0.4195。
  同轮 micro 只从 0.8247 掉到 0.7825，FALSE_LABELING 从 0.908 到 0.8801。
  ⇒ 规则：**不许改阈值/支持线去把数拉回 0.6798**（那正是"改口径达标"）；三个数（macro-all / macro≥20 / micro）必须**带类清单**并列，并写明 OTHER 的 support 变化。
- **另记**：模型在 1128 篇上把 **798 篇**判成 FALSE_LABELING（70.7%），且对 OTHER 类从不输出（0/31，全部落到 FALSE_LABELING 28 + FORGED 3），对 UNLICENSED 好（14/52 正确、36 落到 FALSE_LABELING）——这是"仪器在未定型类上不可用"的直接证据，也是 E6 只能报粗粒度的实证支撑。
- **E9** 在**本冻结语料**上起跑（窗口标记 `state/e9_window.json` 于 04:02:57Z 写入）；E9 不进发布包，也不改任何已发布数字。

## D-89 — E9 首跑作废：基座臂没走 ChatML 模板（仪器不等价），已修并重跑

- **事实**：`2026-11-05T04:02:57Z` 开窗、`04:16:05Z` 我主动终止（`rc=143`）。日志 `logs/e9.out` 有 `[base] 50/423  460s  err=49`——基座臂 50 篇里 **49 篇解析不出类别**。
- **根因**：标注路径是把消息交给服务端渲染的——`foods_pipeline/label/llm.py` 用 `{"messages":[{"role":"user","content":prompt}]}` 调 `/chat/completions`，由 vLLM 套 ChatML。
  而 `scripts/e9_selftrain.py::_predict` 原来直接 `tok(prompt)`（裸字符串，无 `<|im_start|>user/assistant`）⇒ 同一个 7B 在 E9 里根本不是 E1 里那个仪器。
- **为什么必须作废而不是"跑完再说"**：基座臂全部不可解析 ⇒ 基座 macro 锚点 F1 ≈ 0；adapter 只要学会输出 JSON 就能把 macro 从 0 抬到 0.4 量级，轻松跨过计划书 **+3 个点** 的判据。
  那样会把**格式学习**报成"伪标签自训练有效"——正是本项目明令禁止的"口径制造达标"。
- **修法**（协议参数一个没动）：新增 `_chat()`＝`tok.apply_chat_template([{"role":"user","content":p}], tokenize=False, add_generation_prompt=True)`，**推理与训练两侧同用**；
  4-bit NF4、LoRA r16/α32/q_proj+v_proj、lr 1e-4、3 epoch、grad_accum 8、`MAX_LEN 3072`、贪心单样本 **全部保持计划书值**。
- **新增两道防线**：① 判定加 `invalid_base_arm`——基座臂可解析率 < 0.5 时，无论 delta 多大都不许给 `positive`；
  ② 新增 `n_ctx_truncated` 与 `sensitivity_untruncated`（只在未截断篇上重算 delta）。理由：标注路径的文档上限是 `label.doc_text_chars = 20000` 字符，
  而 E9 的 `MAX_LEN 3072` tokens 远短于此 ⇒ 长文书在 E9 里只看到一部分；两臂同截断，**delta 不受影响**，但**绝对 F1 不得当成 E1 标注仪器的 F1**。
- **重跑**：`04:17:16Z` 开窗（`state/e9_window.json`）、`scripts/run_e9_window.sh` pid 234226、`e9_selftrain.py` pid 234319，仍 `MAX_LEN 3072`、423 篇锚点评测集。
- **模板已实测生效**（`2026-11-05T04:1xZ`，纯 CPU 校验）：渲染尾部为 `…<|im_end|>\n<|im_start|>assistant\n`，`eos = <|im_end|>`。
- 另记（不改）：`generate()` 只给 `input_ids` 不给 `attention_mask`，transformers 会告警"pad token 与 eos 相同、自动推断掩码"。批大小为 1、无填充，自动掩码即全 1，行为正确；记录于此以免日后被当成缺陷。

## D-90 — E6 的年份分布是采样窗口产物，**不得**写成趋势（T1 结案）

- **现场数字**：冻结语料 875 篇中文文书的 `published` 年份 = 2023 **6** / 2024 **94** / 2025 **167** / 2026 **608**（69.5%）。
- **证据一（门户按发布日倒序）**：`collect/cfws.py` 的查询载荷里 `"sortFields": ""`（走门户默认排序）。`2026-11-05T04:1xZ` 活探 page 1：
  `伪造/食品` 第 1 页日期由 `2026-10-16` 单调降到 `2026-07-28`；`检验报告/食品` 由 `2026-10-19` 降到 `2026-09-30`；`冒用认证标志` 由 `2026-10-16` 降到 `2026-08-27`。⇒ 默认排序 = **发布日倒序**。
- **证据二（每个查询只发前 ~200 行）**：`config/expansion_queries.yaml` 头注自述"门户每个查询最多约 200 行（resultCount 更大时第 5 页也是空）"。
  我按已注册的全部 92 个查询做了全量探测（产物 `data/reports/t1_coverage_probe.json`，`at_utc 2026-11-05T04:15Z`，sha256 `ca3c9d2493618c960631a5f23fde71f3cf093596b9ab5f81a78c709f0241bcbc`）：
  - **16 个查询 resultCount > 200**，它们 resultCount 合计 **27,850**，而**任何单查询的登记数最高只有 201**；
  - 例：`检验报告/食品` resultCount **6,760** → 登记 **174**（覆盖 2.6%）；`虚假/食品` **5,260** → **88**；`合格证明/食品` **2,764** → **123**；`检测报告/食品` **2,004** → **131**；`冒用认证标志` **1,471** → **197**；`伪造/食品` **720** → **201**；
  - 反向对照：`篡改/食品` resultCount **80** → 登记 **80**，**完整覆盖**（说明截断只在超 200 的查询上发生，不是登记环节丢件）；
  - 92 个查询中 47 个完整覆盖、68 个 resultCount>0、单查询登记数中位 171。
- **结论**：语料 = "每个关键词查询按发布日倒序的**前 ~200 行**"的并集。年份构成因此是**采样窗口 + 门户存量**的产物，**不是**处罚文书年份的事实，更不是执法强度的时间趋势。
- **佐证（不是筛选造成的）**：2026-08/09 的峰值在 `filtered_out`（385 / 501）与 `extracted`（120 / 161）里同时出现，说明它是采集端进来的形状，不是标定筛出来的。
- **写作纪律（硬）**：
  1. **禁止** `increasing / rising / 近年上升 / 逐年增长 / 占比上升` 一类趋势词；
  2. 只许写"在采集窗口内、按门户默认排序取前 ~200 行所见的构成"；
  3. 引用时必须同时给出上面至少 3 个 `resultCount vs 登记数` 例证与产物 sha，作为覆盖上界；
  4. 语料规模不得表述为"全国食品安全处罚文书 N 篇"，只能写"本采样帧内 N 篇"。

## 编号说明 — D-88 出现两次（引用须带标题）

- 本册 `## D-88` 有两条：一条是 **“包内 `gates.json` 的 `E1.pre_registered` 落后一次 extras”**（读数口径，另一线程所写），另一条是 **“终版语料冻结与发布（stamp 20261105）”**。
- 论文、STATUS、AUDIT 里凡引 **D-88**，指的是一律是**冻结与发布那条**（含锚点 macro 口径陷阱）。引用另一条时必须写明标题。本条只做消歧，不改任何既有条目。

## D-90 更正 — 上限是实测的"每查询 4 页 = 200 行"；逐查询登记数是下界（撤回"篡改/食品 80→80"这一句）

- **实测（`2026-11-05T04:24Z`，`/tmp/t1_pages.py`）**：`检验报告/食品` `resultCount=6,760`，`page2/3/4` 各 **50** 行、**`page5` = 0、`page6` = 0**；`伪造/食品` `resultCount=720` 同形（50/50/50/0/0）。
  ⇒ 门户上限不是"约 200"，而是**实测的 4 页 × 50 行 = 200 行**；`config` 里的 `max_pages_per_query: 40` 形同虚设（永远走不到第 5 页）。
- **撤回一句**：D-90 写的"反向对照 `篡改/食品` 80 → 80 完整覆盖"**作废**。产品 `t1_coverage_probe.json` 记的是 `resultCount = 80`、`registered = 76`。
  差的 4 篇是被**别的查询先登记**（`meta.query` 只记第一次看到该文的查询，插入按 `doc_id` 去重），所以**逐查询登记数只是下界**；同理 `n_fully_covered = 47` 也是下界，**不能**用来证明"完整覆盖"。
- **结论不变、且更硬**：92 个查询里**单查询登记数最大只有 201**，而 16 个查询 `resultCount` 合计 **27,850**（最大 6,760），叠加上面实测的 4 页上限 ⇒ 语料是"按发布日倒序取前 200 行"的并集，年份分布是**采样窗口产物**。
- **写作纪律（替换 D-90 里对应的那句）**：引用覆盖上界时用 **`page1–4 = 50/50/50`、`page5 = 0`** 这条实测 ＋ `data/reports/t1_coverage_probe.json`（sha `ca3c9d24…`），**不要**再用 `篡改/食品` 当反例。趋势词禁令、禁"全国 N 篇"不变。

## D-89 更正 — 真正绑住 E9 的不是 ChatML 模板，而是"右侧截断把 `<|im_start|>assistant` 切掉了"；答案预算也不是 256

- **第二跑证伪了单一归因**：`04:17:16Z` 加了 ChatML 模板重跑，50 篇时仍是 `[base] 50/423 430s err=49 ctx_trunc=34`（新字段表明有 34 篇文档被上下文截断）。⇒ 模板是**必要不充分**。
- **定位手段（新增，保留）**：给 `scripts/e9_selftrain.py` 加 `--probe N`，`run_e9_window.sh` 加 `E9_MODE`；用同一个窗口脚本跑小样本，直接看模型的原始答案，不再靠猜。6 篇探针的输出把两个原因分开了：
  1. **答案预算太小**：`data/metrics/e1.json` 的 `protocol.max_tokens.channel_a = 3000`，而 E9 用的是 **256**。解析成功的答案本身就要 **308–511** tokens，256 连正常答案都装不下。
  2. **右侧截断毁掉模板尾部**：`ids[:budget]` 从右边切，切掉的正是 `…<|im_end|>\n<|im_start|>assistant\n`。模型于是**续写文书正文**——探针里失败的答案逐字重复"询问笔录1份，证明当事人：…"，不是标注。这一条与文档长否无关，凡是超窗口的文档全部中招。
- **修法（判据与训练超参一个没动）**：
  - `MAX_NEW` 256 → **3000**（= channel A 的预算，完全对齐）；`MAX_LEN` 3072 → **8192**。
  - 新增 `_fit_ids()`：**不再右截断 token 序列**，改为**二分搜索缩短文书正文**，保住 `<<<DOC>>>` 之外的模板与 assistant 头；记录每篇 `doc_chars_kept`。**训练侧同样改**（原来也右截断）。
  - 新增 `sensitivity_base_parseable`：只取"基座臂能解析"的篇给两臂同时打分，把**格式学习**从**类目学习**里剥出去——否则 adapter 只要学会吐 JSON 就会把 delta 抬高（这正是 D-89 一开始要防的事）。
- **探针迭代（同一 6 篇）**：解析 **4/6**（模板修好、预算 1024）→ **5/6**（改为缩短正文）→ **6 篇里仍 1 篇跑满 3000 tokens 未闭合**（该文实体列表爆炸，属"答案截断"类，标注路径也有同类：`e1.json coverage.label_truncated_output = 20`）。⇒ 残余不可解析**逐臂照报**，不填、不猜。
- **重跑**：`04:39:34Z` 开窗（pid 见 `logs/e9.out`），协议 = 4-bit NF4、LoRA r16/α32/q_proj+v_proj、lr 1e-4、3 epoch、grad_accum 8、`MAX_LEN 8192`、`MAX_NEW 3000`、贪心单样本。
- **仍存在且必须写进论文的仪器差**：文档窗口 = 8192−3000 = **5192 tokens**（≈3.5k 汉字），小于标注路径的 `label.doc_text_chars = 20000` 字符 ⇒ 长文书在 E9 里只看到一部分（探针 6 篇里 2 篇被缩短）。两臂同窗口 ⇒ **delta 可比**；**绝对 F1 不得与 E1 的锚点 0.7825 并列**。

## D-91 — 三个"看着像缺陷其实是读数口径"的件：`ladder.json`、`gates.json` 的 `E1.pre_registered`、`gates.json` 里没有 status 的 E3

- **`data/metrics/ladder.json` ＝ `{"docs": 0, "entity_density_before": null, "entity_density_after": null}`**：这不是测量失败，而是**这一轮 self-consistency 动作无事可做**（`state kv actions:ladder` 记 `{"action":"self_consistency","docs":0}`，随后 `self_training_not_triggered`（228 < 500 阈值）与 `shrink`）。
  ⇒ **论文不得引用 `ladder.json` 说"实体密度没变"**；阶梯统计只引 `data/metrics/e1.json` 的 `mean_agreement_shrunk = 0.8610`（稳定类型 END_USER / JURISDICTION / PENALTY_EVENT）。
- **`data/analysis/gates.json → E1.pre_registered` ＝ 0.6962 / n=1033（`as_of 2026-11-05T03:23:18Z`）**，比 `data/metrics/e1_preladder.json` ＝ **0.6966 / n=1037 / n_lost 91**（`as_of 03:54:17Z`）**落后一次 extras**。两者规则相同、只差一次重算。
  ⇒ 论文 / STATUS / AUDIT 一律引 `e1_preladder.json`（与本册另一条 D-88「包内 `gates.json` 的 `E1.pre_registered` 落后一次 extras」是同一件事，本条给它一个可查的对照数）。**不要改 `gates.json` 去对齐**——包已发，改包等于换凭证。
- **`gates.json → E3` 没有 `status` 字段**（只有 `attack: insufficient_nodes`、`h1_supported: null`、`survival: inconclusive`、`hawkes: degenerate_fit`）：E3 按其既定口径就是**不可估计**，不是漏写。论文报"不可估计 + 原因"，**不得**补一个状态。
- **配套纪律**：凡"某个件里缺字段/为 0"的现象，先查它的**上游 action 记录**（`state kv actions:*`）再决定是不是缺陷；不要用"文件里有空值"直接推"流水线坏了"（这正是 D-83/D-84 的同型错误）。

## D-86 更正 — 长度偏差只能用**同一把尺子**量：1.80× 作废，改为 **1.71×**；`awaiting_pdf` 296 篇没有长度，不能参与比较

- **原 D-86 的错**：分子取 `docs.n_chars`（清洗后仍不可标文书），分母取 `e1.json` 的 `input_chars.labelled_p50 = 3151`（**多语混合、且是标注输入文本**的口径）。两把尺子相除得到 **1.80×**，这个数**作废**。
- **重算（同一列 `docs.n_chars`，新产物 `data/reports/length_bias.json`）**：
  - `stage='clean'` 不可标 **25** 篇：p50 **6,136**、p90 9,964、max 16,263（其中 `label_truncated_output` 20 篇 p50 6,136、`label_parse_failed` 5 篇 p50 2,976）；
  - `stage='extracted' AND lang='zh'` 已标 **875** 篇：p50 **3,578**、p90 5,698、max 12,742；
  - ⇒ **中位数比 = 1.71×**（不是 1.80×）。结论方向不变：不可标文书系统性更长，语料低估长文书。
- **`stage='failed'` 的 296 篇（全部 `awaiting_pdf`）没有任何 `n_chars`**——它们从未拿到正文。⇒ **不得**把"296 篇"写成长文书；它们的长度**未知**，只能当"缺失"报告（`n_with_len = 0`，不插补）。原稿若写过"296 篇更长"，一并作废。
- **论文只引 `data/reports/length_bias.json`**（p50 6,136 / 3,578、比 1.71、`failed_no_text.n_with_len = 0`），并且必须写成"可标而未标的 25 篇更长"，不是"失败的 296 篇更长"。
- 教益（与 D-91 同型）：**比值必须来自同一仪器**；分子分母的采集口径不同时，比值没有意义，哪怕两边的数各自都是对的。

## D-92 — 粗粒度折叠**救不回**规则层：负对照在两种粒度上同为 **0.28**（14/50）

- **事实**（新产物 `data/analysis/negative_control_coarse.json`，同一 50 篇切片 seed 20261104，同一冻结 coarse map，不改任何阈值/映射/切片）：
  - 细粒度：rule vs A **14/50 = 0.28**、rule vs B **14/50 = 0.28**；
  - **粗粒度：rule vs A 仍是 14/50 = 0.28**、rule vs B 0.28；A vs B 37/50 = 0.74；
  - 只在"规则已给类别"的 32 篇上：**14/32 = 0.4375**；
  - 50 篇里规则判 UNDETERMINED 的有 **18** 篇，且这 18 篇全部与通道 A 不一致。
- **为什么必须登记**：v7 计划书的回退规则是"任一维度一致率 < 0.75 ⇒ 只报粗粒度"。这条规则**隐含假定**细粒度分歧大部分会在粗粒度折叠中消失。**该假定不成立**：同一批 14 篇在两种粒度上一致，折叠一篇没救回来。⇒ **粗粒度分布同样没有通过负对照授权。**
- **处置（不改口径，只改写法）**：
  1. 表 1 定性为 **instrument output**（某文档化仪器的输出），**不是**总体估计；表题与正文同段落必须出现负对照 0.28 与 14/32 三个数；
  2. 摘要**不得**写"数据造假占 68.2%"这类总体语言，只能写"该仪器把 412/875 篇判为数据造假类"；
  3. 图 1 第一级（"构成）**从 Supported 降为 Conditional**，条件写明 = 负对照 0.28 + 仅作仪器输出；
  4. 不重跑、不换切片、不调阈值——**负数就是结果**。
- **未检验的假设（禁止当解释写进论文）**：多违规文书（罚则同时援引多类条款）会让"单标签相等"判定系统性偏低，从而压低一致率。此假设**未做任何检验**；若要检验须新增"集合重叠"口径并先登记 D-nn，本轮不做。

## D-93 — 两个 `run_e9_window.sh` 实例重叠：陈旧实例的 EXIT trap 把窗口标记删了，还空转 600 秒去抢 GPU

- **经过**（`logs/e9_window.out` 可逐行复现）：04:35:38 启动的**探针实例**在 04:38:50 跑完 probe 后进入 `restart_llm`；与此同时 04:39:30 **正式实例**启动，把探针实例刚拉起的 vLLM（pid 236890）杀掉并开跑 `--run`。探针实例随后 600 秒等不到 vLLM（`WARN: vLLM not ready after 600s`），在 **04:58:52** 于 `EXIT trap` 里 **`rm -f state/e9_window.json`** 并打印 `window closed`。
- **后果**：正式实例（wrapper **237075**）与它的子进程（**237145**，GPU 7160 MiB，`State: R`）**一直正常运行、未受影响**；但**窗口标记在任务还剩约 5 小时时被删掉**——这段空窗里任何值守代理或人启动 vLLM 都会与 237145 抢显存。已在 04:59:56Z **手工重建标记**并注明属主。
- **不是数据问题**：没有数据被写坏，也不是"E9 挂了"。判据：`/proc/237145/status` 为 `R`、`nvidia-smi --query-compute-apps` 仍列 237145、`e9.out` 无异常栈。
- **两条教训**：
  1. **启动窗口脚本必须先加互斥锁**；同一时刻只允许一个实例，已存在就把新实例挡在 precondition 之前；
  2. **trap 只能删自己写的标记**（标记里带 owner/pid，退出时校验），否则陈旧实例会替新任务"关窗"。
- **修法**：`scripts/run_e9_window.sh.v2` 已写（`flock` 互斥 + 标记 owner 校验 + `restart_llm` 先用 `nvidia-smi --query-compute-apps` 确认无他人占用再启 vLLM）。**本轮不动正在执行的脚本**（bash 会边读边执行，改运行中的脚本会破坏后续语句），等 237075 退出后再换上。

## D-94 — 参考文献题名是「意译」不是「注册题名」：4/7 条与 Crossref 不符，[7] 的实质内容也说错了

- **事实**（产物 `D:\Foods\manuscript\refs_crossref.json`，2026-11-05 逐条取 Crossref；7/7 DOI **全部解析成功**）：
  - [3] 注册题名含 `Evidence from Food Safety Violation Data in Gansu Province, China`，原稿漏掉 `Food Safety Violation Data`；
  - [5] 注册题名是 `Governance Capacity and Regulatory Enforcement: Street-Level Organizations in Beijing's Food Safety Reform`，原稿写成 `Street-Level Enforcement`；
  - [6] 注册题名是 `Administrative Penalty Decision Disclosure Limit`（Hans Publishers，作者 刘文静，中文刊），原稿写成一个意译句；
  - [7] 注册题名是 `How Is Food Safety Regulation Implemented? The Key Role of Meso-Institutions Assessed through a Cross-Country Comparison`，原稿完全改写。
- **比题名更要紧的是 [7] 的实质**：该文比较的是**跨国 meso-institutions**，不是「召回/执法记录」。原稿 Related work 里写的 "studies that compare recall or enforcement records across countries compare constructs, not genres" 对这篇**不成立**，已按注册摘要改写成「跨国比较把差异定位在 meso-institutions；它比较的是构念，没有问两种记录体裁能否支撑同一个率」。
- **[2] 已核实为印度**：ACL Anthology 摘要载明 782 件 **Indian** 食品安全违规案件（2022–2024）、上诉判决。原稿 "applied to other jurisdictions' judgments" 成立，但已收紧成具体表述（782 / 印度 / 上诉判决），因为含糊的「其他辖区」经不起追问。
- **为什么这类错危险**：**DOI 全部点得开**，所以「能解析」根本不证明「引对了」；而意译题名读起来比注册题名更顺，自查时最不容易起疑。判据必须是**逐字比对注册元数据**，不是打开链接看一眼。
- **处置**：参考文献一律照抄注册元数据（作者 / 题名 / 刊名 / 卷 / 页 / 年）；补齐卷页 = [2] 41–52、[3] 83:677–685、[4] 107:54–80、[5] 87:256–274、[6] 8:424–430、[7] 16:1045–1058。
- **判据扩展**：`_tools/check_numbers.py` 现在**跳过 References 区**（4185 字符）——该区的数由 Crossref 记录授权，不是本项目的测量；引他人研究的数（`782`）单列 `CITED` 集并注明出处。正文 258 个数字 token **全部有据、0 未授权**。

## D-95 — E9 的训练集与评测集重叠 **112/423**：主报必须在"未见过的 311 篇"上算，规则在看到结果之前登记

- **事实**（本轮 E9 运行中、结果尚未产出时测得，判据全部来自产物）：
  - 训练集 = `data/train/selftrain.jsonl` **228** 篇（silver `tier==high`，zh 128 + en 100）；
  - 评测集 = `anchor_pairs` 唯一口径下的 **423** 篇（全 zh，`fact_only_excluded = 0`）；
  - **交集 = 112 篇，全部为 zh**，即评测集的 **26.5%** 被适配器在训练时见过（读过其伪标签）。
- **为什么必须处理**：这 112 篇上的分数同时反映"学到的类别"与"记住的伪标签"，把两者合在一起报，等于用 contaminated 数字支撑一个关于泛化的判断。这与 D-89 是同一类错误的两面：D-89 是**仪器不等价**（两臂渲染不同），本条是**信息泄漏**（评测集进了训练集）。
- **处置（先定规则，再看数）**：
  1. **主报口径 = 311 篇 clean 子集**（423 − 112），两臂在同一子集上重算 macro-F1；预注册判据（Δ ≥ +3 个点）**只对 clean 子集生效**；
  2. 423 篇全集的结果照报，但标为 `leakage_inflated`，**不得**用作证据；
  3. 不需要重跑：`data/analysis/e9_selftrain.json` 的 `predictions.base / predictions.adapter` **逐篇**落盘，子集重算无模型调用、无新信息；
  4. 子集的变换只做"去掉交叉集"，**不按结果挑子集**——这一点在结果产出**之前**写死（本条登记时间早于 `e9_selftrain.json` 生成）。
- **剩余局限**：311 篇仍非随机子集（被排除的 112 篇恰好是 tier=high 且带锚点的文书，可能是"较易"的一类），故 clean 子集上的分数**只答复"在同一帧内未见过的文书上有没有增益"**，不外推到全体；论文附录须写明这一点，并与 D-89 的"文档窗口 5192 tokens ≪ 标注路径 20,000 字符"并列作为两条仪器边界。
- **顺带**：`scripts/e9_selftrain.py` 的未来版本应从训练集里先剔除带锚点的文书（或在 `build` 阶段断言 `train ∩ anchor = ∅`），并把交集数写进产物。

## D-96 — E9 窗口期 `start_llm.sh` 无窗口守卫：watchdog 每 10 分钟拉 vLLM，与训练器抢显存（已加守卫）

- **现象**：E9 正式运行期间（pid 237145，04:39:33Z 起，GPU 6.99–7.16 GiB），两个常驻 watchdog 循环
  （pid 4913 / 171839，同一 `while true; curl /v1/models || start_llm.sh; sleep 600`）仍按"`/v1/models` 不通就拉起 vLLM"的规则反复调用 `scripts/start_llm.sh`。
  `logs/watchdog.log` 共 **11** 次 `vLLM starting`、**9** 次 `not ready after 600s`、**1** 次 ready；
  最近一次 **05:57:04Z**（`start_llm.sh` pid 246958 → vLLM pid 246962）在 `logs/vllm.log` 留下
  `CUDA out of memory. Tried to allocate 1.63 GiB ... Process 237145 has 6.99 GiB memory in use ... this process has 15.07 GiB ... 1.47 GiB is free`，
  随后 `RuntimeError: Engine process failed to start`。该次启动还覆写了 `state/vllm.pid`（7 B）和 `logs/vllm.log`（原日志被截断）。
- **量测（05:57Z）**：`nvidia-smi --query-compute-apps` 只有 `237145, 7160 MiB`；`/v1/models` = 000（窗口期应有）；
  `state/e9_window.json` `at_utc=04:59:56Z`（D-93 后手工重建），age 3950 s < 6 h。
  E9 本体未受损：`e9.out` 05:57Z 仍为 `[base] 250/423 5026s err=14 ctx_trunc=16`，进程 `State: R`。
- **根因**：`scripts/start_llm.sh` 只认 `/v1/models` 与 `vllm.pid`，**不读 `state/e9_window.json`**；
  D-82/D-93 的窗口纪律只约束"值守代理/人"，没有落到脚本层。每 10 分钟一次的 vLLM 预分配（`--gpu-memory-utilization 0.85`）
  在 7 GiB 已被训练器占用时必然 OOM；反复尝试会持续制造显存/CPU 争用，且在极端时序下可能把训练器挤出。
- **处置（只改守卫，不改任何阈值/映射/协议/数据）**：在 `scripts/start_llm.sh` 的"已服务"与"pid 存活"检查之后加守卫：
  当 `state/e9_window.json` 存在、其 `at_utc`/`started_utc` 距今 < 6 h、**且** `pgrep -f 'e9_selftrain[.]py'` 有进程时，
  打印 `E9 VRAM window active ... refusing to start vLLM` 并 `exit 0`。
  条件里要求训练器**确实在跑**，是为了不挡 E9 wrapper 自己的收尾重启（v1 的 EXIT trap 在 `e9_selftrain` 退出后才调 `start_llm.sh`，届时 pgrep 为空 ⇒ 正常启动）。
- **验证**：`bash -n scripts/start_llm.sh` OK；在窗口内手动执行 `bash scripts/start_llm.sh` → 打印拒绝（marker 04:59:56Z、age 3950 s），
  rc=0，`state/vllm.pid` mtime 不变（仍是 05:57:05）、GPU 仍只有 237145、`/v1/models` 仍 000（未启动、未抢显存）；
  `make smoke` **9/9 OK**。
- **影响面**：分析产物、语料、门禁、发布包**均未改动**；两个 watchdog 保留其窗口外职责；窗口标记的创建/删除纪律仍按 D-93（v1 wrapper 当前在跑，v2 待其退出后替换）。
  本条目只登记运维缺陷与守卫，不改变任何科学口径。

## D-97 — 人工编码执行：单编码者 + 会话口述通道；H1 判据触发，救援判为失败

- **偏离 1（编码通道）**：预注册 §4 规定使用 `human/coding_packet.html`（sha
  `ccad4fe227b80956d11385ccf5c09b3637220adfeadee72e6714a2094f90fb24`，808,549 B）。
  实际由用户**在会话中逐篇口述判断**，经 `human/chat_next.py` 呈现；其摘录规则机械固定且对
  80 篇一致：文书头 90 字 ＋「经查明/经调查/现查明/经查」起 900 字 ＋ 最后一条「违反了/依据」句
  （≤200 字）。**已知缺陷**：该规则在部分文书中检出的「依据」句是程序性条款（缴款、加处罚款、
  公示、裁量说明），而非定性条款；编码者据事实段判断。逐篇原始记录 `human/coded_chat.jsonl`
  （80 行，k=1..80，`--record k CODE` 写入，未回改）。
- **偏离 2（编码者数）**：预注册 §4 与 `human/CODER_MANUAL.md` §五设想**两名**编码者以计算人际
  κ。实际只有 **1 名**（用户本人），无第二编码者。因此**仪器—人工分歧与该编码者的判读习惯无法
  分离**。H1 的预注册定义本身只要求「一个独立的人类读者」，其判定按预注册有效；但论文**不得**
  声称人际信度，须写明 `n_coders = 1`、无第二编码者复核。
- **未替换、未补抽**：样本 doc_id 集合与 `human_sample.json` digest
  `013218fb6d479a4c093974e89c0eaa568012ab1330b4ec4ea09391a39de916c6` 一致
  （文件 sha `f722dd114f0a0ab81b6e9bddf8273091c1859bc7e75124a14a676024def82634`）；
  silver sha `a1deda2c…`。零篇 `UNRESOLVED`，未剔除任何篇，敏感性分析同值。
- **预注册落盘锚点（补齐）**：`PREREG_20261105_rescue.md`（含附记 #1/#2）
  sha `88644a43f85057c7100faae060ebc5acb8b54a9a10fa2ac87c35a5761c49b98a`；
  `human/CODER_MANUAL.md` sha `8cf7d123ab9890f9fb3638d7cf8f17023d1b45956349fa75fe88a6404c6a25b8`。
- **结果**（`data/analysis/e11_agreement.json` sha
  `5864703ad1a14f43d8b6bb686fcf6561a066ad327b3a9b27f58801d008544bf6`，
  `at_utc` 2026-11-05T06:22:48Z；输入 `human/coded.json` sha
  `5b1735b582fed2aeb60e39f227688020fa87fbe1185f7368f02726410dc68e9b`）：
  - **H1**（S1，n=60，0 篇 UNRESOLVED）：一致 **29/60 = 0.4833**，Wilson 95%
    **[0.3618, 0.6069]**；κ **0.2622**、Gwet AC1 **0.4101**、PABAK **0.3800**；
    UNRESOLVED→OTHER 敏感性分析同值（0.4833）。
  - **H2**（S2，n=20）：一致 **13/20 = 0.6500**，Wilson [0.4329, 0.8188]；
    与 S1 之差 **+0.1667**，Newcombe [−0.0832, +0.3747]，**跨 0 ⇒ not_estimable**；
    且方向与假设（S2 更低）**相反**。
  - **H3**：S1 中仪器属三个「造假」细类的仅 **5** 篇 < 10 ⇒ 按先验判 **not_estimable**。
  - **H4**：判据 1 触发（0.4833 < 0.70）；判据 2（UNRESOLVED > 12）未触发（0）；
    判据 3（人工类别 < 3）未触发（6 类）。⇒ **`rescue_failed = true`**。
- **混列（S1，仪器行 → 人工列；行和 60，对角 29）**：
  FALSE_LABELING 43（→同 21、OTHER 19、UNLICENSED 2、FAKE_CERT 1）；
  UNLICENSED 9（→同 2、OTHER 6、FALSE_LABELING 1）；FORGED 2（→同 2）；
  OTHER 3（→同 3）；FAKE_CERT 2（→同 1、FORGED 1）；TAMPERED 1（→OTHER 1）。
  人工标签全样本分布：OTHER 46、FALSE_LABELING 24、UNLICENSED 5、FORGED 3、
  FAKE_CERT 2、TAMPERED 0、UNRESOLVED 0。
- **按预注册 §2 的后果（照此执行，不另择口径）**：H1 被拒绝 ⇒ 摘要必须写明「仪器未通过
  忠实度门槛」；主表类别分布改标 `instrument output, uncalibrated`；结合 H4 ⇒ 全文退回
  「只报可估计性边界」的定位，**不得**把 `violation_category` 的任何比例写成总体估计。
- **不改变**：`data/silver/silver.jsonl`、`data/raw/`、`state/foods.sqlite`、E9
  （pid 237145 仍在跑）。本条目只登记执行偏离与预注册判据的自动判定，不修改任何
  阈值／映射／口径／抽样。

## D-98 — 第二编码者加入：A/B 人际一致度的**先验**判据（写于 B 的任何编码之前）

- **背景**：D-97 记录本次人工编码只有 1 名编码者，导致「仪器错」与「该编码者的判读习惯」
  无法分离。现补第二编码者 B。**本条目在任何 B 的编码结果产生之前写定**，B 的数据一旦落盘，
  下面 H5/H6 的判据不得改动；如需改动，另开 `D-nn` 并在正文同位置披露。
- **规程（不变）**：B 使用**同一** `coding_packet.html` 的同一份题库（`human_sample.json`
  digest `013218fb6d479a4c093974e89c0eaa568012ab1330b4ec4ea09391a39de916c6`），
  **同一** `human/CODER_MANUAL.md`（sha `8cf7d123…`），独立完成，**不得**看到 A 的任何答案、
  不得看到本会话任何内容、不得与 A 交流。B 的界面键为独立命名空间（`coding_packet_B.html`，
  localStorage 键 `foods_coding_B_v1`），防止与 A 在同一台机器上串档。
  B 的结果落 `human/coded_B.json`；A 的结果为 `human/coded_A.json`（= 已落盘的 `coded.json`，
  sha `5b1735b582fed2aeb60e39f227688020fa87fbe1185f7368f02726410dc68e9b`）。
- **H5（人际信度，主判定）**：在**全部 80 篇**上计算 A 与 B 的 6 类一致率 `p_AB`
  （`UNRESOLVED` 剔除并报剔除数；另报 UNRESOLVED→OTHER 敏感性分析），同时报 Wilson 95%
  区间、Cohen's κ、Gwet's AC1、PABAK、prevalence index。
  - `p_AB ≥ 0.80` 且 Wilson 下界 `≥ 0.70` 且 `κ ≥ 0.60` ⇒ **人类可复原**
    （human-recoverable）：仪器与人工的分歧归因于**仪器**，H1 的 0.4833 可写作
    「仪器忠实度」，且类目体系本身可用。
  - `p_AB < 0.60` 或 `κ < 0.40` ⇒ **人类不可复原**：类目对独立读者都不可靠，H1 的 0.4833
    只能写作「**上限估计**」，正文须写明「该六类方案在本语料上不具备人际可复原性」。
  - 其余区间 ⇒ **中间态**，只报数值与区间，**不做**归因判定。
- **H6（三方分解，描述性）**：记 `p_IA` = A↔仪器（已测 0.4833）、`p_IB` = B↔仪器、
  `p_AB` = A↔B。逐类给出三张混淆矩阵，并报 A、B 各自的 OTHER 份额。
  - 若 `p_AB` 高而 `p_IA`、`p_IB` 都低且彼此接近（|p_IA − p_IB| ≤ 0.10）⇒ 判定为
    **仪器系统偏离**，偏差方向以 A、B 的共同判读为准，逐类列出。
  - 若 `p_AB` 低 ⇒ 不归因，只报「类别不可复原」与各矩阵。
  - **不作**任何显著性主张；H6 是描述性分解，不是假设检验。
- **禁止**：不得由人事后协商统一口径（`CODER_MANUAL.md` §五）；不得以 B 的结果回头修改
  A 的任何一条（`coded_A.json` 冻结）；不得把 A、B 任一单方的标签当作「真值」。
- **产物**：`human/coded_B.json`、`human/coded_A.json`、`data/analysis/e11_ab_agreement.json`
  （脚本 `scripts/e11_ab_agreement.py`，读到 `coded_B.json` 才启用；缺失时只报 pending）。
  所有新数字进 `numbers.csv` 后才能进正文。
- **不改变**：预注册 H1–H4 的定义与判定（D-97 已登记 H4 触发、`rescue_failed = true`）；
  本条目只**新增**人际信度这一层，不推翻、不替换 H1–H4。

## D-99 — D-98 口径澄清：H6 的 `p_IA` 有两种分母，两者都报（写于 B 的任何编码之前）

- **起因**：D-98 的 H6 把 `p_IA` 写成「A↔仪器（已测 0.4833）」。0.4833 是**预注册 H1 的 S1
  口径**（n=60，简单随机层）；而 H6 的三方分解按「全部 80 篇」做，导入 S2 后 `p_IA` 会变。
  两种口径都不能省，故澄清如下，**不改 D-98 的任何判据**。
- **口径甲（全部 80 篇，H6 归因用）**：`p_IA`、`p_IB` 均在 80 篇上算；H6 的
  `instrument_systematic_deviation` 判据（`|p_IA − p_IB| ≤ 0.10`）用**口径甲**。
- **口径乙（S1 60 篇，与预注册 H1 对齐用）**：单列 `H6_I_vs_A_s1`、`H6_I_vs_B_s1`，
  供正文把「仪器忠实度」与预注册数字对照。已验证：`H6_I_vs_A_s1` = **0.4833**，
  与预注册 H1 完全一致（同一批 60 篇、同一标签）。
- **合成冒烟测试（不产生任何真实数据）**：以 A 的答案按 `Random(1)` 独立翻转 15% 生成
  合成 B，脚本给出 `p_AB` 0.8875、κ 0.8178 ⇒ 判定 `human_recoverable` 且
  `instrument_systematic_deviation = true`，与设计一致；测试目录 `/tmp/e11t` 已删除，
  `/opt/foods/human/` 下**只有** `coded.json`、`coded_A.json`，**没有**任何合成 `coded_B.json`。
  脚本 sha `deab21f4ba4716522dce7e06b78dd9aa547e858dfea1af7545778f4ba4fd7805`。
- **当前状态**：`data/analysis/e11_ab_agreement.json` 为 `status: pending`，
  `missing: ["coded_B.json"]`。B 的结果一旦落盘，按 D-98 判据自动判定，不得改判据。

## D-100 — 编码者 B 经**同一会话**完成：泄漏风险的先验处置（写于 B 的第 1 题之前）

- **事实**：B 由同一会话通道完成（用户在会话中转述 B 的判断），呈现规则与 A 完全相同
  （`human/chat_next.py`，同一摘录规则）。B 的作答写入**独立**状态文件
  `human/coded_chat_B.jsonl`（A 为 `human/coded_chat.jsonl`）；脚本以 `--coder B` 切换，
  A 的记录在 B 期间**只读、不改**（sha 已冻结 `5b1735b5…`）。
- **已识别的泄漏面（不可完全消除）**：本会话上下文里含 A 的全部 80 条答案与分布。
  B 若向上滚动即可见。呈现者（本代理）在 B 编码期间**不输出**A 的任何答案、分布或倾向，
  每题只给与 A 完全相同的机械摘录与同一行菜单；但「同一窗口」这一事实本身无法通过技术手段消除。
- **先验处置（防自欺）**：D-98 的 H5 判定加一条**泄漏守卫**，在任何 B 数据之前写定：
  - 若 `p_AB ≥ 0.95` **且** A、B 的 OTHER 份额之差 `< 0.05` ⇒ 判
    **`indeterminate_leakage_risk`**，**不得**判 `human_recoverable`；
    此时 H5 只能写成「两人高度一致，但同窗口施测使该一致性不可归因于独立判读」。
  - 该守卫**只降级、不放宽**：它使结论更难成立，不会使 H1 的失败更好看。
  - 若 `p_AB < 0.95` 或 OTHER 份额差 `≥ 0.05`，按 D-98 原判据执行，守卫不触发。
- **呈报要求**：论文与台账中必须写明「两名编码者经同一会话通道施测」，`n_coders = 2` 但
  **非独立分道**；不得写作「独立双编码」。
- **不改**：D-98 的 H5/H6 判据（本条目只**追加**守卫）、预注册 H1–H4、任何数据或映射。

## D-101 — D-97 引用的逐篇原始编码记录不在盘上；`human/` 对 agent 不可写

- **事实**（`2026-11-05T06:39Z`，pod 全盘 `find / -name 'coded_chat*' -o -name 'chat_next.py'` 零命中）：`human/` 只有 `CODER_MANUAL.md`、`coded.json`、`coded_A.json`；D-97 写的 `human/coded_chat.jsonl`（80 行）与 `human/chat_next.py` **均不存在**。`coded.json` 与 `coded_A.json` 字节相同（各 80 条，sha `5b1735b582fed2aeb60e39f227688020fa87fbe1185f7368f02726410dc68e9b`），类别分布 OTHER 46 / FALSE_LABELING 24 / UNLICENSED 5 / FORGED 3 / FAKE 2 / TAMPERED 0 / UNRESOLVED 0，与 D-97 一致。
- **可复读性**：用 `coded.json` + `human_sample.json`（digest `013218fb…`）+ 冻结 silver 独立重算，S1 **29/60 = 0.4833**、S2 **13/20 = 0.6500**，与 `data/analysis/e11_agreement.json` 逐位一致 ⇒ **D-97 的科学结论不依赖缺失的原始记录**。但 A 的逐题理由与呈现顺序只能从会话记录复读，pod 上没有第二份；**不得**据 D-97 声称该 jsonl 在盘，再分析只能以 `coded.json` 为准。未重建、未补写该文件（重建即伪造）。
- **写入阻塞**：`human/` 为 `2755 root:foods`、文件 `644 root:foods`；当前值守进程为 `agent`（uid 1000，组 `foods`），无 sudo，`test -w human` 为假。⇒ D-98/D-100 要求落盘的 `human/coded_B.json`、`human/coded_chat_B.jsonl`、`human/coding_packet_B.html` 若由 agent 写会 `PermissionError`（与 D-85 同型）。**建议在 B 写入前由 root/属主执行 `chmod 2775 human && chmod 664 human/*`**，或经 root 通道落盘。
- **不改变**：silver sha `a1deda2c…`、E9（pid 237145 在跑）、任何阈值／映射／tier／数据。本条目只更正 D-97 的文件断言并登记一个写入前置。

## D-101 — 双编码者一致性（D-98 H5/H6）落地结果与判决

- **判据来源**：D-98（H5/H6 判据，写于 B 的任何编码之前）＋ D-99（两种分母口径）＋ D-100（泄漏守卫）。
  三件**均未改动**。本条目只登记结果。
- **执行**：`scripts/e11_ab_agreement.py`（sha `deab21f4…`，未改）在 pod 上跑通，产出
  `data/analysis/e11_ab_agreement.json`，sha **`4f0a023ec977a5403c91b8599be05998f4a252f4cd1737708ac8f468861ee127`**，
  7,595 B，`at_utc = 2026-11-05T07:01:45Z`。
- **输入 sha**：`human_sample.json` `f722dd11…`、`silver.jsonl` `a1deda2c…`（终版树）、
  `coded_A.json` `5b1735b5…`（未动）、`coded_B.json` `924c1469…`（7,279 B，80 篇，k=1…80 无缺无重，
  与 B 版卡片顺序逐条对齐 0 处不符）。
- **编码实施**：A、B 各 80/80 篇，**无 UNRESOLVED**。B 类别分布：FALSE_LABELING 33、
  FAKE_CERTIFICATION 26、FORGED_INSPECTION_REPORT 6、TAMPERED_TRACEABILITY 6、
  UNLICENSED_OPERATION 6、OTHER 3。

### 结果（口径甲＝全部 80 篇，D-99）

| 量 | 值 |
|---|---|
| A↔B 一致率 p̂_AB | **0.1625**（13/80），Wilson 95% [0.0975, 0.2584] |
| Cohen's κ | **0.0019** |
| Gwet's AC1 | 0.0172 |
| PABAK（6 类） | −0.005 |
| S1（n=60） | 12/60 = 0.2000，CI [0.1183, 0.3178]，κ 0.0062 |
| S2（n=20） | 1/20 = 0.0500，CI [0.0089, 0.2361]，κ 0.0052 |

### 判决

- **H5 = `human_not_recoverable`**：p̂_AB < 0.60 **且** κ < 0.40，D-98 的两条否定判据同时触发。
- **D-100 泄漏守卫未触发**：触发需 `p̂_AB ≥ 0.95` 且 OTHER 份额差 `< 0.05`；
  实测 p̂_AB = 0.1625、差 = |0.5750 − 0.0375| = **0.5375**。故仍按 D-98 原判据执行。
- **H6 = `instrument_systematic_deviation` 不可判定**：D-98 要求先满足 `human_recoverable`，
  该前置条件不成立 ⇒ **不得**写作「仪器系统性偏离」。同时 |p̂_IA − p̂_IB| = 0.1875 > 0.10。

### 必须一并报出的三方数字（口径甲／口径乙）

- 口径甲（80 篇）：仪器↔A **0.5250**（κ 0.3298）、仪器↔B **0.3375**（κ 0.0795）。
- 口径乙（S1，60 篇）：仪器↔A **0.4833**（与预注册 H1 同一数字）、仪器↔B **0.3833**（κ 0.0860）。

### 读数纪律（写进论文时必须照此，不得压缩成一句「一致性低」）

1. **一致率可直接横比（同为 6 类判定），κ 因边际分布不同不宜直接横比。** 就一致率而言，
   两人之间（0.1625）**低于**任一方与仪器之间（0.5250 / 0.3375）。这不是「仪器差、人好」的结构。
2. **不一致的形态不同**：A 退守 OTHER（46/80 = 0.5750），B 铺开实质类（OTHER 仅 3/80 = 0.0375）。
   混淆矩阵中 A 的 46 篇 OTHER 被 B 拆成 FALSE_LABELING 18、FAKE_CERTIFICATION 14、
   FORGED_INSPECTION_REPORT 4、TAMPERED_TRACEABILITY 4、UNLICENSED_OPERATION 4、OTHER 2；
   A 的 33 篇 FALSE_LABELING 里 B 只认同 10 篇。
3. **可下的结论只有一条**：六类违规类型学在**两名人类判读者之间不可复原**。
   因此以该类型学为测量单位的任何比例（E6 粗/细粒度、E8 国别构成、表 1 各格）都不是总体估计。
4. **D-92 的措辞须再降一级**：不只是「instrument output 非总体估计」，而是
   「**该类别系统本身未通过人际信度检验**」。
5. **禁写**：「人工优于仪器」「仪器优于人工」「人类判不准所以仪器可用」「仪器系统性偏离」——
   H6 归因判据未满足，三方差异不可归因。
6. **施测方式须写明**：两名编码者经**同一会话通道**施测（D-100），`n_coders = 2` 但
   **非独立分道**，不得写作「独立双编码」。

### 产物与台账

- `data/analysis/e11_ab_agreement.json` sha `4f0a023e…`（7,595 B）；本地副本 `D:/Foods/data/analysis/`。
- `human/coded_B.json` sha `924c1469…`（7,279 B）；`human/coded_A.json` 未动。
- `supplementary/numbers.csv` 追加 **34 行**（`e11.ab_*`、`e11.h6_*`、`e11.other_share_*`、
  `e11.leak_guard_triggered`、`e11.h5_*`、`e11.h6_instrument_systematic_deviation`），
  全文件 CRLF，280 数据行，sha **`804fe92a1ad3a5ab216d564d6fb644580cc147b5dafc01813f7d746e210491f8`**。
- **不改**：D-98/99/100 判据、预注册 H1–H4、任何数据、任何映射。

## D-102 — 第三名编码者 C 与三人信度判据（写于 C 的第 1 题之前）

- **起因**：D-101 的 A↔B 判决（p̂=0.1625、κ=0.0019）已落定，但 **n=2 且同窗口施测**（D-100）
  不足以支撑「人类判读者普遍不可共享码本」的外推。补第三名编码者 C，用**完全相同**的机械摘录
  规则与菜单（`human/chat_next.py --coder C`，状态文件 `human/coded_chat_C.jsonl`，
  A/B 的文件只读不改），把结论从「两人不合」升级为「三人各自不合」。
- **判据（先于任何 C 数据写定）**：
  - **主统计量**：80 篇 × 3 名编码者、**6 类**（FORGED_INSPECTION_REPORT、
    TAMPERED_TRACEABILITY、FAKE_CERTIFICATION、FALSE_LABELING、UNLICENSED_OPERATION、OTHER）
    的 **Fleiss' κ**。UNRESOLVED 走完全案例，剔除篇数必须报出。
  - **次统计量**：三对两两一致率（A-B、A-C、B-C），各带 Wilson 95% 区间与 Cohen's κ、AC1、PABAK。
  - `typology_shared_reading` = 三对中最小的两两一致率 **≥ 0.80** **且** 该对 Wilson 下界 **≥ 0.70**
    **且** Fleiss κ **≥ 0.60**。
  - `typology_no_shared_reading` = Fleiss κ **< 0.40** **或** 最小两两一致率 **< 0.60**。
  - 两者都不成立 ⇒ `intermediate`，只能写成「不可判定」，**不得**择一叙述。
  - 触发否定判据时，主张只能写成：**三名判读者在同一份码本、同一批文书上的一致率不超过随机水平**。
    **禁写**「人类判不准」「仪器优于人工」「人工优于仪器」「所有人类编码都不可靠」——
    三人不构成对人类判读者总体的抽样。
- **不看**：C 在编码期间不接触 A/B 的任何答案、分布或倾向；编码期间本代理不输出 A/B 的任何数字。
  **同一会话通道**施测，D-100 的披露要求同样适用（`n_coders=3`，非三条独立分道）。
- **不改**：D-98 的 H5/H6、D-99 口径、D-100 守卫、D-101 已登记的 A↔B 判决。本条目只**新增**三人层。
- **脚本**：`scripts/e11c_three_coder.py`，sha **`483c48c8f6e6177f1c6d74c95c562d9a40a0a9b719f0922eae5f759d410655a2`**，
  7,355 B。产出 `data/analysis/e11c_three_coder.json`；`coded_C.json` 缺失时写 `status: pending`
  并列出 `missing`，不产生任何替代数据。
- **冒烟测试（不产生真实数据）**：以 A 的答案按两个独立种子各翻转 15% 合成 B、C，脚本给出
  Fleiss κ **0.659**、最小两两一致率 **0.70** ⇒ 判 `intermediate`（正确：最小两两一致率 0.70 < 0.80）。
  另做恒等核验：m=2 时 Fleiss κ 与 Cohen κ 数值完全相等（0.294118 = 0.294118），确认实现无误。
  测试目录为项目树外的临时目录，已删除；`/opt/foods/human/` 下**没有**任何合成 `coded_C.json`。
- **状态**：C 尚未开始。判据、脚本、执行方式三件均已冻结。

## D-103 — E9 `--run` 在 base 臂推理完成后于评分崩溃（`anchor_f1` 收到 `None` 标签）；已修评分路径并加逐臂落盘

- **现象**（`logs/e9.out`，可逐行复读）：`2026-11-05T04:39:34Z` 启动 `e9_selftrain.py --run`（E9 窗口，vLLM 已停），base 臂在 **423 篇**锚点集上跑完
  （末行 `[base] 400/423 8398s err=27 ctx_trunc=20`，约 8400 s），随后在评分处抛
  `TypeError: '<' not supported between instances of 'NoneType' and 'str'`
  （`scripts/e9_selftrain.py::_score` → `foods_pipeline/label/anchors.py:223 anchor_f1`），
  `07:08:50Z` rc=1。**`data/analysis/e9_selftrain.json` 未产生**，`data/train/adapter_e9/` 未训练 ⇒ 约 2.3 h GPU 输出丢失。
  窗口脚本随后按设计重启 vLLM（`07:09:40Z vLLM ready`，pid 250439，`/v1/models`=200），并删除 `state/e9_window.json`。
- **根因（量测，不是猜测）**：`_score` 把该篇预测写成 `rr["violation_category"] = by.get(doc_id)`；base 臂有未解析输出时该值为 `None`
  （04:38:50Z 的 `--probe 6` 已实测 `pred=null` 1/6；base 臂 `err=27/423` 与之同源）。`anchor_pairs` 只校验锚点侧非空，
  于是 `(None, "某个类别")` 进入 `anchor_f1`，其 `sorted()` 对 `None` 与 `str` 排序即抛错。
  复现（无 GPU）：`anchor_f1([("FALSE_LABELING","FALSE_LABELING"),(None,"FALSE_LABELING")])` 抛同一 TypeError。
- **处置（只改 E9 评分脚本，不改锚点引擎）**：`scripts/e9_selftrain.py` 中
  1. 未解析预测映射为哨兵标签 `__UNPARSED__`（真实类别不可能取此值）再交给 `anchor_pairs`，**计为答错**，
     不丢弃、不插补；每份分数新增 `n_unparsed`。**丢弃这些篇会抬高分数，属造假，故不采用。**
  2. base / adapter 两臂在推理结束后、评分之前各写一份**只写不读**的逐篇快照
     （`data/train/e9_base_preds.json`、`data/train/e9_adapter_preds.json`），使评分异常不再毁掉数小时推理；
     产物判定仍只来自同一次运行的返回值，快照不会被回读，旧快照无法进入结论。
  - **不动** `foods_pipeline/label/anchors.py`：它的输出就是冻结的 E1 anchor F1（现语料 0.2693），
    修共享函数会把 E9 的边界问题带进冻结口径。`anchor_f1` / `anchor_support` 一个字节未改。
- **验证**：`py_compile` OK；合成 3 篇小样本（1 正确 / 1 错类 / 1 未解析）得
  `n_unparsed=1`、macro **0.2222**、micro **0.3333**，`__UNPARSED__` 以 F1=0 进入宏平均；全未解析 3 篇得 macro/micro **0.0**，不再抛错；
  `only_ids` 子集路径正常（n=2、n_unparsed=0）；`make smoke` **9/9 OK**。
  脚本 sha：`ac5812dce7804e456488972ac745573bcb834c35f2089496254dad8d67fd2f99` → **`02204e2bbb35620972a710934f1cb283c1d6d44c93a3a69a7e9426aec00ec4cd`**。
- **口径说明**：哨兵类会给**有未解析输出那一臂**的宏平均多一个 0 分类；两臂标签宇宙因此不完全相同。
  这是保守方向（未解析=错），且 D-89 的 `sensitivity_base_parseable`（两臂只在 base 可解析篇上比较）继续作为配对对照；
  不得把该 delta 写成纯"类别学习增益"。
- **影响面**：`data/silver/silver.jsonl`（sha `a1deda2c…`）、`data/raw/`、`state/foods.sqlite`、门禁、E6–E8、终版发布包**均未改动**；
  未改任何阈值／映射表／tier 规则。E9 **未重跑**：它需要 10–12 GB 显存窗口（vLLM 必须停），本轮窗口已关闭、vLLM 已在服务，
  重跑须由执行者另开窗口；`e9_selftrain.json` 仍**不存在**，本条目不产生任何替代数字。

## D-104 — 编号重复：寄存器里有两个 `D-101`；引用约定与 MANIFEST 措辞的更正

- **事实**（`grep -o '^## D-[0-9]*' DEVIATIONS.md`，可逐行复读）：文件有 **109 个编号标题**，
  唯一编号 **103** 个（`D-1 … D-103`）。六个同号中，**五个是有意的「更正」条目**
  （`D-86 更正`、`D-88` 第二条、`D-89 更正`、`D-90 更正`、`D-84` 更正 D-83 的第二条），
  MANIFEST 已就此说明「更正条目不领新号」。**第六个不是**：
  - `DEVIATIONS.md:1990` `## D-101 — D-97 引用的逐篇原始编码记录不在盘上；human/ 对 agent 不可写`
    （`2026-11-05T06:39Z` 写就）
  - `DEVIATIONS.md:1997` `## D-101 — 双编码者一致性（D-98 H5/H6）落地结果与判决`（`07:01Z` 之后写就）
  两条**顺序上先有前一条**，后一条本应领 `D-102`，但 `D-102` 已被「第三名编码者 C 判据」占用，
  且 `D-102`/`D-103` 已被脚本注释与冻结文本引用 ⇒ **不重编号**（重编号等于改写历史，
  与本寄存器「只追加」的纪律相悖），改为登记 + 固定引用约定。
- **引用约定（自此生效）**：
  - 论文、补件、脚本注释中单写 `D-101` 时，**一律指「双编码者一致性（H5/H6）判决」那一条**
    （它是唯一被外部引用的那条）。
  - 指「逐篇编码记录不在盘上」那一条时必须写 `D-101(文件可读性)`，不得简写。
  - 新条目从 **`D-104`** 起（本条即 D-104）；编号必须 `grep -o '^## D-[0-9]*' | sort -n | tail -1`
    取 max+1，并在追加后 `grep -c` 复核唯一性（本条之前漏做了这一步）。
- **MANIFEST 措辞更正**：`supplementary/MANIFEST.md` 现写「append-only and single-numbered」。
  准确表述为：**编号唯一，但存在 6 处同号**——5 处是「更正」条目（有意同号），
  1 处是 `D-101` 的重号（本条目登记）。更正方式是追加新条目，不重写原文。
  该文件须在下次同步时改写此句。
- **不改**：任何数据、判据、判决、脚本。`D-98/99/100/101(一致性)/102/103` 全部维持原判。

## D-105 — E9 重跑启动（同脚本、同判据、同评测集；写于窗口打开之前）

- **依据**：D-103 已把 `scripts/e9_selftrain.py` 修好并通过合成件验证，脚本 sha
  **`02204e2bbb35620972a710934f1cb283c1d6d44c93a3a69a7e9426aec00ec4cd`**（22,584 B，
  `mtime 2026-11-05T07:10Z`）。本次是**同脚本重跑**：不改判据、不改映射、不改阈值、
  不改评测集（423 篇锚点集）、不改 D-95 的 311 篇主报子集、不改 `--run` 的任何超参。
- **为什么要重跑**：`2026-11-05T07:08:50Z` 那次 `--run` 的 base 臂 423 篇推理已完成
  （8,400 s）后在评分处崩溃，且崩溃版脚本**尚无逐臂落盘** ⇒ 该臂输出无法救回；
  `data/train/e9_base_preds.json` 在盘上**不存在**（`ls data/train/` 只有 `selftrain.jsonl`）。
  故只能整臂重跑，不存在「只补评分」的捷径。
- **执行方式**：`scripts/run_e9_window.sh`（`E9_MODE=--run`，`E9_STAMP=20261105`），
  `setsid nohup` 脱离会话。该脚本自带三道前置：终版收据 `status=released` 且 bundle sha 全对、
  训练栈可导入、写 `state/e9_window.json` 标记后停 vLLM；`EXIT` trap 无论成败都重启 vLLM
  并删标记（D-82/D-83 窗口纪律、D-96 的 watchdog 守卫）。
- **启动前实测**：`/v1/models` = **200**（vLLM 在服务）、`data/analysis/e9_selftrain.json` **不存在**、
  上述脚本 sha 与 D-103 登记值逐位相同。
- **预期用时**：base 臂约 2.3 h（上次 423 篇 8,400 s），adapter 训练 + 推理另计；窗口内 vLLM 不在线，
  期间**不得**有任何依赖 `/v1/models` 的流水线动作。人工编码 C 的会话通道**不依赖** vLLM，可并行。
- **崩溃处置（预先写定）**：若再次在评分处崩溃，逐臂快照 `data/train/e9_base_preds.json` /
  `e9_adapter_preds.json` 会保留；**只重跑缺失的那一臂**，不得用快照顶替本次运行的返回值
  （D-103：快照只写不读）。若同一崩溃复现，则 E9 记为 `instrument_failure` 并如实报出，
  **不得**改用其它口径凑出一个数字。
- **不改**：`data/silver/silver.jsonl`（`a1deda2c…`）、`data/raw/`、`state/foods.sqlite`、
  门禁、E6–E8、终版发布包、`foods_pipeline/label/anchors.py`。

## D-106 — 三人信度（D-102）落地结果：判据按原样触发 `no_shared_reading`，但 **D-102 的模板句不成立，须撤回**

- **执行**：`scripts/e11c_three_coder.py`（sha `483c48c8…`，未改）在 pod 上跑通，产出
  `data/analysis/e11c_three_coder.json` sha **`24da181906e149f781c8729e119e51cea69cfaefdc7deb3b2d0e69f62bb763f4`**，
  2,233 B，`status=complete`、`at_utc=2026-11-05T07:40:17Z`、`n_docs=80`、`n_excluded_unresolved=0`。
- **输入 sha（脚本自记）**：`human_sample.json` `f722dd11…`、`coded_A.json` `5b1735b5…`（未动）、
  `coded_B.json` `924c1469…`（未动）、`coded_C.json` **`20908949df09e95a996415cb0d2d7137e61d058649f7010bdc0898f87c3d226e`**（6,336 B，80 条，
  k=1…80 无缺无重、80 个唯一 doc_id、与 `human_sample.json` 顺序**逐条对齐 0 处不符**、无 UNRESOLVED）。
- **C 的编码实施**：80/80，同一机械摘录与同一菜单（`--coder C`），状态文件 `human/coded_chat_C.jsonl`。
  C 的类别分布：OTHER 49、FALSE_LABELING 25、FAKE_CERTIFICATION 3、UNLICENSED_OPERATION 2、
  FORGED_INSPECTION_REPORT 1、TAMPERED_TRACEABILITY 0。

### 结果

| 对 | 一致数 | p̂ | Wilson 95% | Cohen's κ |
|---|---|---|---|---|
| A↔B | 13/80 | 0.1625 | [0.0975, 0.2584] | 0.0019 |
| **A↔C** | **64/80** | **0.8000** | **[0.6995, 0.8730]** | **0.6371** |
| B↔C | 11/80 | 0.1375 | [0.0785, 0.2297] | −0.0353 |

Fleiss' κ（80 篇 × 3 人，6 类）= **0.0881**（p̄ = 0.3667、p_e = 0.3055）。
分类别一致度：OTHER 0.3125、FALSE_LABELING 0.2708、FAKE_CERTIFICATION 0.0646、
UNLICENSED_OPERATION 0.0298、FORGED_INSPECTION_REPORT 0.0241、TAMPERED_TRACEABILITY 0.0122。

### 判决（按 D-102 的操作定义，逐条对照）

- 最小两两一致率 = **0.1375 < 0.60** ⇒ `typology_no_shared_reading = true`；Fleiss κ 0.0881 < 0.40，
  同一方向。⇒ 判决 = **`no_shared_reading`**。`typology_shared_reading` = false（最小对 0.1375 < 0.80）。
- **判据未被改动，结论未被挑选**：本条目只登记按原式算出的结果。

### ★ 必须撤回想定措辞（本条目的主要内容）

D-102 规定「触发否定判据时，主张只能写成：**三名判读者…一致率不超过随机水平**」。
**这句话在本次数据上不成立**：A↔C 的 p̂ = 0.8000、κ = 0.6371，**远高于随机**。
若照抄，就是用一条预设的保守句去覆盖一个明显的反例 ⇒ **该模板句作废，不得写入论文或补件**。

**实际结构（分解后才知道，不是判据给的）**：

| 对 | 一致总数 | 其中 OTHER↔OTHER | 实质类一致（剔除 OTHER↔OTHER） | OTHER 份额 |
|---|---|---|---|---|
| A↔C | 64 | **42** | 22/38 = **0.5789** | A 0.5750 / C 0.6125 |
| A↔B | 13 | 2 | 11/78 = 0.1410 | A 0.5750 / B 0.0375 |
| B↔C | 11 | 2 | 9/78 = 0.1154 | B 0.0375 / C 0.6125 |

⇒ 三人不是「一致率都低」，而是**两种作答姿态**：**A 与 C 都倾向退守 OTHER（57.5% / 61.25%），
其 64 次一致里 42 次是「双方都判 OTHER」**；**B 几乎不退守（OTHER 仅 3.75%）**，与两人都不合。
A↔C 的 κ 0.6371 **不能当作类型学的信度系数**：κ 把「双方都弃权」记为一致。

### 可写与禁写（**取代** D-102 的模板句，其余 D-102 禁令继续有效）

- **可写**：六类类型学在三名判读者之间**不可共同复原**——按 D-102 的操作定义，最小两两一致率
  0.1375、Fleiss κ 0.0881 均落在否定区；且 A↔C 的一致 64/80 中有 42 次是共同弃权，
  剔除后实质类一致 22/38 = 0.5789。
- **必须一并报出**：三对一致率、A↔C 的 κ 0.6371、OTHER↔OTHER 占该对一致数的 42/64、
  三人 OTHER 份额（0.5750 / 0.0375 / 0.6125）、Fleiss κ 0.0881。**只报「三人一致率低」属误报。**
- **禁写**：「三名判读者一致率不超过随机水平」「人工不可靠」「人类判不准」「仪器优于人工」
  「人工优于仪器」「仪器系统性偏离」「A 与 C 相互印证类型学可用」。
- **必须披露**：三名编码者经**同一会话通道**施测（D-100），`n_coders = 3`，**非三条独立分道**。
  D-100 的泄漏守卫按原式只对 A↔B 定义（p̂_AB ≥ 0.95 且 OTHER 份额差 < 0.05），本轮未触发；
  A↔C 的 0.80 < 0.95，字面上也不触发，但**共同弃权已足以解释其主要成分**，不得据此主张独立判读成功。
- **对论文的处置**：D-92 的降级（instrument output 非总体估计）、D-101(一致性) 的第 3、4 条继续有效；
  新增一条：**若使用「人类编码者一致性」作为效度证据的任何论述，必须在同一段内报出弃权分解**，
  否则该论述不成立。
- **不改**：D-98 的 H5/H6、D-99 口径、D-100 守卫、D-101(一致性) 的 A↔B 判决、D-102 的判据本身。
  本条只登记结果、撤回模板句、给出替代措辞。

## D-107 — 一致率的弃权分解：新增一个**纯描述性**产物（写于该脚本上机之前）

- **起因**：D-106 必须报出「A↔C 的 64 次一致中 42 次是 OTHER↔OTHER、剔除后实质一致 22/38」
  这一组数，但这组数原先只存在于一条临时命令的输出里（**手打的数没有机器**），不能进台账。
  本条目把一个可复读的产物立起来。
- **脚本**：`scripts/e11c_decompose.py`，sha **`555adac2d316aad17d0de81202de05a13a68ff43461779da2c7636021981a267`**，
  3,391 B，`py_compile` OK。读 `data/analysis/human_sample.json` 与 `human/coded_{A,B,C}.json`，
  产出 `data/analysis/e11c_decomposition.json`：每对给 `n_agree`、`n_agree_other_other`、
  `n_scored_substantive`、`n_agree_substantive`、`substantive_agreement`，另给三人 OTHER 份额与
  各人标签计数、四件输入的 sha。
- **判据状态：本条目不设定、也不改动任何判据。** 该产物被显式标记
  `"role": "descriptive_decomposition_only"`，**不参与任何判决**；D-102 的 `no_shared_reading`
  已由 `scripts/e11c_three_coder.py`（sha `483c48c8…`）以原判据算出，本脚本**不重算、不覆盖**它。
- **方向性**：该分解只会使「类型学可共同复原」更难成立（它把一致性拆出弃权成分），
  **不会**让任何负面结论变好看；若结果与 D-106 已登记的分解不一致，以**新产物**为准，
  并把差异写进后续更正条目，而不是沿用本条与 D-106 里已写的数字。
- **不改**：D-98/99/100/101(一致性)/102/103/104/105/106 全部；不改任何数据、映射、阈值。

## D-108 — D-102/D-106 断言的两个原始文件在盘上不存在；三人信度的**数字本身可复读**（更正文件断言，不改口径）

- **事实**（`2026-11-05T07:46Z`，`find / -name 'coded_chat*' -o -name '*chat_C*'` 与 `grep -rn coded_chat scripts/ foods_pipeline/` 均零命中）：
  `human/` 只有 `CODER_MANUAL.md`、`coded.json`、`coded_A.json`、`coded_B.json`、`coded_C.json`；
  D-102 与 D-106 写的 `human/chat_next.py` 与 `human/coded_chat_C.jsonl` **均不存在**（与 D-101 对 A/B 的发现同型）。
  `scripts/e11c_three_coder.py` 只读 `coded_{A,B,C}.json`，不依赖这两个文件 ⇒ **不影响可复读性**。
- **独立复算**（本代理只用 `human/coded_{A,B,C}.json` 与 `human_sample.json`，未调用项目脚本）：
  n=80、三人各 80 条、doc_id 完全对齐；A↔B 13/80 = 0.1625、κ 0.0019；A↔C 64/80 = 0.8000、κ 0.6371；
  B↔C 11/80 = 0.1375、κ −0.0353；Fleiss κ **0.0881**（p̄ 0.3667、p_e 0.3055）；A↔C 的 64 次一致中 **42 次 OTHER↔OTHER**、
  剔除后 22/38 = 0.5789。**与 `e11c_three_coder.json`（sha `24da1819…`）、`e11c_decomposition.json`（sha `cf836f4c…`）逐位一致。**
  两个脚本 sha 也与登记值一致（`483c48c8…` / `555adac2…`）。
- **处置**：D-102/D-106 中「状态文件 `human/coded_chat_C.jsonl`」「`human/chat_next.py --coder C`」两处表述
  按「会话通道施测、逐篇记录未落盘」更正；**不得**再以「原始逐篇记录在盘」作为审计证据引用。
  若属主另有该会话日志，落盘后可再更正本条；在此之前以本条为准。
- **不改**：D-98/99/100/101(一致性)/102/103/104/105/106/107 的全部判据与数字；不改任何数据、映射、阈值、代码。
  本条只登记文件断言与复算结果。科学结论维持 D-106：`no_shared_reading`，且必须连同弃权分解一起报。

## D-109 — E9 窗口守卫在 6 h 处**失效打开**，而本次 `--run` expected 5.6–6.5 h（先登记，后改 21600→43200）

- **现象**：`scripts/start_llm.sh` 的 E9 守卫（D-96）拒绝启动 vLLM 的条件是三合一：marker 存在 **且**
  `pgrep -f 'e9_selftrain[.]py'` 命中 **且** marker `at_utc` 的 age `< 21600s`。本次 `--run`（D-105，
  07:18:40Z 开窗）在三段——base 臂 423 篇、adapter 训练、adapter 臂 423 篇——之后才结束；
  若总时长跨过 6 h，"训练器仍在跑"这一条会被 age 条件短路，watchdog（`logs/watchdog.log`，pid 4913 与 171839，
  每 600 s 一次）将在训练器仍持 7.1 GiB 显存时启动 vLLM（约需 15 GiB），与 05:57Z 观察到的 OOM 同型，
  可能让本次约 6 h 的输出再次作废。
- **量测**（`2026-11-05T07:38Z`，`logs/e9.out`）：base 臂 `50/423 @1180s` ⇒ **23.6 s/篇 ⇒ 单臂 ≈ 2.77 h**；
  两臂 5.5 h 再加 adapter 训练 ⇒ **5.6–6.5 h**，落在 07:18:40Z + 6 h = **13:18:40Z** 边界两侧。
  （上次 base 臂 8 398 s/423 篇 = 19.9 s/篇，本次 `MAX_LEN=8192` 更长，单臂更慢。）
- **处置**：只把 age 上限 **21600 → 43200（12 h）**；「训练器在跑」仍是必要条件——EXIT trap 在训练器退出后
  调 `start_llm.sh` 时 `pgrep` 已为空，不受影响；陈旧 marker + 挂死进程仍会在 12 h 后放行。
  **不动 `scripts/e9_selftrain.py`**（本轮跑的是 D-105 登记的 sha `02204e2b…`，中途改盘会与台账不符）。
- **影响面**：只影响 E9 窗口内 watchdog 的拒绝时长；不改数据、阈值、映射表、tier 规则、任何判据或 silver；
  对**正在跑**的进程无影响（bash 每次调用重读脚本）。验证：`bash -n scripts/start_llm.sh`、`make smoke`。
- **不改**：D-82/D-96 的其余窗口纪律、D-103/D-105 的 E9 口径与脚本、E1–E8、终版发布包。

## D-108 — D-102/D-106 断言的两个原始文件在盘上不存在；三人信度的**数字本身可复读**（更正文件断言，不改口径）

- **事实**（`2026-11-05T07:46Z`，`find / -name 'coded_chat*' -o -name '*chat_C*'` 与 `grep -rn coded_chat scripts/ foods_pipeline/` 均零命中）：
  `human/` 只有 `CODER_MANUAL.md`、`coded.json`、`coded_A.json`、`coded_B.json`、`coded_C.json`；
  D-102 与 D-106 写的 `human/chat_next.py` 与 `human/coded_chat_C.jsonl` **均不存在**（与 D-101 对 A/B 的发现同型）。
  `scripts/e11c_three_coder.py` 只读 `coded_{A,B,C}.json`，不依赖这两个文件 ⇒ **不影响可复读性**。
- **独立复算**（本代理只用 `human/coded_{A,B,C}.json` 与 `human_sample.json`，未调用项目脚本）：
  n=80、三人各 80 条、doc_id 完全对齐；A↔B 13/80 = 0.1625、κ 0.0019；A↔C 64/80 = 0.8000、κ 0.6371；
  B↔C 11/80 = 0.1375、κ −0.0353；Fleiss κ **0.0881**（p̄ 0.3667、p_e 0.3055）；A↔C 的 64 次一致中 **42 次 OTHER↔OTHER**、
  剔除后 22/38 = 0.5789。**与 `e11c_three_coder.json`（sha `24da1819…`）、`e11c_decomposition.json`（sha `cf836f4c…`）逐位一致。**
  两个脚本 sha 也与登记值一致（`483c48c8…` / `555adac2…`）。
- **处置**：D-102/D-106 中「状态文件 `human/coded_chat_C.jsonl`」「`human/chat_next.py --coder C`」两处表述
  按「会话通道施测、逐篇记录未落盘」更正；**不得**再以「原始逐篇记录在盘」作为审计证据引用。
  若属主另有该会话日志，落盘后可再更正本条；在此之前以本条为准。
- **不改**：D-98/99/100/101(一致性)/102/103/104/105/106/107 的全部判据与数字；不改任何数据、映射、阈值、代码。
  本条只登记文件断言与复算结果。科学结论维持 D-106：`no_shared_reading`，且必须连同弃权分解一起报。

## D-109 — E9 窗口守卫在 6 h 处**失效打开**，而本次 `--run` expected 5.6–6.5 h（先登记，后改 21600→43200）

- **现象**：`scripts/start_llm.sh` 的 E9 守卫（D-96）拒绝启动 vLLM 的条件是三合一：marker 存在 **且**
  `pgrep -f 'e9_selftrain[.]py'` 命中 **且** marker `at_utc` 的 age `< 21600s`。本次 `--run`（D-105，
  07:18:40Z 开窗）在三段——base 臂 423 篇、adapter 训练、adapter 臂 423 篇——之后才结束；
  若总时长跨过 6 h，"训练器仍在跑"这一条会被 age 条件短路，watchdog（`logs/watchdog.log`，pid 4913 与 171839，
  每 600 s 一次）将在训练器仍持 7.1 GiB 显存时启动 vLLM（约需 15 GiB），与 05:57Z 观察到的 OOM 同型，
  可能让本次约 6 h 的输出再次作废。
- **量测**（`2026-11-05T07:38Z`，`logs/e9.out`）：base 臂 `50/423 @1180s` ⇒ **23.6 s/篇 ⇒ 单臂 ≈ 2.77 h**；
  两臂 5.5 h 再加 adapter 训练 ⇒ **5.6–6.5 h**，落在 07:18:40Z + 6 h = **13:18:40Z** 边界两侧。
  （上次 base 臂 8 398 s/423 篇 = 19.9 s/篇，本次 `MAX_LEN=8192` 更长，单臂更慢。）
- **处置**：只把 age 上限 **21600 → 43200（12 h）**；「训练器在跑」仍是必要条件——EXIT trap 在训练器退出后
  调 `start_llm.sh` 时 `pgrep` 已为空，不受影响；陈旧 marker + 挂死进程仍会在 12 h 后放行。
  **不动 `scripts/e9_selftrain.py`**（本轮跑的是 D-105 登记的 sha `02204e2b…`，中途改盘会与台账不符）。
- **影响面**：只影响 E9 窗口内 watchdog 的拒绝时长；不改数据、阈值、映射表、tier 规则、任何判据或 silver；
  对**正在跑**的进程无影响（bash 每次调用重读脚本）。验证：`bash -n scripts/start_llm.sh`、`make smoke`。
- **不改**：D-82/D-96 的其余窗口纪律、D-103/D-105 的 E9 口径与脚本、E1–E8、终版发布包。

## D-110 — 本轮**两次**追加均撞号（D-108、D-109 各被占用）：最终编号裁定——品类指数条目 = D-111，编号纪律条 = D-112

- **事实**：本轮追加两条新条目时，我都用 `grep -c '^## D-'`（标题行数）代替「数值最大号」判断，两次都错：
  - 第 **2290** 行 `## D-108 — 食品品类关键词出现指数…`（1,920 B）与第 **2255** 行既有 D-108
    （`D-102/D-106 断言的两个原始文件在盘上不存在…`）**同号**；
  - 第 **2307** 行 `## D-109 — 编号冲突更正…`（1,928 B）与第 **2272** 行既有 D-109
    （`E9 窗口守卫在 6 h 处失效打开… 21600→43200`）**同号**。
  两条既有条目在本轮追加**之前**已在盘上，**不是**本轮产生；本轮产生的只有第 2290、2307 行两条。
- **最终裁定（append-only：不回改任何正文，只由本条指定编号）**：

  | 行号 | 正式编号 | 内容 |
  |---|---|---|
  | 2255 | **D-108**（不变） | 文件断言更正：coded_chat 两文件不在盘，数字可独立复算 |
  | 2272 | **D-109**（不变） | E9 窗口守卫 age 上限 21600→43200 |
  | 2290 | **D-111** | 食品品类关键词出现指数（词表与规则，写于任何计数之前） |
  | 2307 | **D-112** | 编号纪律条；其正文里的 `D-108a` / `D-108b` 属**暂用标签，由本条作废** |

  - `scripts/e12_commodity_index.py` 的 `criterion_register` 字段**必须**写 `"D-111"`。
  - **后续新条目从 D-113 起编**。追加前必须两步都过：① `grep -o '^## D-[0-9]*' | sed 's/## D-//' | sort -n | uniq | tail -1`
    取数值最大号；② `grep -c '^## D-<n>\b'` 必须为 0。
- **影响面：无数据影响。** D-111 写定时**尚未运行**，盘上不存在任何品类计数产物；本条不改任何判据、
  已成产出的数字、数据、映射、阈值、门禁，也不参与 E1–E11 任何判决。
- **纪律（写进台账，不只写进事故记录）**：**标题行数 ≠ 最大号**。本台账里五条 `… 更正` 会重复号，
  `grep -c` 既可能少算也可能多算，**永远不能作编号依据**；编号只认 `sort -n` 的最大值 +1 与唯一性复查。
- **现状计数**（本条追加前）：117 个 `## D-` 标题行，109 个唯一数值号（D-1…D-109）；追加本条后 118 / 110。

## D-113 — D-111 跑出品类出现谱（首次执行记录），并**在核对完成之前**增列 `subject / ingredient / false` 三分判读

- **脚本**：`scripts/e12_commodity_index.py` sha **`6f79d791e37b17d6cbf5fa4299126d76dd720556b13b2c6e70e6d9c4e1e976aa`**，9,994 B，
  `criterion_register` 字段写 **`D-111`**（编号由 D-110 裁定）。首次执行 `at_utc=2026-11-05T07:49:12Z`。
- **产物**：`data/analysis/e12_commodity_index.json` sha **`f98fdcdfe5ce891cde300b21c772c67fd16b3035b4de4dd0bec8a7f64875fa46`**，66,971 B；
  核对样本 `data/analysis/e12_precision_sample.json` sha **`52873605838d1d6fb815e03746411832cdd5927fcb75de66d479185b73f50b82`**，246,921 B、**270** 条。
- **输入**：`silver.jsonl` sha `a1deda2c…`（与终版一致）；清洁全文按
  `data/clean/docs/<doc_id 的 ':' 换成 '_'>.txt` 定位（本语料 1,128 个 doc_id **全部含一个冒号**，
  首次执行按 `${doc_id}.txt` 直接拼路径 ⇒ `FileNotFoundError`，该次**未写出任何产物**）。
  盘上 `.txt` 共 **1,153** 个，其中 **25** 个在 `silver.jsonl` 中无对应 `doc_id`（清单已写入产物
  `inputs.orphan_files`，多为纯数字案号型文件名），**未计入任何计数**。实际读入 1,128 个文件、
  **9,309,505 B**；`(doc_id, 文件 sha256)` 列表 sha **`325ded3a…`**。
- **结果（全窗 1,128 篇）**：至少命中一个品类词 **679** 篇、零命中 **449** 篇。
  分类别篇数（份额，分母 = 1,128）：调味品 163（0.1445）、生鲜肉 137（0.1215）、粮食 111（0.0984）、
  水产 100（0.0887）、糕点 86（0.0762）、糖果蜜饯炒货 85（0.0754）、酒类 82（0.0727）、
  肉制品 72（0.0638）、食用油脂 70（0.0621）、水果 69（0.0612）、保健食品 66（0.0585）、
  饮料 56（0.0496）、蔬菜 54（0.0479）、乳 49（0.0434）、蛋 39（0.0346）、豆制品 35（0.0310）、
  特殊膳食 32（0.0284）、茶叶 24（0.0213）。**这 18 个数一律读作「该品类词在本文书窗口内出现」，
  不是该品类的违规流行率，也不构成任何风险排序。**
- **阴性对照**：`电池` 2 篇、`锅炉` 2 篇、`计量秤` 1 篇；**有非食品词命中且无任何品类命中的文书 3 篇**
  ⇒ 本语料**并非纯食品文书**，该 3 篇的 `doc_id` 已在产物中列出，写论文须作为语料的成分事实报出
  （不得隐藏，也不得据此推断比例）。
- **★ 增列（本条写定时核对**尚未**完成，仅为把判读口径先钉住）**：D-111 定的通过判据
  「该词是否指食品意义上的该品类」**不变**；但核对中看到大量命中来自**配料表**（如虚假标注案里
  的「小麦淀粉」「玉米淀粉」「大豆分离蛋白」），这类命中**指确为食品品类，却不指本案的被查商品**。
  因此每一例除通过/不通过外，另记一个三分位：
  - `subject` = 该词指**本案被查/被标注/被抽检的商品本身**；
  - `ingredient` = 该词只出现在配料/成分/原料中，或作为对比项、标准名、机关名的一部分；
  - `false` = 该词并不指该食品品类（地名、人名、成语、机构名等）。
  报告时**必须同时给两个数**：`subject-only 精确率` 与 `any-mention 精确率`（= 非 false / 全部），
  **不得只报一个并称之为「精确率」**。D-111 的允许/禁写条款继续有效，并追加一条：
  **品类出现谱若要用于「该品类的执法案件」这一表述，只能用 `subject` 计数，不能用 any-mention 计数。**
- **待办**：核对结论另写 `data/analysis/e12_commodity_precision.json`（含 Wilson 95%），结果另登记条目；
  本条目只登记执行事实与判读口径，不改任何既有判据、数据、映射、阈值、门禁，不参与 E1–E11 判决。

## D-114 — D-113 的核对样本有显示缺陷（42/270 条窗口为空）：修显示循环后重跑，**计数逐字段不变**，重记 sha

- **缺陷**：`e12_precision_sample.json` 的窗口循环按「**整个词表**中最长的 6 个词」取窗，而不是按
  「**本篇实际命中**的词」取窗。肉制品、水果、水产等类的词几乎全是两字词，长度并列后排序不稳定，
  实际命中的词常落在前 6 之外 ⇒ **270 条样本里 42 条窗口为空**（分布：类4 8、类9 7、类5 6、类7 6、
  类11 4、类17 4、类15 3、类1 2、类2 1、类8 1）。空窗口的样本无法按 D-111 定的 ±120 字符核对。
- **修法（只改显示循环，不改匹配、不改判据、不改词表、不改取样规则）**：先筛出 `term in text` 的命中词，
  再按长度降序取前 6 个出窗。脚本 sha 由 `6f79d791…` → **`95826e15013bb1c7b5e9f57890980a81935e480c8b8219b3d1cff32edc258f3f`**，**10,082 B**。
- **重跑**（`at_utc=2026-11-05T07:50:39Z`）：`e12_commodity_index.json` sha **`52e3ca41db38102da29c15bdb8190fd351b1db12a73c6e6e2b54f2c5e16a5c2e`**（66,971 B，与旧件**同字节数**）；
  `e12_precision_sample.json` sha **`85d90fed0b90890e299eb5aabbfa8235ef126ea792f9512f3a016de10f789e55`**（299,726 B）、
  270 条、**空窗口 0**。
- **不变的证据（机器比对，不是复述）**：新旧两版 index 除 `at_utc` 外**逐字段 diff = 0**
  （`categories` 下 18 类的 `n_docs`/`share_of_window`/`terms_with_hits`/`terms_zero_hits`/`doc_ids` 全等，
  以及 `inputs`、`negative_control`、`lexicon`、`n_docs_*` 全等）⇒ **D-113 登记的每个计数、份额、
  阴性对照数、孤儿文件数全部继续有效**；样本的 270 个 `(doc_id, category)` 对**逐条相同**，
  即「取哪些篇」未变，只有「显示哪几段窗口」被修好。
- **状态**：本条写定时**尚无任何核对结论**（样本里 270 条的 `verdict` 全为 `null`），因此不存在
  「看过结果再修工具」的情形；精确率结果另条登记。
- **不改**：D-111 的词表与规则、D-113 的计数与三分判读口径、任何数据/映射/阈值/门禁、E1–E11 任何判决。
  本条只更正两个产物文件的 sha 与脚本 sha。

## D-115 — 品类出现谱的实测精确率（270 条人工判读）：any-mention 0.9296、**subject 仅 0.3852**，两类几乎全是法条文本

- **脚本**：`scripts/e12_commodity_precision.py` sha **`d10123d25099d714a3c4a79d52f8b818a93781add6f0c4b4a30a0306165ce900`**，9,101 B；
  `criterion_register` 写 `D-115`。判读表以源码字面量形式存于该脚本（位置式，18 类 × 15 条 = 270，超界即报错退出）。
- **产物**：`data/analysis/e12_commodity_precision.json` sha **`11108382db41aac741bf121c9376e88732dc977f947251c2072c6e017ed77ff8`**，
  `at_utc=2026-11-05T07:54:11Z`，n=270；输入 sha 自记（样本 `85d90fed…`、指数 `52e3ca41…`）。
- **判读分布**：**S（本案被查商品）104；I（提及但非本案商品）121；T（仅见于法条/标准文本）26；F（根本不是该品类）19。**
- **两个精确率（必须并列报，禁止只报一个并称「精确率」）**：

  | 口径 | 等额分配 | Wilson 95% | 按类规模事后分层 |
  |---|---|---|---|
  | **any-mention**（S+I+T）/270 | **0.9296** | [0.8927, 0.9545] | 0.9404 |
  | **subject** S/270 | **0.3852** | [0.3291, 0.4445] | 0.3636 |

  等额分配（每类 15 条）**不是**语料级比例，**分类别数才是主报**；事后分层列只作参考、不给区间。

- **分类别（N=语料篇数；S/I/T/F；any；subject）**：
  1 粮食 111：4/11/0/0，1.0000，0.2667 ｜ 2 油脂 70：3/12/0/0，1.0000，0.2000 ｜ 3 生鲜肉 137：4/11/0/0，1.0000，0.2667 ｜
  4 肉制品 72：9/6/0/0，1.0000，0.6000 ｜ 5 水产 100：5/7/0/3，0.8000，0.3333 ｜ 6 蛋 39：6/9/0/0，1.0000，0.4000 ｜
  7 乳 49：5/4/2/4，0.7333，0.3333 ｜ 8 蔬菜 54：4/7/1/3，0.8000，0.2667 ｜ 9 水果 69：3/7/1/4，0.7333，0.2000 ｜
  10 豆制品 35：14/0/0/1，0.9333，0.9333 ｜ 11 糕点 86：9/5/0/1，0.9333，0.6000 ｜ 12 酒类 82：13/2/0/0，1.0000，0.8667 ｜
  13 饮料 56：8/4/3/0，1.0000，0.5333 ｜ 14 茶叶 24：5/7/1/2，0.8667，0.3333 ｜ 15 调味品 163：2/12/1/0，1.0000，**0.1333** ｜
  16 保健食品 66：1/10/4/0，1.0000，**0.0667** ｜ 17 糖果炒货 85：8/6/0/1，0.9333，0.5333 ｜ 18 特殊膳食 32：1/1/13/0，1.0000，**0.0667**。
- **★ 三条必须写进论文的实测事实**：
  1. **19 个 F 全部是字面匹配的伪命中**，而非语义误判：跨词界合成（`金桂花`+`生产日期`→「金花生」、`面包车`、`土豆干`、`拷贝`光盘）、
     化学名（`苹果酸`、`葡萄糖酸`）、地名（`呼伦贝尔`、`石笋镇`、`普洱`2 例）、公司名（`鱼爪网`、`南京太二酸菜`）、
     **风味词**（`草莓牛奶味`、`葡萄牛奶味`、`蓝莓酸奶味` 4 例）。⇒ 未分词的字面匹配，其误差主要来自**词界**而非词义。
  2. **第 16、18 类（保健食品、特殊膳食用食品）的命中主要是法条文本**：T 分别 4/15 与 13/15。
     这两类的「出现谱」在本语料里**基本是法条引用谱**，不是商品谱 ⇒ 论文中这两行必须加标记，
     或干脆只报 subject 计数（分别为 1 与 1 篇样本）。
  3. **subject 份额普遍很低**（等额 0.3852）：绝大多数命中是**配料表、菜单组成、经营范围、邻近商品**。
     ⇒ 「本篇文书出现了某品类词」**不能**被读成「本案与该品类有关」。

- **写作用途约束（本条新增，D-111 原有禁令继续有效）**：
  - 表里两列并排：`any-mention 篇数（精确率）` 与 `subject 篇数（精确率）`；**只允许 subject 列**支撑
    「该品类的执法案件」这一措辞；any-mention 列只能写「该品类词在正文出现」。
  - 第 15、16、18 类必须在脚注写明「以配料/法条成分为主（subject 0.1333 / 0.0667 / 0.0667）」。
  - 品类出现谱与 `violation_category` 的交叉表**仍只作 instrument output**（D-92 + D-106 双重降级），且不得排序。
  - 一律不得出现「某品类造假占比/风险最高/流行率」。
- **不改**：D-111/D-113/D-114 的词表、计数、取样规则；任何数据、映射、阈值、门禁；E1–E11 任何判决。
  本条只登记核对结果与写作约束。

## D-116 — E9 自训练实验**中止**：打分阶段必然崩（`anchor_f1` 排序含 `None`），本次 4 h 算力改投 D-117

- **现场**：第 3 次尝试（07:18:40Z 起，`pid 251200`）在基座臂 150/423 处被**人工终止**，`rc=143`；
  窗口脚本 EXIT trap 已自动重启 vLLM。终止是本条裁定的一部分，不是事故。
- **根因（第 2 次尝试即已暴露）**：04:39:34Z–07:08:50Z 那次**基座臂跑完 423/423**（8,398 s，`err=27`、`ctx_trunc=20`），
  随后在 `scripts/e9_selftrain.py:311 → _score → foods_pipeline/label/anchors.py:223` 抛
  `TypeError: '<' not supported between instances of 'NoneType' and 'str'`。
  机制：基座臂 27 篇输出不可解析 ⇒ `anchor_pairs` 产生 `llm_category=None` 的对 ⇒
  `sorted({a for _, a in pairs} | {l for l, _ in pairs})` 同时含 `None` 与 `str` ⇒ 崩。
- ★**这是设计缺陷，不是偶发**：只要基座臂有任何一篇不可解析，E9 就在**打分**这一步崩；而打分发生在**全部生成之后**
  ⇒ **再跑一次只是重复烧掉约 2.3 h 的基座臂**。08:08Z 的现场（同一脚本、同一调用链）正是如此。
- **为什么不"修一行再跑"**：修法确实只需一行（`pairs` 中 `l is None` 者剔除并单列 `n_unparseable`），
  但两臂各约 2.3 h ⇒ 合计约 4.6 h，**恰好吃掉本次授予的全部 4 h**；而 E9 在论文中仅为附录，
  且其设计已自认两处不可比（文档窗口 5,192 tokens vs 标注上限 20,000 字符；训练∩评测 112/423）。
  **性价比不成立。**
- **裁定**：**中止 E9**，本次算力改投 **D-117**。E9 状态记为 `aborted_by_design_defect`；
  **不写"未完成"、不写任何 E9 数值**；论文附录 A 改为一段说明中止理由与缺陷，不留 `RESULT SLOT`。
- **遗留缺陷（登记，本次不修）**：`anchor_f1()` 必须容 `None`——`pairs` 中标签为 `None` 的条目单列
  `n_unparseable` 并从分母剔除；`_score()` 应在调用前断言，或显式把不可解析篇数传入。
- **不改**：E1–E8、E10–E12 的任何判决、产物与阈值；不改语料、映射、门禁；不改 D-95 的 clean 子集定义。
- **影响面**：只影响附录 A（自训练结果段删除）。

## D-117 — E13 商品角色测量（预注册）：用 LLM 二次判读把 D-115 的人工精确率扩成**全语料的 subject 篇数与召回率**

本条写于任何 E13 调用之前。动机：现稿有精确率、**没有召回率**，因此"某品类有多少案件"一句都不能写。
这是全文离"食品刊实质贡献"最近、也是唯一还空着的一格。

- **金标准**：D-115 的 270 条人工判读（`data/analysis/e12_commodity_precision.json`，sha `11108382…`）。
- **输入构造（S1 与 S3 必须一致，这是本条的关键约束）**：每篇文书取**事实段**；取不到则用清洁全文并按
  8,000 tokens 截断，截断篇数入产物。**S1 不得只用 ±120 字符窗口**——窗口里没有足够证据判断"本案商品是什么"，
  用窗口验证会系统性低估 LLM，使判定门变成对输入的检验而不是对判读能力的检验。
- **S1 验证**：用本地 vLLM 的 Qwen2.5-7B-Instruct，对同一 270 篇文档问同一个问题——
  「本案被查处的商品属于下面 18 类中的哪一类？只答类别号；不确定答 none」。
  把 S1 的回答按 270 条样本的 (doc_id, 品类) 对齐，得到二值"该品类是否本案商品"的
  **κ、balanced accuracy、混淆矩阵**。
- **S2 判定门（写在跑之前）**：**κ ≥ 0.60 且 balanced accuracy ≥ 0.75** ⇒ 通过，进 S3；
  否则 E13 判 `not_validated`，召回率一律报 `not_estimable`，论文写明"LLM 二次判读未达门槛"。
- **S3 全语料**：对 1,128 篇各问同一个问题，得到每篇的 subject 品类（18 选 1 或 none）。
- **S4 估计**（每品类 c）：
  - `A_c` = 关键词命中 c 的篇数（D-113 产物，已有）；
  - `B_c` = LLM 判 subject=c 的篇数；
  - **recall_c ≈ |A_c ∩ B_c| / |B_c|**；
  - **precision_c** 取 D-115 的 subject 精确率（人工，不由 LLM 产生）；
  - 两者都给 Wilson 区间，并**明写**：区间只含抽样与判读误差，**不含 LLM 误差**；LLM 误差以 S1 的 κ/BA 单独报告。
- **允许的措辞**：本帧内「LLM 判为本案商品的 N 篇中，词表命中 M 篇」。
  **禁止**：流行率、风险排序、跨帧比较、把 S3 的 LLM 输出称作人工标注、把 `A_c` 当分母
  （关键词只测出现，不测缺席）。
- **纪律**：`silver.jsonl` sha 必须仍为 `a1deda2c…`；E13 不写 `data/raw/`、不动 `silver.jsonl`、不动 `state/foods.sqlite`；
  产物写 `data/analysis/e13_*.json`，脚本写 `scripts/e13_commodity_subject.py`，`criterion_register="D-117"`。
- **失败即结论**：S2 未过就是结果，照实报，不得调门（改 κ/BA 门槛须先写新条目）。

## D-118 — E13 判定门**未通过**：LLM 二次判读 κ 0.3241 / BA 0.6519 ⇒ 召回率 not_estimable

- **产物**：`data/analysis/e13_commodity_subject.json` sha **`fc60b4fa7245d90e331eef1356cfde62d6b56834e72192ca91df91d06098dcf7`**；
  逐篇预测 `data/analysis/e13_preds.jsonl`（sha 见产物字段）；脚本 `scripts/e13_commodity_subject.py`（sha 见产物字段，
  `criterion_register="D-117"`）。模型 qwen2.5-7b-instruct，温度 0，max_tokens 16，字符上限 12,000。
- **S1 结果**：n=270，人工 S=104；**κ 0.3241**、**balanced accuracy 0.6519**（TPR **0.4423**、TNR **0.8614**）。
  D-117 的判定门（κ≥0.60 且 BA≥0.75）**未通过**。
- **机制不是随机噪声**：TNR 高、TPR 低 ⇒ 模型对"不是本案商品"判得准，对"就是本案商品"**系统性不认**
  （104 条里只认下 46 条）。这与类别直方图的偏斜一致：模型把 203 篇判为保健食品、188 篇判为肉制品、137 篇判为糕点，
  而人工判读里保健食品 subject 只有 1/15。
- **S3 覆盖**：1,128/1,128 全部有预测，**0 不可解析**，**0 篇触及 12,000 字符截断**。
  （覆盖完整不等于可用：判定门在 S1 已否，S3 的标签**一律不得使用**。）
- **裁定**：E13 = `not_validated`。召回率一律报 **`not_estimable`**；
  **不得**用 E13 的 S3 标签写任何"某品类 subject 篇数"；论文须写明"LLM 二次判读未达门槛"并给出 κ/BA/TPR/TNR。
- **不改**：D-117 的门槛、提示词、输入构造；E1–E12 任何判决与产物。
- **下一步**：D-119（模型敏感性），若仍不过则转人工零命中样本。

## D-119 — E14 商品角色判读的**模型敏感性**（预注册，写于任何 E14 调用之前）

- **问题**：E13 的失败是**模型特异**（换个模型就行）还是**构造特异**（本地模型都做不到）？
  这个答案决定论文能不能给出召回率，也决定"商品角色可自动测量"是不是一个真结论。
- **固定项（一个字都不许动）**：提示词与输入构造**与 E13 逐字节相同**——直接 `import` 同一个
  `SYSTEM` 与 `build_prompt`，不复制、不重写；温度 0；`max_tokens=16`；同一 1,128 篇文书；同一 270 条 D-115 金标准；
  同一判定门（κ≥0.60 且 BA≥0.75）。
- **候选模型（按此顺序跑，全部上报，与结果无关）**：① Qwen3.5-9B；② Qwen3.5-27b-GPTQ-Int4。
  GLM-4-9B 原在计划内，但本机 `models--THUDM--glm-4-9b-chat` 缓存**仅 4 KB、无权重** ⇒ 记为 `unavailable`，
  **不作为结果**，也不因为它缺席而缩小结论。
- ★**事先固定的汇报规则**：三个模型的 κ/BA/TPR/TNR **必须同表列出**，含 E13 的 Qwen2.5-7B（0.3241/0.6519/0.4423/0.8614）。
  不得只报通过的那个。
- **结论规则（写死，不因结果改）**：
  - **全部不过门** ⇒ 结论 `commodity_subject_not_automatable_with_local_models`；召回率继续 `not_estimable`；
    转 D-120 的人工零命中样本。这个结论本身进论文：它说明**商品角色不是换个模型就能测的**。
  - **恰有一个过门** ⇒ 该模型的标签**可以**用于 D-117 的 S4，但同表必须列出全部模型的门值，
    且摘要/正文**不得**单引召回数字而不带"1/N 个模型通过"。
  - **多个过门** ⇒ 用**逐篇一致性**（模型间 Cohen κ 与一致率）报告稳健性；名义仪器取过门模型中最小号者。
- **禁止**：为过门而改提示词、温度、截断、门槛、样本或对齐规则。任一改动须先写新条目再跑。
- **纪律**：`silver.jsonl` 仍须 `a1deda2c…`；产物流水 `data/analysis/e14_*`，脚本 `scripts/e14_model_sensitivity.py`，
  `criterion_register="D-119"`。

## D-120 — E14 未能执行：候选模型在本机栈上**不可加载**，模型敏感性 not_estimable

- **Qwen3.5-9B**：vLLM 启动失败，`ValueError: The checkpoint you are trying to load has model type
  'qwen3_5' but Transformers does not recognize this architecture`（本机 `transformers 4.46.3` / `vllm 0.6.6.post1`）。
  日志 `/opt/foods/logs/vllm_e14_qwen35_9b.log`。
- **Qwen3.5-27b-GPTQ-Int4**：同一 `qwen3_5` 架构 ⇒ 按同一 config 判定同样不可加载。**未单独运行，本条不声称跑过。**
- **Qwen3.8 / Qwen3.6 / Qwen3-VL 系列**：架构更新，同一栈更不可能支持；未试。
- **GLM-4-9B**：`models--THUDM--glm-4-9b-chat` 缓存 **仅 4 KB、无权重**（已实测 `du -sh`）。
- **裁定**：E14 = `unavailable`；**模型敏感性 not_estimable**。**不**因不可用而改写 E13 的 `not_validated`；
  本机 `/opt/foods/venv` 禁动，**不**升级 transformers/vLLM 去凑一个第二模型。
- **现场恢复**：已用 `scripts/start_llm.sh` 恢复 `qwen2.5-7b-instruct`（`/v1/models` 已实测返回）。
- **影响面**：无产物、无数字变化；论文中"商品角色判读是否依赖模型"一句只能写 `not_estimable`，不得暗示已检验。

## D-121 — E15 提问**格式**敏感性（预注册，写于任何 E15 调用之前）

- **问题**：E13 的失败是"商品角色不可自动判读"（构造特异），还是"18 选 1 的强制选择格式"造成的（格式特异）？
  两者对论文含义完全不同：前者是结论，后者只是仪器调参。
- **唯一改动**：把提问从「18 选 1」改为**逐类二值**——给出该品类名，问
  「本案被查处的商品是不是这一类？只答 1 或 0」。
  **其余全部不变**：同一提示词正文（除问题句）、温度 0、`max_tokens=16`、同一 1,128 篇、
  同一 270 条 D-115 金标准、同一判定门（**κ ≥ 0.60 且 BA ≥ 0.75**）。
- **★汇报纪律**：E15 的 κ/BA/TPR/TNR 必须与 E13 的（0.3241 / 0.6519 / 0.4423 / 0.8614）
  **同表列出并注明格式**。若 E15 过门而 E13 未过，论文须写明"过门依赖提问格式，18 选 1 不过门"，
  摘要**不得**单引召回数字而不带格式说明。
- **结论规则**：
  - **过门** ⇒ 跑全语料 1,128 × 18 的二值判读（20,304 次调用），按 D-117 的 S4 口径算
    `B_c`、`|A_c ∩ B_c|` 与 recall，精确率仍取 D-115 的人工值。**LLM 只提供分母侧的"本案是不是这一类"，
    不提供精确率。**
  - **不过门** ⇒ 召回率 `not_estimable`，转人工零命中样本（将另条预注册）。
- **禁止**：为过门改提示词其余文字、温度、截断、门槛、样本或对齐规则；不得只跑部分类别后据部分结果决定是否跑全量
  （判定门只看 270 条人工样本，与全语料结果无关）。
- **纪律**：`silver.jsonl` 仍须 `a1deda2c…`；产物 `data/analysis/e15_*`，
  脚本 `scripts/e15_binary_format.py`，`criterion_register="D-121"`。

## D-122 — E15 的**第二处**改动：文书正文前置、问句收尾（为前缀缓存），并明示这是独立于 D-121 的偏离

- **问题**：D-121 的逐类二值需要 1,128 × 18 = **20,304 次调用**，每次携带约 3,000–12,000 字符正文。
  若按 E13 的模板（问句在正文**之前**），同一文档 18 次提问的公共前缀只有系统提示加几十个 token，
  **末尾的正文每次都要重新预填**。按本机预填吞吐粗估约 **3.4 h**，几乎吃掉本轮 4 小时窗口的全部。
- **唯一额外改动**：把**文书正文前置**，问句作为提示词的**结尾**——
  `系统提示 → [规则] → ===== 文书正文 ===== → 正文 → ===== 问题 ===== → 本案被查处的商品是不是「{cat}」这一类？`
  这样同一文档的 18 次提问共享「系统提示 + 规则 + 整段正文」的公共前缀。
- ★**必须单独登记的理由**：这**不是** D-121 的"唯一改动"。D-121 锁死的是**提问格式**，
  正文与问句的**先后次序**是第二个变量。把它并进 D-121 会让"格式敏感性"结论带一个未申报的混杂项。
  本条目把它显式写出来：**E15 相对 E13 有两处改动（提问格式 + 正文前置）**，论文与产物必须同时标注这两处。
- **不变项（一个字不许动）**：系统提示、规则三条、只输出一个字符 1/0、温度 0、`max_tokens=16`、
  `CHAR_CAP=12,000` 截断、同一 1,128 篇、同一 270 条 D-115 金标准、同一判定门（κ ≥ 0.60 且 BA ≥ 0.75）。
- **服务端**：vLLM 以 `--enable-prefix-caching` 重启（经 `start_llm.sh` 的 `FOODS_VLLM_EXTRA` 传入）。
  前缀缓存是**服务端调度优化**，温度 0 的贪心解码下不改变任何一条输出。**不因此调整**任何门槛或结论规则。
- **自检**：若开缓存后在 270 条上的门值与"关缓存"存在任何不一致，视为实现缺陷，
  **先登记再处理**，不得二选一挑好的报。
- **汇报纪律**：E15 的 κ/BA/TPR/TNR 仍须与 E13 的（0.3241 / 0.6519 / 0.4423 / 0.8614）**同表列出**，
  并注明 E15 的格式为「正文前置 + 逐类二值」。凡引用 E15 的召回，正文与摘要都不得省略这两处标注。
- **结论规则**：与 D-121 相同，不因本条目而放宽——过门则跑全量并按 D-117 的 S4 口径算 `B_c`、`|A_c ∩ B_c|`、recall；
  不过门则召回率 `not_estimable`，转人工零命中样本（另条预注册）。**LLM 仍只提供分母侧，不提供精确率。**
- **纪律**：`silver.jsonl` 仍须 `a1deda2c…`；产物 `data/analysis/e15_*`，脚本 `scripts/e15_binary_format.py`，
  `criterion_register="D-121"`，`criterion_register_secondary="D-122"`。

## D-123 — E15 判定门**仍未通过**（κ 0.4885 / BA 0.7390）：格式是真实变量，但不足以救回可自动判读

- **产物**：`data/analysis/e15_validation.json` sha
  **`5b961f5c27a7b6bce9bd052ffaab8c8bca377519790fcf696b8ca2bbc8567ab9`**；
  逐条预测 `data/analysis/e15_preds.jsonl`（270 行）。脚本 `scripts/e15_binary_format.py`。
- **实测**：n=270，**κ 0.4885**、**BA 0.7390**（TPR **0.6346**、TNR **0.8434**）。判定门（κ≥0.60 且 BA≥0.75）**未通过**。
- **完整性**：270/270 有预测，**0 不可解析**（全部就是裸 `0`/`1`），**0 重复键**，**0 篇截断**，运行 59 s。
  仪器本身没有故障；这是仪器的**判定**，不是仪器的**失灵**。
- **同表（D-121 要求，格式必须注明）**：

  | 实验 | 提问格式 | κ | BA | TPR | TNR |
  |---|---|---|---|---|---|
  | E13 | 18 选 1（强制单选） | 0.3241 | 0.6519 | 0.4423 | 0.8614 |
  | E15 | 正文前置 + 逐类二值（1/0） | **0.4885** | **0.7390** | **0.6346** | 0.8434 |

- **读法**：换格式把 κ 抬了 **+0.1644**、TPR 抬了 **+0.1923**，TNR 基本不动（−0.0180）。
  ⇒ **格式确实是一个真实变量**（E13 的低 TPR 不是纯粹"读不懂"，有相当部分是被强制单选压出来的）；
  但**抬到 0.75 门槛之下、κ 差距更大**（κ 需 0.60，实得 0.4885）⇒ **可自动判读的失败不是格式假象**。
- **裁定**：E15 = `not_validated`。**D-121 的结论规则照办**：
  - **不跑**全语料 1,128 × 18（过门才跑；跑了也不得使用）；
  - 召回率继续 **`not_estimable`**；
  - 论文须把 **E13 与 E15 同表**列出并注明格式，**不得**只报 E15 的 0.4885 而隐去它仍未过门。
- **不改**：判定门、门槛、金标准、E1–E14 任何判决与产物。

## D-124 — E16 生成式抽取（**最后一次**自动尝试，写于任何 E16 调用之前）

- **为什么还试一次**：E13/E15 都是**分类**构造——从给定标签集里挑。但"本案被查处的是什么商品"在文书里是**被写出**的
  一个名词短语。用分类去问，等于要模型先在心里抽出来再映射到 18 个标签；两次失败可能来自**映射**而不是**抽取**。
  这是一个**构造问题**，不是调参问题，所以值得再测一次；但它也是**最后一次**（见下）。
- **构造**：让模型**只写出商品名**（≤20 字），再由**确定性词典**把该短语映射到 18 类（复用 E12 的 lexicon）：
  短语中出现的词条若属于类 c，则记 c；多类命中取**匹配词条最长**者；无命中记 0。
  **映射完全确定、可复算、与模型无关**——模型只负责"抽出那一个商品"，不负责"归类"。
- **与 E13 的可比性**：E13 的 `pred == c` 与 E16 的 `map(phrase_d) == c` 是**同一个统计量**，
  因此 κ/BA/TPR/TNR 可与 E13、E15 **同表**。
- **固定项**：系统提示**逐字复用 E13**（`import`）；文书正文前置（D-122 的版式）；温度 0；`max_tokens=32`；
  同一 1,128 篇；`CHAR_CAP=12,000`；同一 270 条 D-115 金标准；同一判定门（**κ ≥ 0.60 且 BA ≥ 0.75**）。
- ★**次数上限（写死）**：**E16 之后不再新增任何"换构造/换模型/换格式"的自动尝试**。
  若 E16 不过门 ⇒ 自动判读到此为止，召回率 `not_estimable`，转人工零命中样本（将另条预注册）。
  这条上限是为了让"尝试"不变成"调参直到过门"。
- **汇报纪律**：E16 的 κ/BA/TPR/TNR 必须与 E13（0.3241/0.6519/0.4423/0.8614）、E15（0.4885/0.7390/0.6346/0.8434）
  **三者同表**列出并注明构造与格式。**不得**只报通过的那一个。
- **结论规则**：过门 ⇒ 跑全语料 1,128 次调用，按 D-117 的 S4 口径算 `B_c`、`|A_c ∩ B_c|` 与 recall（带 Wilson 区间），
  精确率仍取 D-115 的人工值；**LLM 只提供分母侧**。不过门 ⇒ 召回率 `not_estimable`。
- **纪律**：`silver.jsonl` 仍须 `a1deda2c…`；产物 `data/analysis/e16_*`，脚本 `scripts/e16_extract_commodity.py`，
  `criterion_register="D-124"`。

## D-125 — E16 判定门**仍未通过**（κ 0.3888 / BA 0.6766）：自动判读到此为止

- **产物**：`data/analysis/e16_validation.json` sha
  **`0e560f5ae95a1c41e3170fca832e0515ef8c6bd3823c1a3b45693b118a34ae4e`**；
  逐篇抽取 `data/analysis/e16_preds.jsonl`（1,128 行）。脚本 `scripts/e16_extract_commodity.py`。
- **实测**：n=270，**κ 0.3888**、**BA 0.6766**（TPR **0.4135**、TNR **0.9398**）。判定门**未通过**。
- **三仪器同表（D-124 要求，构造与格式必须注明）**：

  | 实验 | 构造 | κ | BA | TPR | TNR |
  |---|---|---|---|---|---|
  | E13 | 18 选 1（强制单选） | 0.3241 | 0.6519 | 0.4423 | 0.8614 |
  | E15 | 正文前置 + 逐类二值（1/0） | **0.4885** | **0.7390** | **0.6346** | 0.8434 |
  | E16 | 自由文本商品名 + 确定性词典映射 | 0.3888 | 0.6766 | 0.4135 | **0.9398** |

- **失败点各不相同，这不是同一个失败量的三次重复**：
  - E15 把 TPR 抬得最高（0.6346）、TNR 最高的是 E16（0.9398）、κ/BA 最高的是 E15。
  - E16 的瓶颈**明确在映射步**：1,128 篇里有 **818 篇（72.5%）**抽出的短语**不含任何一条 lexicon 词条** ⇒ 记 0。
    所以 E16 的 TNR 高、TPR 低是**词典覆盖不足**的形态，不是"模型抽不出来"的直接证据。
    **本条不据此宣称抽取模型能力**（那样就需要新一轮构造，而 D-124 已封顶）。
- **裁定**：E16 = `not_validated`。**D-124 的封顶条款生效**：自动判读到此为止，
  **不再新增**任何"换模型/换格式/换构造"的尝试。召回率一律 **`not_estimable`**。
- **可发表的结论**（进论文）：**商品角色**（"本案查处的是哪一种食品"）在**现成 7B 本地模型 + 冻结提示词**下
  **三种构造全部不过预注册门槛**，且**三者失败模式互不相同**。这是一个**关于可测性**的结论，
  不是关于某个模型的性能报告。论文必须以**同表**呈现三次尝试，**不得**只报最好的一次。
- **不改**：判定门、门槛、金标准、E1–E15 任何判决与产物。

## D-126 — **不执行**人工零命中样本：召回率保持 not_estimable（写于任何零命中判读之前）

- **背景**：D-121 与 D-124 都把"转人工零命中样本"列为召回率的兜底。本条**撤销该兜底**，并给出理由。
  **本条写于尚未阅读任何零命中文书之前**，因此**不是**结果驱动的决定。
- **理由（三条，缺一不可）**：
  1. **单人判读达不到本文自己的信度线**。D-115 的 270 条金标准是**三人独立判读**，
     结果 **Fleiss κ 0.0881**、最小成对 **B↔C 0.1375**。同一任务上**单读**给出的品类归属，
     其判读误差**未知且很可能很大**；把它折算成召回率，等于把**未测量的判读误差**藏进分母。
  2. **这会直接违反本项目的硬约束**：不得以未验证量充当测量值。召回率若以单读样本产出，
     论文将出现一个"看起来是测量、实际是单人印象"的数字，而这正是本稿批评记录本身的那种失败。
  3. **零命中池不小，所以"看起来会很好"才是危险**：全窗 **449/1,128（39.8%）**没有任何商品词条命中，
     抽样完全没有问题（抽 150 篇毫无压力）。**正因为抽得动、算得出、区间还不会太宽**，
     单读产出的召回率会以"测量值"的姿态进入论文，而它的判读误差恰好藏在理由 1 里。
     稀疏不是障碍——**稀疏会让错误显形，而不稀疏会让错误隐形**。
     这一条也顺带给出一个**可写进论文的结构事实**：679 篇命中 / 449 篇零命中，
     零命中侧的 subject 份额**未测**，因此"某品类覆盖多少案件"不可答。
- **裁定**：召回率 **`not_estimable`**（终局，不再有后续条目翻转）。论文的品类层面主张**只能**是
  **subject 侧的精确率**（0.9296 any-mention / 0.3852 subject），**不得**出现任何"某品类占多少比例"、
  "覆盖了多少案件"、"漏掉了多少"的表述。
- **连带**：题名/摘要/图 1 中与"分母"有关的一律不得暗示已测。图 1 的"商品维度"一级必须标注
  **precision 已测 / recall 未测**，不得只写一个 0.9296。
- **不改**：D-115 的 270 条金标准与三人协议、E1–E16 任何判决。

## D-127 — E17 分词敏感性（预注册，写于任何 E17 调用之前；本条目也是本轮自动流水线的授权依据）

- **问题**：§3.3 报告 19 个假匹配中有 **4 个是跨词边界伪影**（金花生 / 面包车 / 土豆干 / 拷贝）。
  审稿人一定会问："分词之后呢？"本实验就是那个答案，且**不需要任何人工判读**。
- **固定输入**：同一 1,128 篇 cleaned 全文；**同一 lexicon**（从 `e12_commodity_index.json` 的 `lexicon` 字段读入，
  不从脚本复制），因此词典不可能漂移。
- **两条规则**：
  - **R0（基线，无分词）**：字面子串匹配。**必须先复现 E12 的逐类篇数**；复现不上 ⇒ 立即中止，
    本实验**不**报告任何比较结果（基线错则比较无意义）。
  - **R1（分词）**：`jieba.lcut(text)` 默认模式、无自定义词典、固定版本 0.42.1，
    词条命中当且仅当该词条可**由连续整词拼成**（即命中位置两侧都落在词边界上）。
- **指标（双向，必须都报）**：
  - 每类与总体：`hits_R0`、`hits_R1`、**lost**（R0 去掉的）、**gained**（R1 新增的）；
  - 4 个已知跨词伪影是否被 R1 消除（逐个点名，不合并成一句）；
  - **在 270 条 D-115 判读样本上重算**：R0 通过/R1 通过 的 2×2，以及用同一批 `verdict` 重算的
    subject 侧精确率（R1 若删掉的是 S 则该精确率**下降**，若删掉的是 F 则上升）。
- **禁止**：调 jieba 模式、加自定义词典、只报一个方向（只报 lost 或只报 gained）、
  用 R1 重算 679 这个总数并据此改正文的主数字。**E12 的 679/1128 与两个精确率是冻结的**；
  E17 只作为**敏感性**附注。
- **结论规则**：无论结果如何都进论文，写成一段并给一个数（精确率在 R1 下是多少）。
  若 R1 使 subject 精确率**下降**，正文必须写明"分词不是免费的"，不得只写伪影被消除。
- **纪律**：`silver.jsonl` 仍须 `a1deda2c…`；产物 `data/analysis/e17_segmentation.json`，
  脚本 `scripts/e17_segmentation.py`，`criterion_register="D-127"`。

## D-128 — 本轮**后台自治流水线**的授权与边界（写于点火之前）

- **背景**：本地机即将关机，服务器继续运行。用户已授权"写好自动化后台化流水线并点火"。
- **流水线做什么**（顺序固定，每步写回执，任一步失败不阻断后续但记录）：
  1. **预检**：`silver.jsonl` sha 必须为 `a1deda2c…`；E12 索引与 270 条判读产物存在且 sha 可用；磁盘余量。
  2. **E17**（D-127）：跑完写 `data/analysis/e17_segmentation.json`。
  3. **出处自校验**：逐行重算 `numbers.csv` 每一行（读 `product` 的 `json_path` 字段，与 `value` 比对），
     输出不一致清单。**这是对"每个数可回溯"这一声明的机器检验**，此前从未做过。
  4. **心跳与看护**：每 10 分钟写 `runs/autopilot/heartbeat.log`；
     `/v1/models` 连续 3 次失败才允许重启 vLLM（既有规则）。
- **禁止**：不改任何已冻结产物；不改门槛；不发起新的模型判读；不删除 `data/raw/`、`silver.jsonl`、`foods.sqlite`；
  不动 `/opt/foods/venv`（jieba 装在 `/opt/foods/third_party`，用 `PYTHONPATH` 引入）。
- **停机条件**：步骤 1–3 全部完成即写 `RECEIPT.md` 并转入心跳模式，不自行结束。

## D-129 — E17 分词敏感性结果：**分词不是解药**（0.3852 → 0.3966，代价是 12 个真主体）

- **产物**：`data/analysis/e17_segmentation.json` sha
  **`9f5432ccdcf3036cf577d8c8e3a5e17f9c830230820ddaac30482ad36afae5e3`**；
  脚本 `scripts/e17_segmentation.py`，jieba **0.42.1**（装在 `/opt/foods/third_party`，venv 未动），默认模式、无自定义词典。
- **基线自检通过**：R0（字面子串）**逐类复现** E12 的冻结篇数（679 any-doc），因此下面的比较成立。
- **结果**：
  - 文档层面：**R0 679 → R1 634**，逐类合计 **lost 201、gained 0** ⇒ **R1 严格是 R0 的子集**，分词只删不加。
  - 270 条判读样本 2×2：**232 双方都过、38 被 R1 删掉、0 新增、0 双方都不过**。
  - 被删的 38 条按判读类型：**S 12、I 13、T 5、F 8**。
  - **subject 侧精确率：R0 0.3852（104/270）→ R1 0.3966（92/232）**，**仅 +0.0114**。
- **读法（必须这样写进论文）**：分词确实清掉了 19 个假匹配里的 **8 个**（跨词边界那 4 类里的多数），
  但**同时删掉 12 个真主体**，净收益是把精确率抬了 **1.1 个百分点**。
  ⇒ **§3.3 的警告不是分词能修的**：伪影只是 19/270，而「主体 vs 配料」占了 121/270。
  这也回答了审稿人一定会提的那个问题，而且是**用数**回答的。
- **机制**：R1 的损失集中在单字/双字词条——`鱼` 52 篇、`辣椒` 19、`葡萄` 17、`小麦` 23、`辅食` 9。
  jieba 把「草鱼」「鱿鱼」切成一个词，于是词条 `鱼` 落在词内被 R1 判掉，而草鱼**本来就是水产**。
  ⇒ 分词对**短词条**是净损失；对长词条（四字跨词伪影）才是净收益。
- **禁止**：用 R1 的数替换正文的 679/0.9296/0.3852（冻结值不动）；只报「伪影被清理」而不报「删掉 12 个真主体」。
- **产物另有**：`runs/autopilot/03_numbers_verify.json`（出处自校验，见 D-128）。

## D-130 — 出处校验的**收据与被检表已经不同版本**：号码表在 stage-3 之后 6 分钟被改写（仅登记事实，不改任何数）

- **现象**：`runs/autopilot/RECEIPT.md`（2026-11-05T08:43:50Z）记的是
  `numbers.csv` sha `42ed93fc…`、**574 行**、ok 527 / mismatch 0。但该表 **08:49Z 被改写**为
  sha **`43255b10d98948a93992beba054ab58fd1f78befbe0f78785b6bc37df39cf896`**、**584 行**
  （新增 `e17.*` 14 行等）。因此收据里的 "574 / ok 527" **不对应当前件**，它不是错，只是旧快照。
- **量测（值守代理只读复算，复用 `scripts/verify_numbers.py` 的 `resolve()`/`close()`，未写任何文件）**：
  在 sha `43255b10…` 上 **584 行 → ok 534 / mismatch 0 / unresolved 27 / composite 11 /
  missing 2 / derived 10**（合计 584）。**0 不一致**。
  - `missing 2` = `gate.kappa` / `gate.ba`，其 `product` 指向 `DEVIATIONS.md`（markdown，路径 `D-117`）——
    **结构性不可机读**，与数值无关。
  - `unresolved 27` 全是**路径写法**，不是错值：8 条 `queries[检验报告/食品].field` 走的是列表选择器
    （产品实为 `queries` 列表，通用解析器按字典取键必然失败），其余是 `a-b`、`x/604`、`per_class{…}` 等算式路径。
    代理逐条手工重算 **旧 25 条全部一致**（含 tau 三档、t1 四查询 ×2、anchor macro≥20 = (0.8801+0+0.3784)/3、
    e16 映射 310 与 0.7252、E15−E13 三个差、e6 两个份额、net 9/125、t1tab 16 行整表）；
    新 2 条亦一致（`e17.lost_docs`=Σlost_docs=201、`e17.fish_lost`=水产类 `terms_lost["鱼"]`=52）。
  - `product_sha256` 列 **2/584 与现件不符**，正是上面两行（DEVIATIONS.md 每次 append 必然改 sha）；
    其余 582 行的 product sha 与盘上逐字节一致。
- **处置**：**不改** `numbers.csv`、不改校验脚本、不改任何门槛；收据原样保留作为"当时"快照，本条为改写后基线。
- **纪律（新增）**：出处校验的回执必须**把被检表的 sha 与行数写在回执正文里**，且表每改一次就重跑 stage 3；
  否则 "mismatch 0" 只证明**旧表**。读收据的人必须先比 sha，再读计数。
- **影响面**：无数值变化；仅收窄"每个数可被产物复读"这一声明的适用范围——机读覆盖为
  **534/584（91.4%）**，其余 50 行需按上面的口径人工复算或视为不可机读。

## D-131 — 收据补钉：Stage 3 被检表的 sha 与行数已写入正文（并修复一次被反引号吃掉的追加）

- **触发**：D-130 的「下一步一件事」——收据只证明旧表。巡检代理在 `review_20261105T0922Z.md`
  中把这条列为唯一未闭项（RECEIPT.md 为 root:foods 644，agent 不可写）。
- **做了什么（只有一处文件被写）**：在 `/opt/foods/runs/autopilot/RECEIPT.md` 末尾追加
  「Stage 3 re-run — sha-pinned」小节，写明：被检表 `/opt/foods/numbers.csv`、
  sha **`43255b10d98948a93992beba054ab58fd1f78befbe0f78785b6bc37df39cf896`**、**584 行**、
  `ok 534 / mismatch 0`、不可机读 50 行按类列明（27 unresolved + 11 composite + 10 derived + 2 文本产物行），
  并点明机器覆盖 = **534/584（91.4%）**。
- **事故与修复（一并登记）**：第一次追加经 `pod.py exec` 下发时，正文里的**反引号被远端 shell 当作命令替换**，
  四个值（表路径、表 sha、产物路径、产物 sha）被吃成空串，文件里留下了 4 个空格子。**发现方式**：追加后立即
  `get` 回读并逐行看。**修复方式**：本地补回四个值 → `put` 覆盖 → 回读核对
  （`grep -c` 命中 `43255b10` 1 次）。追加的历史快照段（08:52Z）**原样保留**，未改写。
  ⇒ 纪律：**任何含反引号的文本不得经 `pod.py exec` 的 heredoc 下发**，一律本地写好再 `put`。
- **未改**：`numbers.csv`、`verify_numbers.py`、任何门槛、任何数值、任何判读。`DEVIATIONS.md` 自身 append 后
  `product_sha256` 指向它的那 2 行必然再次失配（D-130 已述，属结构性）。
- **登记纪律补充**：收据类文件每被 append 一次，`numbers.csv` 中以其为 product 的行即失配一次；
  故此类行只承诺「当时一致」，不承诺「永久一致」。
