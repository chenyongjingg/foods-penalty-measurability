"""Entity grounding and span alignment (Plan §5.2: span overlap tau = 0.5).

Definitions (fixed before seeing results; reported in the paper):
- An entity is grounded only if its `text` occurs verbatim in the document.
- Span overlap between two grounded mentions of the same type is
  IoU = |A n B| / |A u B|.
- Two mentions match if same type and IoU >= tau.
- Document-level agreement = micro F1 over matched mentions, i.e.
  2*|match| / (|A| + |B|).
Sensitivity at tau in {0.3, 0.5, 0.7} is computed by the evaluation step.
"""
from __future__ import annotations

import threading
from typing import Iterable

# Counting malformed model output instead of letting it crash or vanish
# (DEVIATIONS.md D-45). On 2026-11-04 the extract stage died 77 minutes into a
# run with `AttributeError: 'list' object has no attribute 'strip'`: one of the
# 5-sample votes returned {"text": ["…", "…"]}. `(e.get("text") or "").strip()`
# only guards against falsy values, not against a non-empty list. A non-string
# span cannot be grounded verbatim, so the correct handling is to drop that
# entity — but silently dropping it is what the record-keeping rule forbids,
# so every such drop is counted and reported.
MALFORMED: dict[str, int] = {"non_dict_entity": 0, "non_string_text": 0,
                             "non_string_type": 0}
_MALFORMED_LOCK = threading.Lock()


def malformed_stats() -> dict[str, int]:
    """Cumulative per-process counts of model output that could not be grounded."""
    with _MALFORMED_LOCK:
        return dict(MALFORMED)


def _bump(key: str) -> None:
    with _MALFORMED_LOCK:
        MALFORMED[key] = MALFORMED.get(key, 0) + 1


def ground(doc: str, entities: Iterable[dict]) -> list[dict]:
    out = []
    used_spans: set[tuple[int, int]] = set()
    for e in entities or []:
        if not isinstance(e, dict):
            _bump("non_dict_entity")
            continue
        etype = e.get("type")
        raw = e.get("text")
        if raw is not None and not isinstance(raw, str):
            _bump("non_string_text")
            continue
        text = (raw or "").strip()
        if not isinstance(etype, str):
            _bump("non_string_type")
            continue
        if not etype or not text:
            continue
        start = doc.find(text)
        if start < 0:
            continue  # hallucinated span: drop, never repair semantically
        end = start + len(text)
        if (start, end) in used_spans:
            continue
        used_spans.add((start, end))
        item = {"type": etype, "text": text, "start": start, "end": end}
        if e.get("normalized"):
            item["normalized"] = e["normalized"]
        out.append(item)
    return out


def iou(a: dict, b: dict) -> float:
    inter = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    union = max(a["end"], b["end"]) - min(a["start"], b["start"])
    return inter / union if union > 0 else 0.0


def match(a_list: list[dict], b_list: list[dict], tau: float) -> list[tuple[dict, dict, float]]:
    candidates = []
    for i, a in enumerate(a_list):
        for j, b in enumerate(b_list):
            if a["type"] != b["type"]:
                continue
            v = iou(a, b)
            if v >= tau:
                candidates.append((v, i, j))
    candidates.sort(reverse=True)
    used_a, used_b, pairs = set(), set(), []
    for v, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append((a_list[i], b_list[j], v))
    return pairs


def micro_f1(a_list: list[dict], b_list: list[dict], tau: float) -> tuple[float, float, float]:
    # Two empty annotations carry no evidence of agreement; scoring them 1.0
    # would inflate E1 on documents where both channels silently found nothing.
    if not a_list and not b_list:
        return 0.0, 0.0, 0.0
    pairs = match(a_list, b_list, tau)
    tp = len(pairs)
    prec = tp / len(a_list) if a_list else 0.0
    rec = tp / len(b_list) if b_list else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1
