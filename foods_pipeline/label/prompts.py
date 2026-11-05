"""Prompt rendering for the two independent channels and the adjudicator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..common import REPO_ROOT, cfg

# Files that define the labelling protocol. Their hashes go into e1.json so a
# reported agreement figure can be tied to the exact prompt text that produced
# it (DEVIATIONS.md D-14 versioning).
_PROMPT_FILES = ("alpha_zh.txt", "alpha_en.txt", "beta_zh.txt", "beta_en.txt",
                 "adjudicate.txt")


def _load(name: str) -> str:
    p = REPO_ROOT / "config" / "prompts" / name
    return p.read_text(encoding="utf-8")


def doc_chars() -> int:
    return int(cfg("label.doc_text_chars", 20000))


def version() -> dict:
    """Content hashes of the prompt templates, for the E1 provenance block."""
    out = {}
    for name in _PROMPT_FILES:
        try:
            out[name] = hashlib.sha256(_load(name).encode("utf-8")).hexdigest()[:12]
        except FileNotFoundError:
            out[name] = None
    return out


def render(channel: str, lang: str, doc: str, *, a: dict | None = None,
           b: dict | None = None) -> str:
    """channel in {alpha, beta, adjudicate}.

    The document is cut at `label.doc_text_chars` in every channel, including
    the adjudicator: a third channel that saw more text than A and B would make
    the adjudicated labels incomparable with the agreed ones (D-30).
    """
    n = doc_chars()
    if channel == "adjudicate":
        tpl = _load("adjudicate.txt")
        # Cap the two candidate JSON blobs as well: with a full-length document
        # a verbose candidate list can push the request past the context window.
        # 1,200 chars each keeps a 20k-char document plus both candidates plus
        # the answer inside the 23,040-token server limit.
        a_s = json.dumps(a or {}, ensure_ascii=False)[:1200]
        b_s = json.dumps(b or {}, ensure_ascii=False)[:1200]
        return (tpl.replace("<<<DOC>>>", doc[:n])
                   .replace("<<<A>>>", a_s)
                   .replace("<<<B>>>", b_s))
    suffix = "zh" if lang == "zh" else "en"
    tpl = _load(f"{channel}_{suffix}.txt")
    return tpl.replace("<<<DOC>>>", doc[:n])
