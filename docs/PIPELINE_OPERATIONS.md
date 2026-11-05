# Foods FS-DBI automated pipeline

Implementation of the 2026-11-03 final plan (`数据黑产韧性研究_Foods论文写作计划书_终稿.docx`),
§4 data scheme, §5 seven-layer architecture, §5.2 triple evidence chain, §6.1
experiment matrix.

## What runs

```
L0  daemon (daily 02:00 UTC)  ── scripts/install_daemon.sh
L1  collect                   ── cfws | openfda | rasff | municipal
    events (D4)               ── 两高典型案例 + 总局抽检司 列表页 -> data/events/
L2  clean                     ── text extraction, PII masking, dedupe, D1' intake rule
L3  store                     ── data/raw (append-only) + SQLite manifest state machine
L4  label                     ── channel A/B -> span alignment -> adjudicator -> silver
    extract                   ── tiers, E1 metrics, decoding ladder, analysis dataset
L5  analyze                   ── network / attack / Cox / Hawkes / H2 shocks / tier sensitivity / displacement / comparison
L6  report                    ── reports/daily/report_YYYY-MM-DD.md (+ optional webhook)
```

## Key scientific invariants (do not change silently)

| Invariant | Where |
|---|---|
| Input protocol v2: whole document (cap 20,000 chars; max_tokens A 3,000 / B 4,000 / adjudicator 4,000; vLLM `--max-model-len 23040`); one protocol per corpus | `config/settings.yaml`, `label/prompts.py`, D-30 |
| Anchor category source order: penalty clause → all cited articles → fact lexicon; only the first two enter anchor-F1 | `label/anchors.py`, `extract/runner.py`, D-34 |
| cfws: `quanwen_1` = free text, `quanwen_2` = food facet (a document type there returns 0), ≤200 rows reachable per query | `collect/cfws.py`, D-35, D-36 |
| `label` runs one document synchronously before the pool and aborts on error | `label/silver.py`, D-37 |
| Corpus expansion is automatic but draws only on the pre-registered batch list | `analyze/expansion.py`, `config/expansion_queries.yaml`, D-31 |
| D1' keyword sensitivity is computed over the whole admission frame, including rejected docs | `analyze/keywords.py`, D-32 |
| Law names are normalized (whitespace, amendment parenthetical, leading connector) before the statute lookup; no suffix matching (`食品安全法实施条例` ≠ `食品安全法`) | `label/anchors.py`, D-39 |
| A zero count carries its denominator; `not_estimable` ≠ `no events` | `analyze/displacement.py`, D-40 |
| Sparse E5 tables report Fisher as the test of record; the invalid chi-square is moved under `chi2_unreliable` | `analyze/compare.py`, D-42 |
| Main corpus = high only; medium = D-23 sensitivity, low = exploratory | `extract/runner.py`, `analyze/network.py` |
| Ecosystem graph = actors only (SERVICE_PROVIDER, END_USER); five-type graph is a sensitivity variant | `analyze/network.py`, D-26 |
| D3a openFDA is an E5 comparison corpus — never in CN network/Hawkes/H2 | `analyze/network.py`, `analyze/hawkes.py`, `analyze/shocks.py` |
| Agreement = micro-F1 at IoU τ=0.5 (sensitivity .3/.5/.7) | `label/align.py` |
| Anchor channel is deterministic (statute map), never an LLM | `label/anchors.py` |
| Ambiguous statute sets are excluded from anchor-F1, never guessed | `config/statute_map.yaml` |
| E1 target 0.85/0.80, floor 0.75/0.70; ladder is automatic | `config/settings.yaml`, `extract/runner.py` |
| Government sites ≤1 req/2 s, exponential backoff | `common.RateLimiter`, `http_request` |
| Manifest state machine raw→clean→labeled→extracted→analyzed | `manifest.py` |
| Fixed seed 20261104 for every stochastic step | `config/settings.yaml` |

## Commands (on the pod)

