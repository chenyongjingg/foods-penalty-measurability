"""Silver-standard construction (Plan §5.2).

Per document:
  channel A (prompt alpha, T=0) and channel B (prompt beta, T=0.3) label
  independently; entities are grounded verbatim and aligned at IoU>=tau.
  Agreement = micro-F1. Below target, a stronger adjudicator model resolves.
  Channel ② (deterministic statute anchors) then validates the category.

Tiers (fixed in config):
  high    agreement >= target AND anchor present AND category == anchor
  medium  agreement >= target AND (no anchor OR anchor ambiguous)
  low     disagreement resolved by the adjudicator (or anchor mismatch)
  reject  no usable consensus
Only high+medium enter the main corpus; low enters sensitivity analysis.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..common import append_jsonl, cfg, get_logger, path_of, sha256_text, utc_iso
from ..manifest import Manifest
from . import align, anchors, prompts
from .llm import LLMClient, parse_json

VALID_TYPES = {"SERVICE_PROVIDER", "END_USER", "TACTIC", "DOCUMENT",
               "JURISDICTION", "PENALTY_EVENT"}
VALID_CATS = {"FORGED_INSPECTION_REPORT", "TAMPERED_TRACEABILITY",
              "FAKE_CERTIFICATION", "FALSE_LABELING", "UNLICENSED_OPERATION",
              "OTHER"}


def valid_types() -> set[str]:
    """Entity types the protocol accepts.

    Read from config so the schema lives in one place: the type list was
    duplicated between `label.entity_types` and a hard-coded set here, and
    editing the config silently had no effect (DEVIATIONS.md M-7). An unknown
    type in the config is a hard error, not a silent drop.
    """
    wanted = set(cfg("label.entity_types", sorted(VALID_TYPES)) or [])
    unknown = wanted - VALID_TYPES
    if unknown:
        raise ValueError(f"label.entity_types has unknown types: {sorted(unknown)}")
    return wanted


def _clean_entities(doc: str, entities) -> list[dict]:
    keep = valid_types()
    return [e for e in align.ground(doc, entities) if e["type"] in keep]


def _cat(value: str | None) -> tuple[str, str | None]:
    """Map an out-of-schema category to OTHER, keeping the raw value for audit."""
    if value in VALID_CATS:
        return value, None
    return "OTHER", value


class Labeler:
    def __init__(self, manifest: Manifest | None = None):
        self.m = manifest or Manifest()
        self.log = get_logger("label")
        self.llm = LLMClient()
        self.tau = float(cfg("label.span_tau", 0.5))
        self.target = float(cfg("label.agreement_target", 0.85))
        self.floor = float(cfg("label.agreement_floor", 0.75))
        self.out = path_of("data") / "silver" / "silver.jsonl"

    def _vote(self, outs: list[str], text: str) -> tuple[list[dict], str | None]:
        """Majority vote over k adjudicator samples (Plan §5.2 third channel)."""
        from collections import Counter
        cats, support = [], Counter()
        norm: dict[tuple[str, str], str] = {}
        for o in outs:
            j = parse_json(o)
            if not j:
                continue
            if j.get("violation_category"):
                cats.append(_cat(j["violation_category"])[0])
            for e in _clean_entities(text, j.get("entities", [])):
                support[(e["type"], e["text"])] += 1
                if e.get("normalized"):
                    norm[(e["type"], e["text"])] = e["normalized"]
        cat = Counter(cats).most_common(1)[0][0] if cats else None
        ents = []
        for (t, x), c in support.items():
            if c >= max(1, len(outs) / 2):
                i = text.find(x)
                item = {"type": t, "text": x, "start": i, "end": i + len(x)}
                # Keep the model's normalised form, as the ground() path does
                # (D-62): dropping it makes the downstream node name fall back
                # to the raw span, so the same operator written two ways is two
                # graph nodes.
                if norm.get((t, x)):
                    item["normalized"] = norm[(t, x)]
                ents.append(item)
        return ents, cat

    def _one(self, doc: dict, text: str, lang: str) -> tuple[dict | None, str | None]:
        """Returns (record, failure_reason). A truncated answer is a different
        failure from an unparseable one: it says the document was too big for
        the output budget, which is a property of the protocol, not of the
        model's compliance (D-28/D-30)."""
        cfg_a = cfg("llm.channel_a")
        cfg_b = cfg("llm.channel_b")
        out_a = self.llm.chat_full(cfg_a["model"], prompts.render("alpha", lang, text),
                                   temperature=cfg_a["temperature"],
                                   max_tokens=cfg_a["max_tokens"])
        out_b = self.llm.chat_full(cfg_b["model"], prompts.render("beta", lang, text),
                                   temperature=cfg_b["temperature"],
                                   max_tokens=cfg_b["max_tokens"])
        raw_a, fin_a = out_a[0]
        raw_b, fin_b = out_b[0]
        ja, jb = parse_json(raw_a), parse_json(raw_b)
        if not ja or not jb:
            truncated = "length" in (fin_a, fin_b)
            return None, ("label_truncated_output" if truncated else "label_parse_failed")
        ea = _clean_entities(text, ja.get("entities", []))
        eb = _clean_entities(text, jb.get("entities", []))
        prec, rec, f1 = align.micro_f1(ea, eb, self.tau)
        anchor = anchors.label(text)
        cat_a, raw_a_cat = _cat(ja.get("violation_category"))
        cat_b, raw_b_cat = _cat(jb.get("violation_category"))
        invalid_cats = [x for x in (raw_a_cat, raw_b_cat) if x]

        adjudicated = False
        final_entities = []
        if f1 >= self.target and cat_a == cat_b:
            final_entities = [a for a, b, _ in align.match(ea, eb, self.tau)]
            final_cat = cat_a
        else:
            adjudicated = True
            cfg_adj = cfg("llm.adjudicator")
            k = int(cfg_adj.get("samples", 5))
            outs = self.llm.chat(cfg_adj["model"],
                                 prompts.render("adjudicate", lang, text, a=ja, b=jb),
                                 temperature=cfg_adj.get("temperature", 0.7),
                                 max_tokens=cfg_adj["max_tokens"], n=k)
            final_entities, final_cat = self._vote(outs, text)
            if not final_cat:
                return None, "label_no_consensus_category"

        anchor_pass = bool(anchor["category"] and final_cat == anchor["category"])
        # Plan §5.2: the main corpus is the high-confidence subset = dual-channel
        # agreement >= target AND the anchor agrees. The anchor is a Chinese
        # statute rule engine; it is undefined for the English corpus, so for
        # non-Chinese documents the high tier reduces to the agreement test
        # (DEVIATIONS.md D-15). The floor band (0.75 <= f1 < 0.85) is `medium`
        # and is used for sensitivity analyses only — never for the main
        # estimate.
        if f1 >= self.target and (anchor_pass or lang != "zh"):
            tier = "high"
        elif f1 >= self.floor:
            tier = "medium"
        else:
            tier = "low"
        conf = cfg(f"label.tier_confidence.{tier}", 0.6)
        for e in final_entities:
            e["confidence"] = conf
        return {
            "doc_id": doc["doc_id"], "source": doc["source"],
            "lang": lang, "text_sha": sha256_text(text),
            "tier": tier, "violation_category": final_cat,
            "anchor": anchor, "anchor_pass": anchor_pass,
            "entities": final_entities,
            "metrics": {"agreement_f1": round(f1, 4), "precision": round(prec, 4),
                        # Unrounded, so a later re-derivation of the tier cannot
                        # disagree with the tier written here (D-47: 21/987
                        # records sat exactly on the 0.75 floor after rounding).
                        "agreement_f1_exact": f1,
                        "recall": round(rec, 4), "tau": self.tau,
                        "adjudicated": adjudicated,
                        "finish_reason": {"a": fin_a, "b": fin_b},
                        "invalid_categories": invalid_cats},
            # Raw per-channel grounded annotations are kept so E1 can be
            # recomputed after decoding changes without re-querying the model.
            "channels": {"a": ea, "b": eb,
                         "cat_a": cat_a, "cat_b": cat_b},
            "meta": json.loads(doc.get("meta") or "{}"),
            "labeled_at": utc_iso(),
        }, None

    def _work(self, doc: dict) -> tuple[str, dict | None, str | None]:
        text = Path(doc["text_path"]).read_text(encoding="utf-8")
        rec, reason = self._one(doc, text, doc.get("lang") or "zh")
        return doc["doc_id"], rec, reason

    def run(self, limit: int | None = None) -> dict:
        if not self.llm.health():
            raise RuntimeError("LLM server not reachable at " + cfg("llm.base_url"))
        stats = {"seen": 0, "labeled": 0, "rejected": 0, "high": 0, "medium": 0,
                 "low": 0, "errors": 0}
        workers = max(1, int(cfg("label.workers", 4)))
        # Materialise first: iter_stage holds a read connection open, and the
        # workers write stage transitions concurrently (WAL keeps reads safe,
        # the list keeps this simple).
        docs = list(self.m.iter_stage("clean", limit=limit))
        stats["seen"] = len(docs)
        # Fail fast (DEVIATIONS.md D-37). Label one document synchronously
        # before the pool starts: a systematic error — a changed return
        # contract, a prompt that no longer renders — would otherwise be
        # applied to every document in the stage, each burning an attempt.
        # On 2026-11-04 a two-value unpack of a dict-valued return rejected 58
        # documents in four minutes before the log was read.
        if docs:
            probe = docs[0]
            try:
                got = self._one(probe,
                                Path(probe["text_path"]).read_text(encoding="utf-8"),
                                probe.get("lang") or "zh")
                if not (isinstance(got, tuple) and len(got) == 2):
                    raise TypeError(f"_one returned {type(got).__name__} of "
                                    f"len {len(got) if hasattr(got, '__len__') else '?'}")
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    f"label preflight failed on {probe['doc_id']}: "
                    f"{type(exc).__name__}: {exc}") from exc
        write_lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._work, d): d for d in docs}
            for fut in as_completed(futures):
                doc = futures[fut]
                doc_id = doc["doc_id"]
                try:
                    _, rec, reason = fut.result()
                    if not rec:
                        with write_lock:
                            stats["rejected"] += 1
                        self.m.bump_attempt(doc_id, reason or "label_parse_failed")
                        continue
                    with write_lock:
                        append_jsonl(self.out, rec)
                        stats["labeled"] += 1
                        stats[rec["tier"]] = stats.get(rec["tier"], 0) + 1
                    self.m.set_stage(doc_id, "labeled", note=f"tier={rec['tier']}")
                except Exception as exc:  # noqa: BLE001
                    self.log.exception("label failed %s", doc_id)
                    self.m.bump_attempt(doc_id, f"{type(exc).__name__}: {exc}")
                    with write_lock:
                        stats["errors"] += 1
        stats["at_utc"] = utc_iso()
        self.m.kv_set("stage_status:label", stats)
        return stats
