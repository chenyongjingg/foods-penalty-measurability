"""Audit anchor-channel coverage on Chinese documents (diagnostics only)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/opt/foods")
from foods_pipeline.label import anchors  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

m = Manifest()
n = uniq = cat = multi = zero = 0
for doc in m.iter_stage("labeled", source="cfws"):
    n += 1
    text = Path(doc["text_path"]).read_text(encoding="utf-8")
    r = anchors.label(text)
    st = r["statutes"]
    if st:
        uniq += 1
        if r["category"]:
            cat += 1
        if r["ambiguous"]:
            multi += 1
    else:
        zero += 1
    if n <= 3:
        print(doc["doc_id"], "statutes", st[:5], "cat", r["category"], "amb", r["ambiguous"])
print(f"docs={n} with_statute={uniq} single_category={cat} ambiguous={multi} no_statute={zero}")