```bash
cd /opt/foods
scripts/start_llm.sh                 # vLLM, Qwen2.5-7B-Instruct (localhost:8000)
source venv/bin/activate
python -m foods_pipeline.cli init
python -m foods_pipeline.cli collect --source cfws
python -m foods_pipeline.cli events        # D4 governance timeline
python -m foods_pipeline.cli clean --limit 200
python -m foods_pipeline.cli label --limit 50
python -m foods_pipeline.cli extract
python -m foods_pipeline.cli analyze
python -m foods_pipeline.cli expand       # §6.2: next pre-registered query batch, if E2 is low
python scripts/retier.py                  # after an anchor-engine change: recompute + re-tier,
                                          # archives silver and writes data/metrics/anchor_*.json
python -m foods_pipeline.cli report
python -m foods_pipeline.cli figures  # L6 manuscript panels -> reports/figures/
python scripts/export_release.py      # P115 open-data bundle + MANIFEST.sha256
python -m foods_pipeline.cli run      # full cycle with lock
python -m foods_pipeline.cli daemon --hour 2
make smoke                            # instrument unit tests (no network/GPU/corpus)
```

## Verification

```bash
python tests/smoke_test.py           # synthetic instrument checks (no GPU, no network)
```

`data/metrics/e1.json`, `data/analysis/gates.json` and the daily report are the
machine-readable audit trail; `state/foods.sqlite` holds per-document stages,
fetch attempts, and stage transitions.

## Operations (pod)

Everything is detached (`setsid`), so an SSH drop does not stop work.

```bash
tail -f /opt/foods/logs/pipeline.log          # stage transitions, warnings
tail -f /opt/foods/logs/vllm.log              # model server
tail -f /opt/foods/logs/daemon.out            # daily cycle
cat /opt/foods/reports/daily/ALERTS.md        # unattended-run self-check
cat /opt/foods/state/vllm.pid                 # kill this pid to restart vLLM
bash /opt/foods/scripts/start_llm.sh          # idempotent: returns if already up
bash /opt/foods/scripts/install_daemon.sh     # daemon + vLLM watchdog, idempotent
```

Status without reading logs:

```bash
cd /opt/foods && FOODS_ROOT=/opt/foods ./venv/bin/python -m foods_pipeline.cli status
```

`status` prints the per-source/per-stage document counts, the last run stats for
each stage, and source health (including `rasff: attempted, unavailable`).

### Re-labelling after a prompt change

The corpus is labelled under one prompt version at a time; a corpus that mixed
versions would make E1 agreement uninterpretable (DEVIATIONS.md D-14).

```bash
cd /opt/foods
./venv/bin/python scripts/relabel_source.py openfda --dry-run   # counts only
./venv/bin/python scripts/relabel_source.py openfda             # reset to clean
./venv/bin/python scripts/relabel_source.py all                 # protocol change: whole corpus
./venv/bin/python scripts/chain_locked.py label extract analyze report
```

`relabel_source.py` archives the old `silver.jsonl` to `data/archive/` before
rewriting it. A change that alters the *input* (document length cap, prompt
text) needs `all`; a change that only affects one source does not.

`relabel_source.py` refuses to run while a `cli label` process is alive (it
would append to the same file). `chain_locked.py` runs the stages under
`state/cycle.lock`, the same lock the daemon takes, so a manual run never
overlaps the 02:00 UTC cycle — two label processes started at once would each
label the same clean documents and append duplicates.

### Corpus scale (observed on 2026-11-04)

- cfws listing pass rate through the D1' intake rule: ~10–15% (document- and
  food-specific queries pass more often than the broad `伪造 ∧ 食品` query).
- PDF fetching is the rate-limiting step (1 req / 2 s). A run with
  `pdf_budget_per_run: 1500` takes roughly 55–70 minutes including listing.
- To reach the E2 floor (400 nodes) expect ~300 clean documents; the pipeline
  keeps every metadata-only row for backfill, so repeated daily runs converge.

## Layout

```
config/          settings, statute map, schema, prompts, 50-site registry
foods_pipeline/  code (collect, clean, label, extract, analyze, report)
scripts/         bootstrap, start_llm, run_cycle, install_daemon
tests/           smoke tests
data/            raw (append-only), clean, silver, extracted, analysis, metrics
state/           foods.sqlite, locks, pid files
logs/            pipeline.log, vllm.log, daemon.out
reports/daily/   daily markdown reports
```
