"""Compare channel A/B on openFDA (English) documents only (diagnostics)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/opt/foods")
from foods_pipeline.common import cfg  # noqa: E402
from foods_pipeline.label import align, prompts  # noqa: E402
from foods_pipeline.label.llm import LLMClient, parse_json  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
m = Manifest()
docs = [d for d in m.iter_stage("labeled", source="openfda")][:n]
llm = LLMClient()
for doc in docs:
    text = Path(doc["text_path"]).read_text(encoding="utf-8")
    print("DOC", doc["doc_id"], "chars", len(text))
    sets = {}
    for ch, key in (("alpha", "a"), ("beta", "b")):
        c = cfg(f"llm.channel_{key}")
        out = llm.chat(c["model"], prompts.render(ch, doc.get("lang") or "en", text),
                       temperature=c["temperature"], max_tokens=c["max_tokens"])[0]
        print(f"  RAW {ch}: {out[:400]}")
        j = parse_json(out) or {}
        ents = align.ground(text, j.get("entities", []))
        sets[key] = ents
        print(f"  {ch} cat={j.get('violation_category')} n={len(ents)}")
        for e in ents:
            print(f"    {e['type']:<18} {e['text'][:60]}")
    p, r, f = align.micro_f1(sets["a"], sets["b"], 0.5)
    print(f"  micro P={p:.2f} R={r:.2f} F1={f:.2f}")
