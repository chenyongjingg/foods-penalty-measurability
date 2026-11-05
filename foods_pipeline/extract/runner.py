"""L4 final extraction, E1 evaluation, and the automatic decoding ladder.

E1 (Plan §6.1): target = dual-channel agreement >= 0.85 AND anchor F1 >= 0.80;
floor = 0.75 / 0.70. Failure triggers, in order:
  1. self-consistency decoding (5 samples, majority vote) for low/reject docs;
  2. entity-type shrinkage if agreement stays < 0.75 (Plan §6.2 E1);
  3. self-training trigger (pseudo-labels) when high-tier volume is sufficient.
Every action is recorded in state/kv so the paper can report the ladder taken.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..common import (cfg, get_logger, path_of, read_json, utc_iso, write_json)
from ..label import align, prompts
from ..label.anchors import anchor_f1, anchor_pairs, anchor_support
from ..label.llm import LLMClient, parse_json
from ..manifest import Manifest

# Entity-type shrink rule, fixed before applying it to the corpus: a type is
# retained only if its own per-type agreement F1 is >= label.agreement_floor
# (0.75). The instruction is "drop types the two channels cannot agree on",
# not "keep the types that flatter the analysis".  A type also needs enough
# mentions for its F1 to mean anything; a type seen twice can score 1.0 by luck.
SHRINK_MIN_F1 = 0.75
SHRINK_MIN_SUPPORT = 20

# Plan §5.2 fixes the span-overlap threshold at 0.5 and align.py promises the
# {0.3, 0.5, 0.7} sensitivity in the evaluation step; it is computed here from
# the stored per-channel spans, so it costs no model calls.
TAU_SENSITIVITY = (0.3, 0.5, 0.7)


def _squash(s: str | None) -> str:
    """Strip whitespace/punctuation masks so PDF spacing and PII asterisks do
    not make two spellings of the same party look different."""
    if not s:
        return ""
    return "".join(ch for ch in str(s) if not ch.isspace() and ch not in "*＊·")


class Extractor:
    def __init__(self, manifest: Manifest | None = None):
        self.m = manifest or Manifest()
        self.log = get_logger("extract")
        self.silver = path_of("data") / "silver" / "silver.jsonl"
        self.dataset = path_of("data") / "extracted" / "dataset.jsonl"
        self.e1_path = path_of("data") / "metrics" / "e1.json"

    def _load(self) -> list[dict]:
        if not self.silver.exists():
            return []
        recs = []
        with open(self.silver, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    recs.append(json.loads(line))
        return recs

    def _save(self, recs: list[dict]) -> None:
        tmp = self.silver.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(self.silver)

    def _channels(self, r: dict) -> tuple[list[dict], list[dict]]:
        ch = r.get("channels") or {}
        return ch.get("a") or [], ch.get("b") or []

    def _agreement(self, recs: list[dict], types: set[str] | None = None,
                   tau: float | None = None) -> tuple[float, dict]:
        """Mean document-level micro-F1 and per-type F1 over grounded entities."""
        if tau is None:
            tau = float(cfg("label.span_tau", 0.5))
        tps: Counter = Counter(); na: Counter = Counter(); nb: Counter = Counter()
        per_doc = []
        for r in recs:
            if "channels" not in r:
                # Records written before per-channel storage: keep their
                # document-level F1 so they are not silently dropped. They
                # cannot contribute to the per-type (shrunk) view.
                if types is None and r.get("metrics"):
                    per_doc.append(r["metrics"]["agreement_f1"])
                continue
            a, b = self._channels(r)
            if types is not None:
                a = [e for e in a if e["type"] in types]
                b = [e for e in b if e["type"] in types]
            if not a and not b:
                continue
            pairs = align.match(a, b, tau)
            for x, _, _ in pairs:
                tps[x["type"]] += 1
            for e in a:
                na[e["type"]] += 1
            for e in b:
                nb[e["type"]] += 1
            tp = len(pairs)
            p = tp / len(a) if a else 0.0
            rr = tp / len(b) if b else 0.0
            per_doc.append(2 * p * rr / (p + rr) if (p + rr) else 0.0)
        per_type = {}
        for t in set(tps) | set(na) | set(nb):
            p = tps[t] / na[t] if na[t] else 0.0
            rr = tps[t] / nb[t] if nb[t] else 0.0
            per_type[t] = {"f1": round(2 * p * rr / (p + rr), 4) if (p + rr) else 0.0,
                           "n_a": na[t], "n_b": nb[t], "tp": tps[t]}
        mean = sum(per_doc) / len(per_doc) if per_doc else 0.0
        return round(mean, 4), per_type

    def _protocol(self) -> dict:
        """The labelling protocol that produced this corpus (D-30).

        E1 is only interpretable next to the input it was measured on, and the
        previous revision could not answer "was any document truncated?" after
        the fact. The prompt hashes pin the template text; the cap and the
        observed lengths show whether the cap bound.
        """
        llm = cfg("llm", {}) or {}
        return {
            "prompt_version": prompts.version(),
            "doc_text_chars": prompts.doc_chars(),
            "max_tokens": {k: (llm.get(k) or {}).get("max_tokens")
                           for k in ("channel_a", "channel_b", "adjudicator")},
            "model": (llm.get("channel_a") or {}).get("model"),
            "span_tau": float(cfg("label.span_tau", 0.5)),
            "entity_types": sorted(cfg("label.entity_types", [])),
        }

    def _input_chars(self) -> dict:
        cap = prompts.doc_chars()
        with self.m.conn() as c:
            rows = c.execute(
                "SELECT n_chars, (error LIKE 'label_%') AS pf FROM docs "
                "WHERE n_chars IS NOT NULL AND stage IN ('labeled','extracted','clean')"
            ).fetchall()
        have = sorted(r["n_chars"] for r in rows if not r["pf"])
        failed = sorted(r["n_chars"] for r in rows if r["pf"])

        def pct(xs, p):
            if not xs:
                return None
            k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
            return xs[k]

        return {"cap": cap, "labelled_n": len(have), "labelled_p50": pct(have, 50),
                "labelled_p99": pct(have, 99), "labelled_max": max(have) if have else None,
                "over_cap": sum(1 for x in have if x > cap),
                "parse_failed_n": len(failed), "parse_failed_p50": pct(failed, 50),
                "parse_failed_p90": pct(failed, 90)}

    def _coverage(self, n_labelled: int) -> dict:
        """Share of the admitted frame that produced a silver record.

        The earlier figure divided by the number of documents *currently* at
        stage `clean`, which is a moving count (documents leave it as they are
        labelled) and produced ratios above 1.  The frame is labelled +
        still-clean; parse failures are reported separately because they are
        not missing at random (they are the longest documents, DEVIATIONS D-28).
        """
        with self.m.conn() as c:
            n_fail = c.execute("SELECT COUNT(*) FROM docs WHERE error LIKE "
                               "'label_parse_failed%'").fetchone()[0]
            n_trunc = c.execute("SELECT COUNT(*) FROM docs WHERE error LIKE "
                                "'label_truncated_output%'").fetchone()[0]
            n_nocat = c.execute("SELECT COUNT(*) FROM docs WHERE error LIKE "
                                "'label_no_consensus_category%'").fetchone()[0]
            n_clean = c.execute("SELECT COUNT(*) FROM docs WHERE stage='clean' "
                                "AND (error IS NULL OR error='')").fetchone()[0]
        admitted = n_labelled + n_clean
        return {"labelled": n_labelled, "pending_clean": n_clean,
                "label_parse_failed": n_fail, "label_truncated_output": n_trunc,
                "label_no_consensus_category": n_nocat,
                "rate": round(n_labelled / admitted, 4) if admitted else None}

    def _pooled(self, recs: list[dict], tau: float | None = None) -> float | None:
        """Entity-level pooled micro-F1 = 2*TP / (|A|+|B|) over the corpus.

        Plan §5.2 names the statistic "entity-level span-overlap F1"; the
        headline E1 number is the pre-registered document-level mean (D-9).
        The pooled figure weighs every entity equally instead of every
        document, so a corpus of short documents cannot outvote a long one;
        it is reported next to the headline, never instead of it.
        """
        if tau is None:
            tau = float(cfg("label.span_tau", 0.5))
        tp = na = nb = 0
        for r in recs:
            if "channels" not in r:
                continue
            a, b = self._channels(r)
            if not a and not b:
                continue
            tp += len(align.match(a, b, tau))
            na += len(a)
            nb += len(b)
        return round(2 * tp / (na + nb), 4) if (na + nb) else None

    def evaluate_e1(self, recs: list[dict]) -> dict:
        if not recs:
            return {"n": 0, "status": "no_data"}
        mean, per_type = self._agreement(recs)
        # Documents where both channels extracted nothing have no agreement to
        # score and are skipped by `_agreement`. That exclusion must be counted,
        # otherwise the mean is taken over a subset the reader cannot see.
        zero_ent = 0
        for r in recs:
            if "channels" not in r:
                continue
            a, b = self._channels(r)
            if not a and not b:
                zero_ent += 1
        stable = {t for t, v in per_type.items()
                  if v["f1"] >= SHRINK_MIN_F1 and v["n_a"] + v["n_b"] >= SHRINK_MIN_SUPPORT}
        shrunk, per_type_shrunk = self._agreement(recs, stable) if stable else (None, {})
        # Only records that carry the raw per-channel spans can be re-scored at
        # another tau; records written before per-channel storage were scored at
        # 0.5 and are excluded rather than mixed in.
        with_ch = [r for r in recs if "channels" in r]
        tau_sens = {str(t): {"mean_agreement": self._agreement(with_ch, tau=t)[0],
                            "n": len(with_ch)} for t in TAU_SENSITIVITY}
        # Anchor F1 counts only statute-grounded anchors (penalty clause or
        # clause + fact disambiguation). Fact-only anchors are reported
        # separately: they are deterministic, but they key off the same phrases
        # the LLM reads, so they are a weaker independent check and must not be
        # pooled with the statute anchors.
        pairs, fact_only = anchor_pairs(recs)
        af = anchor_f1(pairs)
        # Support travels with the macro average (D-18/D-58).
        af["support"] = anchor_support(pairs)
        af["fact_only_docs"] = fact_only
        # Basis mix, so the anchor figure can be read together with how the
        # categories were reached (D-34: cited_statute is the all-cited-articles
        # fallback, still statute-grounded).
        by_basis: dict[str, int] = {}
        for r in recs:
            b = ((r.get("anchor") or {}).get("basis")) or "none"
            by_basis[b] = by_basis.get(b, 0) + 1
        af["basis_counts"] = dict(sorted(by_basis.items()))
        # Extraction-level anchor check (Plan §5.2 channel ②: format validation
        # of party / case number). This is a separate statistic from the
        # category mapping: it asks whether the LLM's END_USER and PENALTY_EVENT
        # carry the fields the document states, not whether it classified right.
        ax = {"party": [0, 0], "case_no": [0, 0]}
        for r in recs:
            f = (r.get("anchor") or {}).get("fields") or {}
            ents = r.get("entities") or []
            party = _squash(f.get("party"))
            if party:
                ax["party"][1] += 1
                if any(party and (party in _squash(e["text"]) or _squash(e["text"]) in party)
                       for e in ents if e["type"] == "END_USER"):
                    ax["party"][0] += 1
            case = _squash(f.get("case_no"))
            if case:
                ax["case_no"][1] += 1
                if any(case and case in _squash(e["text"])
                       for e in ents if e["type"] == "PENALTY_EVENT"):
                    ax["case_no"][0] += 1
        af["extraction"] = {k: {"hit": v[0], "docs": v[1],
                                "rate": round(v[0] / v[1], 4) if v[1] else None}
                            for k, v in ax.items()}
        at = float(cfg("label.agreement_target")); af_ = float(cfg("label.agreement_floor"))
        at_a = float(cfg("label.anchor_target")); af_a = float(cfg("label.anchor_floor"))
        anchor_val = af.get("f1") or 0.0
        # Macro-F1 over a handful of anchor-eligible documents is decided by
        # classes with zero support, so the anchor threshold is only read when
        # there are enough documents to estimate it. Below that the anchor is
        # reported as not evaluable and E1 is graded on agreement alone, with
        # the suffix making the difference visible in the gate table.
        min_n = int(cfg("label.anchor_min_n", 30))
        anchor_ok = af.get("n", 0) >= min_n
        suffix = "" if anchor_ok else "_anchor_insufficient"
        if mean >= at and anchor_ok and anchor_val >= at_a:
            status = "target_met"
        elif mean >= af_ and anchor_ok and anchor_val >= af_a:
            status = "floor_met"
        elif not anchor_ok and mean >= at:
            status = "target_met" + suffix
        elif not anchor_ok and mean >= af_:
            status = "floor_met" + suffix
        else:
            status = "failed" + suffix
        # Split by language: the CN and US corpora have different prompts,
        # different anchor eligibility and very different tier yields, so a
        # pooled agreement figure can hide a failing channel on one side.
        by_lang = {}
        for lang in sorted({r.get("lang") for r in recs if r.get("lang")}):
            sub = [r for r in recs if r.get("lang") == lang]
            m_l, pt_l = self._agreement(sub)
            stable_l = sorted(t for t, v in pt_l.items()
                              if v["f1"] >= SHRINK_MIN_F1
                              and v["n_a"] + v["n_b"] >= SHRINK_MIN_SUPPORT)
            by_lang[lang] = {"n": len(sub), "mean_agreement": m_l,
                             "pooled_micro_f1": self._pooled(sub),
                             "stable_types": stable_l,
                             "tiers": dict(Counter(r["tier"] for r in sub))}
        # Plan P095 fallback, reported as a decision record rather than folded
        # into `status`: E1 stays graded on the full entity-type set, and the
        # shrunk figure is shown next to it. Changing the status string to the
        # shrunk value would let a post-hoc type selection masquerade as E1.
        ladder = {"triggered": bool(recs) and mean < af_,
                  "rule": f"keep types with per-type F1 >= {SHRINK_MIN_F1} and "
                          f"support >= {SHRINK_MIN_SUPPORT}",
                  "stable_types": sorted(stable),
                  "agreement_shrunk": shrunk,
                  "note": "Plan P095 type shrinkage; status above is full-type"}
        pooled = self._pooled(recs)
        # Plan §5.2 evidence ③ is a literature calibration, not a gold-standard
        # comparator: the published figures are entity F1 against human
        # annotation on a different task, and ours is dual-channel agreement.
        # It is recorded as context with that caveat spelled out, so it cannot
        # be quoted as an accuracy.
        lit = {"source": "CAEC_LLM (ISPRS Int. J. Geo-Inf. 2026; Plan §2.1)",
               "reported_zero_shot_f1": 0.70, "reported_finetuned_f1": 0.82,
               "our_pooled_micro_f1": pooled,
               "note": "context only — published F1 is against a human gold "
                       "standard on a different task; ours is dual-channel "
                       "agreement and is not numerically comparable"}
        return {"n": len(recs), "mean_agreement": mean, "by_lang": by_lang,
                "n_zero_entities": zero_ent,
                "n_scored_agreement": len(recs) - zero_ent,
                "pooled_micro_f1": pooled, "literature_calibration": lit,
                "protocol": self._protocol(), "input_chars": self._input_chars(),
                "mean_agreement_shrunk": shrunk,
                "stable_types": sorted(stable),
                "tau_sensitivity": tau_sens, "ladder": ladder,
                "per_type": per_type, "per_type_shrunk": per_type_shrunk,
                "anchor_f1": af, "status": status,
                "thresholds": {"agreement_target": at, "agreement_floor": af_,
                               "anchor_target": at_a, "anchor_floor": af_a},
                "tier_counts": dict(Counter(r["tier"] for r in recs)),
                "coverage": self._coverage(len(recs)),
                # Model output that could not be grounded verbatim (D-45).
                # Cumulative for this process; a non-zero count is a fact about
                # the model's compliance, not a licence to repair its spans.
                "align_ground_malformed": align.malformed_stats(),
                "at_utc": utc_iso()}

    def _vote_channel(self, llm: LLMClient, channel: str, cfg_name: str, lang: str,
                      text: str, n_samples: int, temp: float) -> tuple[list[dict], str | None, float]:
        c = cfg(cfg_name)
        outs = llm.chat(c["model"], prompts.render(channel, lang, text),
                        temperature=temp, max_tokens=c["max_tokens"], n=n_samples)
        cats, ents = [], Counter()
        # Carry the model's normalised form through the vote. Without it the
        # voted entities reach the dataset as `normalized == text`
        # (extract/runner.py, dataset writer), so the same operator written two
        # ways in one document becomes two graph nodes and gains an edge to
        # itself. Voting must not change node identity (D-62).
        norm: dict[tuple[str, str], str] = {}
        from ..label.silver import _cat, valid_types
        keep_types = valid_types()
        for o in outs:
            j = parse_json(o)
            if not j:
                continue
            cats.append(_cat(j.get("violation_category"))[0])
            for e in align.ground(text, j.get("entities", [])):
                if e["type"] in keep_types:
                    ents[(e["type"], e["text"])] += 1
                    if e.get("normalized"):
                        norm[(e["type"], e["text"])] = e["normalized"]
        cat = Counter(cats).most_common(1)[0][0] if cats else None
        purity = round(len([x for x in cats if x == cat]) / len(cats), 3) if cats else 0.0
        keep = []
        for (t, x), k in ents.items():
            if k <= n_samples / 2:
                continue
            start = text.find(x)
            item = {"type": t, "text": x, "start": start, "end": start + len(x)}
            if norm.get((t, x)):
                item["normalized"] = norm[(t, x)]
            keep.append(item)
        return keep, cat, purity

    def _snapshot_preladder(self, recs: list[dict]) -> Path | None:
        """Copy the corpus to `data/archive/preladder_<stamp>` before voting.

        Only the single-shot channels matter: a document that has already been
        voted has no original left to lose. Written only when at least one
        document is about to be voted, so a no-op cycle leaves no archive.
        """
        todo = [r for r in recs
                if r.get("tier") in ("low", "reject")
                and r.get("decoding") != "self_consistency"]
        if not todo:
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
        d = path_of("data") / "archive" / f"preladder_{stamp}"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "silver.jsonl"
        tmp = p.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(p)
        self.log.info("pre-ladder snapshot: %s (%d docs, %d to vote)",
                      p, len(recs), len(todo))
        return p

    def _selfconsistency(self, recs: list[dict]) -> int:
        """Plan §6.2 ladder step 1: 5-sample majority vote per channel, then
        re-measure agreement between the two stabilized channels."""
        llm = LLMClient()
        n_samples = int(cfg("llm.selfconsistency.samples", 5))
        temp = float(cfg("llm.selfconsistency.temperature", 0.7))
        tau = float(cfg("label.span_tau", 0.5))
        target = float(cfg("label.agreement_target"))
        floor = float(cfg("label.agreement_floor"))
        changed = 0
        todo = []
        for i, r in enumerate(recs):
            if r["tier"] in ("low", "reject") and r.get("decoding") != "self_consistency":
                doc = self.m.get(r["doc_id"])
                if doc and doc.get("text_path"):
                    todo.append((i, r, Path(doc["text_path"]).read_text(encoding="utf-8")))
        from concurrent.futures import ThreadPoolExecutor
        workers = max(1, int(cfg("label.workers", 4)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            votes = list(pool.map(
                lambda t: (self._vote_channel(llm, "alpha", "llm.channel_a", t[1]["lang"], t[2],
                                              n_samples, temp),
                           self._vote_channel(llm, "beta", "llm.channel_b", t[1]["lang"], t[2],
                                              n_samples, temp)),
                todo))
        density_before = [sum(len(x) for x in (self._channels(t[1]))) for t in todo]
        density_after: list[int] = []
        for (i, r, text), ((keep_a, cat_a, pur_a), (keep_b, cat_b, pur_b)) in zip(todo, votes):
            density_after.append(len(keep_a) + len(keep_b))
            p, rr, f1 = align.micro_f1(keep_a, keep_b, tau)
            r["channels"] = {"a": keep_a, "b": keep_b, "cat_a": cat_a, "cat_b": cat_b}
            # Write the exact value as well as the rounded one: retier.py derives
            # tiers from `agreement_f1_exact`, so leaving it at the pre-ladder
            # value would let a later retier revert this promotion (D-47).
            r["metrics"].update({"agreement_f1": round(f1, 4),
                                 "agreement_f1_exact": f1,
                                 "f1_source": "self_consistency_vote",
                                 "precision": round(p, 4),
                                 "recall": round(rr, 4), "adjudicated": True})
            r["decoding"] = "self_consistency"
            r["selfcons_purity"] = {"a": pur_a, "b": pur_b}
            # Entity rule must be the label protocol's, not channel A's: when
            # the channels agree on both the mention set and the category,
            # silver keeps the matched intersection (`align.match`), so a
            # promoted document built from A alone would enter the main corpus
            # under a different construction rule than every other high-tier
            # document (D-64). Below target the record stays a vote — the same
            # role the adjudicator plays in silver.
            if f1 >= target and cat_a and cat_a == cat_b:
                r["entities"] = [a for a, _b, _s in align.match(keep_a, keep_b, tau)]
                r["entity_rule"] = "intersection"
            else:
                r["entities"] = keep_a
                r["entity_rule"] = "channel_a_vote"
            if cat_a and cat_a == cat_b:
                r["violation_category"] = cat_a
            anchor_pass = bool(r["anchor"]["category"] and
                               r["violation_category"] == r["anchor"]["category"])
            r["anchor_pass"] = anchor_pass
            if f1 >= target and (anchor_pass or r.get("lang") != "zh"):
                r["tier"] = "high"
            elif f1 >= floor:
                r["tier"] = "medium"
            else:
                r["tier"] = "low"
            changed += 1
        # Majority voting (>= 3 of 5 samples) makes both channels sparser, and
        # agreement measured on two sparser sets can rise without the extractor
        # becoming more accurate. A fall in density next to a rise in F1 is
        # sparsity, not accuracy (D-56), so both are recorded.
        self.ladder_stats = {
            "docs": changed,
            "entity_density_before": (round(sum(density_before) / len(density_before), 3)
                                      if density_before else None),
            "entity_density_after": (round(sum(density_after) / len(density_after), 3)
                                     if density_after else None),
            "note": ("Density is entities per document summed over both channels. "
                     "Read the post-ladder agreement next to these two numbers."),
        }
        return changed

    def run(self) -> dict:
        recs = self._load()
        e1 = self.evaluate_e1(recs)
        actions = []
        if recs and e1["status"].startswith("failed"):
            # The ladder stabilises only the low/reject documents, so the
            # headline E1 it produces pools two decoding regimes: 5-sample
            # majority votes for those documents and the original single-shot
            # channels for everything already high/medium. The post-ladder
            # number is a different estimator and cannot be compared with the
            # pre-ladder one as "before and after" (D-55, D-56). Keep both, and
            # publish the mixture so the pooled figure is readable (D-63).
            pre = {"mean_agreement": e1.get("mean_agreement"),
                   "status": e1.get("status"),
                   "by_lang": {k: v.get("mean_agreement")
                               for k, v in (e1.get("by_lang") or {}).items()},
                   "tier_counts": e1.get("tier_counts"), "n": e1.get("n"),
                   "n_scored_agreement": e1.get("n_scored_agreement")}
            # D-65: `pre` is only the pre-registered single-shot E1 when the
            # corpus entering this process had no voted documents. If an
            # earlier cycle already ran the ladder, `pre` is a mixed estimate
            # (votes on some documents, single-shot elsewhere) and must not be
            # labelled `pre_ladder`.
            n_voted_before = sum(1 for r in recs
                                 if r.get("decoding") == "self_consistency")
            # Snapshot before any channel is replaced. The 10:19Z cycle voted 22
            # newly collected documents that no archive contained, so their
            # single-shot channels are gone and the pre-registered E1 can no
            # longer be scored for them (D-68). One file per voting cycle is
            # cheap; losing the original channels is not.
            self._snapshot_preladder(recs)
            changed = self._selfconsistency(recs)
            ladder_stats = getattr(self, "ladder_stats", {})
            actions.append({"action": "self_consistency", "docs": changed,
                            "stats": ladder_stats})
            write_json(path_of("data") / "metrics" / "ladder.json",
                       {**ladder_stats, "at_utc": utc_iso()})
            e1 = self.evaluate_e1(recs)
            # Attach `pre_ladder` only when this process re-decoded something
            # and the starting corpus was entirely single-shot. Otherwise carry
            # a value recorded by an earlier cycle, if any (D-63, D-65).
            if changed and n_voted_before == 0:
                e1["pre_ladder"] = pre
            else:
                prev = read_json(self.e1_path) or {}
                if prev.get("pre_ladder"):
                    e1["pre_ladder"] = prev["pre_ladder"]
            n_voted = sum(1 for r in recs if r.get("decoding") == "self_consistency")
            e1["decoding_mix"] = {
                "self_consistency": n_voted, "single_shot": len(recs) - n_voted,
                "note": ("The headline agreement pools these two regimes; report "
                         "the mixture with it. Only single_shot documents are "
                         "measured on the pre-registered protocol.")}
            self._save(recs)
            if e1["status"].startswith("failed"):
                high = sum(1 for r in recs if r["tier"] == "high")
                # Ladder step 2 has two preconditions that are easy to conflate:
                # enough high-tier documents, and a trainer that can actually
                # run. Record both, so "requested" can never be read as "done".
                try:
                    import importlib.util as _ilu
                    trainer_ok = bool(_ilu.find_spec("peft"))
                except Exception:
                    trainer_ok = False
                if high < 500:
                    actions.append({"action": "self_training_not_triggered",
                                    "docs": high, "threshold": 500,
                                    "note": "high tier below the 500-document trigger"})
                if high >= 500:
                    train = path_of("data") / "train" / "selftrain.jsonl"
                    train.parent.mkdir(parents=True, exist_ok=True)
                    with open(train, "w", encoding="utf-8") as f:
                        for r in recs:
                            if r["tier"] == "high":
                                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    actions.append({"action": "self_training_requested", "docs": high,
                                    "path": str(train), "trainer_available": trainer_ok,
                                    "note": ("see scripts/train_qlora.py; requested only, "
                                             "not performed" if not trainer_ok else
                                             "trainer available (peft importable)")})
                if e1["mean_agreement"] < float(cfg("label.agreement_floor")):
                    actions.append({"action": "shrink_entity_types",
                                    "to": e1.get("stable_types"),
                                    "shrunk_agreement": e1.get("mean_agreement_shrunk"),
                                    "note": f"types with per-type F1 >= {SHRINK_MIN_F1}; "
                                            "Plan §6.2 E1 fallback"})
        if "decoding_mix" not in e1:
            n_voted = sum(1 for r in recs if r.get("decoding") == "self_consistency")
            e1["decoding_mix"] = {
                "self_consistency": n_voted, "single_shot": len(recs) - n_voted,
                "note": ("Documents already stabilised in an earlier cycle stay "
                         "voted; the mix is reported even when the ladder does "
                         "not run again (D-63).")}
        write_json(self.e1_path, e1)

        # Flatten to the analysis dataset; only high+medium enter the main corpus.
        n_rows = 0
        docs_out = []
        self.dataset.parent.mkdir(parents=True, exist_ok=True)
        with open(self.dataset, "w", encoding="utf-8") as f:
            for r in recs:
                # Main estimate uses the high-confidence tier only (Plan §5.2).
                # Medium (the 0.75-0.85 floor band) and low are kept in the
                # file with main_corpus=false so sensitivity runs can use them
                # without re-labelling.
                main = r["tier"] == "high"
                docs_out.append({k: r[k] for k in ("doc_id", "source", "lang", "tier",
                                                   "violation_category", "anchor_pass",
                                                   "metrics", "text_sha")})
                for e in r["entities"]:
                    row = {"doc_id": r["doc_id"], "source": r["source"], "lang": r["lang"],
                           "tier": r["tier"], "main_corpus": main,
                           "category": r["violation_category"],
                           "entity_type": e["type"], "text": e["text"],
                           "normalized": e.get("normalized") or e["text"],
                           "confidence": e.get("confidence", 0.6),
                           "text_sha": r["text_sha"]}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n_rows += 1

        # Mark clean docs as extracted (whether or not they entered the corpus).
        for r in recs:
            if self.m.get(r["doc_id"]) and self.m.get(r["doc_id"])["stage"] == "labeled":
                self.m.set_stage(r["doc_id"], "extracted",
                                 note=f"tier={r['tier']};rows={len(r['entities'])}")
        stats = {"docs": len(recs), "entity_rows": n_rows, "e1": e1["status"],
                 "actions": actions, "at_utc": utc_iso()}
        self.m.kv_set("stage_status:extract", stats)
        self.m.kv_set("actions:ladder", actions)
        return stats
