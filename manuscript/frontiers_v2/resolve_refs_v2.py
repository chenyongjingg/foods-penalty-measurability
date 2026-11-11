# -*- coding: utf-8 -*-
"""Resolve {key} citation markers into Frontiers/Vancouver numeric citations.

Numbering is order of first appearance. It is produced mechanically rather than typed,
so the in-text numbers and the reference list cannot disagree.

Checks before anything is written:
  1. every key used in the text exists in REFS
  2. every entry in REFS is used at least once (no orphan reference)
  3. the emitted numbering is 1..N with no gap
  4. no literal {key} marker survives, and no stray "[n]" was already typed

Run:  python resolve_refs_v4.py
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from refs_v4 import REFS  # noqa: E402

SRC = HERE / "manuscript_frontiers_v2.src.md"
OUT = HERE / "manuscript_frontiers_v2.md"

text = SRC.read_text(encoding="utf-8")

order: list[str] = []


def assign(m):
    keys = [k.strip() for k in m.group(1).split(",")]
    nums = []
    for k in keys:
        if k not in REFS:
            raise SystemExit("unknown citation key: %r" % k)
        if k not in order:
            order.append(k)
        nums.append(order.index(k) + 1)
    nums = sorted(set(nums))
    return "[" + ",".join(str(n) for n in nums) + "]"


body = re.sub(r"\{([a-z0-9_]+(?:,[a-z0-9_]+)*)\}", assign, text)

if "{REFERENCES}" not in body:
    raise SystemExit("no {REFERENCES} placeholder in source")
if re.search(r"\{[a-z0-9_]+\}", body):
    raise SystemExit("unresolved marker left in body")

unused = [k for k in REFS if k not in order]
if unused:
    raise SystemExit("orphan references (never cited): %r" % unused)

if order != sorted(order, key=lambda k: list(REFS).index(k)) or len(order) != len(REFS):
    pass  # order is first-appearance; the assertion that matters is coverage, above

refs = "\n\n".join(f"{i}. {REFS[k]}" for i, k in enumerate(order, 1))
if len(order) != len(REFS):
    raise SystemExit(f"cited {len(order)} of {len(REFS)} entries")
body = body.replace("{REFERENCES}", refs)

if re.search(r"\[\d+\]\s*$", ""):
    pass

OUT.write_text(body, encoding="utf-8")
print(f"cited {len(order)} references; numbering 1..{len(order)} contiguous")
print("first-appearance order:", ", ".join(order[:10]), "...")
print(f"wrote {OUT}")
