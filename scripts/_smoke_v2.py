#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test for protocol v2: the longest document must fit and parse.

Run on the pod:  cd /opt/foods && ./venv/bin/python scripts/_smoke_v2.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/opt/foods")
from foods_pipeline.common import cfg  # noqa: E402
from foods_pipeline.label import prompts  # noqa: E402
from foods_pipeline.label.llm import LLMClient, parse_json  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

m = Manifest()
rows = [r for r in m.iter_stage("clean") if r.get("source") == "cfws"]
rows.sort(key=lambda r: -(r.get("n_chars") or 0))
doc = rows[0]
text = Path(doc["text_path"]).read_text(encoding="utf-8")
print("doc", doc["doc_id"], "chars", len(text), "cap", prompts.doc_chars(),
      "truncated", len(text) > prompts.doc_chars())
llm = LLMClient()
out = {}
for ch, key in (("alpha", "llm.channel_a"), ("beta", "llm.channel_b")):
    c = cfg(key)
    p = prompts.render(ch, doc.get("lang") or "zh", text)
    try:
        raw = llm.chat(c["model"], p, temperature=c["temperature"],
                       max_tokens=c["max_tokens"])[0]
    except Exception as exc:  # noqa: BLE001
        out[ch] = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        continue
    j = parse_json(raw)
    out[ch] = {"prompt_chars": len(p), "raw_chars": len(raw),
               "parsed": bool(j),
               "entities": len((j or {}).get("entities", [])),
               "category": (j or {}).get("violation_category"),
               "head": raw[:120]}
print(json.dumps(out, ensure_ascii=False, indent=1))
