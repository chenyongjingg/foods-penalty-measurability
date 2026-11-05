# DECISIONS.md — D 登记簿索引（E6–E9 与全部既有条目）

本文件是**索引**；权威登记全文在 `DEVIATIONS.md`（同一份登记簿，v7 计划书称之为 DECISIONS.md）。
两者一并进入发布包；任何 D 编号的含义以 `DEVIATIONS.md` 中该条正文为准。

- 条目数：79
- 语料冻结规则：D-71
- v7 补跑实验：D-72…D-79

| 编号 | 标题 |
|---|---|
| D-1 | Deployment: venv + daemon instead of docker-compose |
| D-2 | D1' primary intake: national penalty portal (cfws.samr.gov.cn) |
| D-3 | RASFF (D3b) has no machine-readable bulk distribution |
| D-4 | Dual-channel independence form |
| D-5 | Third channel = 5-sample majority vote, not a stronger model |
| D-6 | Municipal adapters are calibration-pending |
| D-7 | Time authority |
| D-8 | openFDA (D3a) sampling cap |
| D-9 | Operational definition of E1 agreement |
| D-10 | PDF budget and backfill |
| D-11 | cfws text must come from the PDF |
| D-12 | The cfws portal serves at most 200 rows per query |
| D-13 | English channel prompts revised after an instrumentation failure |
| D-14 | Prompt versioning and wholesale re-labelling |
| D-15 | Confidence tiers and the main corpus |
| D-16 | The US corpus is not part of the ecology network |
| D-17 | Displacement coding requires an enforcement context |
| D-18 | Anchor engine: penalty-clause basis + fact disambiguation |
| D-19 | Intake proximity requirement removed |
| D-20 | openFDA dates are YYYYMMDD; every date reader now goes through `as_date` |
| D-21 | Hawkes remains degenerate; the nonparametric fallback replaces the claim |
| D-22 | D4 timeline: static court/spp listings + rule typing + event clustering |
| D-23 | Tier sensitivity: the network estimate is not robust to tier choice |
| D-24 | H1/H3 uncertainty: document bootstrap, and a stricter H3 rule |
| D-25 | Prompt codebook v2 pilot rejected: the disagreement is capability, not wording |
| D-26 | The ecosystem graph is actor-only; type-level terms are not nodes |
| D-27 | E5 uses the same high tier as every other experiment; E1 also reports pooled entity F1 |
| D-28 | Labelling rejections are not missing at random — and the old coverage figure was wrong |
| D-29 | Stack substitutions: networkx for PyG, no vector index, no external pager |
| D-30 | Protocol v2: the 6,000-character cap is removed (whole-corpus re-label) |
| D-31 | Corpus expansion is automatic but pre-registered (Plan §6.2 / P063) |
| D-32 | D1' keyword sensitivity (Plan P115) |
| D-33 | Staleness stamp on every network metric |
| D-34 | Anchor engine: fall back to all cited articles before the fact lexicon |
| D-35 | Reachable corpus is capped by the portal, not by the query list |
| D-36 | The portal's second query slot is a facet, not a full-text field |
| D-37 | Fail-fast preflight in the label stage |
| D-38 | D1' municipal layer: measured yield, and why cfws carries the corpus |
| D-39 | Law-name normalization in the anchor engine (instrument bug) |
| D-40 | "0 events" must carry its denominator |
| D-41 | GraphML export failed silently and left a 0-byte file |
| D-42 | E5: the chi-square number must not survive its own assumption check |
| D-43 | The E1 mean is taken over a subset; the subset is now printed |
| D-44 | Re-label noise band and tier-flip rate under the frozen v2 protocol |
| D-45 | A list-valued entity field killed a 77-minute extract run (grounding now counts what it drops) |
| D-46 | Protocol v2 did not remove the length bias in labelling rejections |
| D-47 | Re-deriving a tier from the rounded F1 disagrees with the label stage |
| D-48 | The apparent 04:00Z labelling discontinuity was query composition, not instrument drift |
| D-49 | The high tier is selected by document genre, not by sampling design |
| D-50 | E2 counts nodes, but edges are bounded by documents that name two actors |
| D-51 | E5's main-corpus comparison is degenerate: the tier filter removes the variation it tests |
| D-52 | The GraphML export verdict never reached network_metrics.json |
| D-53 | Plan P095's type-shrinkage trigger is now met; the unstable types are the ones the network needs |
| D-54 | Correction to a sub-count in D-49: 7/79, not 3/79, is the graph's binding structure |
| D-55 | The self-consistency ladder could be silently undone by the next retier |
| D-56 | Majority voting can raise agreement by making both channels say less |
| D-57 | E4's zero is a sensitivity and construct limit, not "no displacement" |
| D-58 | The anchor gate on the rebuilt corpus is dominated by classes it cannot predict |
| D-59 | Ladder step 2 (self-training) cannot run in this environment |
| D-60 | A zero category column made chi-square raise, and the crash left a stale compare.json |
| D-61 | A crashed analyze module exited 0 and the gate read last cycle's file |
| D-62 | Majority voting dropped `normalized`, so a voted document changed graph node identity |
| D-63 | The post-ladder E1 pools two decoding regimes and only its own number was kept |
| D-64 | A ladder-promoted document entered the corpus under a different entity rule |
| D-65 | A no-op ladder re-run would have relabelled the mixed E1 as `pre_ladder` |
| D-66 | `tier_shrunk.json` claimed to match the network build after D-64 |
| D-67 | A no-op `retier` reported every anchored document as "changed" |
| D-68 | The ladder overwrote single-shot channels with no snapshot, and the pre-registered E1 had to be rebuilt from archives |
| D-69 | Correction to D-62: `normalized` was never present on the final entity set at all |
| D-70 | The release bundle shipped data and code but none of the numbers the paper quotes |
| D-71 | The corpus had no stopping rule, so "the final release" had no definition |
| D-72 | v7 计划书 E6–E9 的登记与编号重映射（先登记，后执行） |
| D-73 | E6 的三个接口决定：事实段匹配、食品词典、地域口径 |
| D-74 | E7 行为—危害类型学的构建规则（先定后跑） |
| D-75 | E8 中美对照：映射表、可估性判据、样本量差异 |
| D-76 | 每个确定性抽取器上线前的负对照（沿用计划书编号） |
| D-77 | 确定性结果与冻结的 LLM 结果冲突时，以确定性为准（沿用计划书编号） |
| D-78 | E9（QLoRA 自训练受控复跑）：当前状态 |
| D-79 | E6 负对照未过底线后的处置：粗粒度降级、事后诊断、以及 E7 的一致率波动 |
