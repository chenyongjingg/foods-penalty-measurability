# -*- coding: utf-8 -*-
"""Move Tables 1-4 to the end of the manuscript, as the Frontiers template asks.

Template text (Frontiers_Template.docx, paragraph 23): "Tables should be
inserted at the end of the manuscript."

Nothing inside a table block is touched: each block (caption line + blank line +
header/separator/rows) is lifted whole and appended, in order, under a
`## Tables` heading placed after the References placeholder. Re-running is a
no-op because the body no longer contains a `**Table N.**` caption.

Prints, for every block moved, its byte length and sha256 before and after, so
the move can be checked as a move and not a rewrite.
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = Path(__file__).resolve().parent / "manuscript_frontiers_v2.src.md"
CAP = re.compile(r"^\*\*Table ([1-4])\.\*\*")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    lines = SRC.read_text(encoding="utf-8").split("\n")
    blocks: list[tuple[int, int, int, str]] = []      # (n, start, end, text)

    i = 0
    while i < len(lines):
        m = CAP.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        while i < len(lines) and not lines[i].startswith("|"):
            i += 1
        while i < len(lines) and lines[i].startswith("|"):
            i += 1
        blocks.append((int(m.group(1)), start, i, "\n".join(lines[start:i])))
        # swallow the single blank line that separated the block from what follows
        if i < len(lines) and lines[i].strip() == "":
            i += 1

    if not blocks:
        print("no table blocks in the body: already moved (no-op)")
        return 0

    keep = [ln for j, ln in enumerate(lines)
            if not any(s <= j < e for _, s, e, _ in blocks)]
    text = "\n".join(keep)
    text = re.sub(r"\n{3,}", "\n\n", text)

    out = [text.rstrip("\n"), "", "## Tables", ""]
    for n, _, _, blk in sorted(blocks):
        out += [blk, ""]
    new = "\n".join(out).rstrip("\n") + "\n"

    for n, _, _, blk in sorted(blocks):
        print(f"Table {n}: {len(blk):5d} B  sha {sha(blk)}  (moved whole)")
    # equal multiset of block bytes is the claim worth checking
    moved = [blk for _, _, _, blk in blocks]
    print(f"blocks moved: {len(moved)}; all still present verbatim in output: "
          f"{all(b in new for b in moved)}")

    SRC.write_text(new, encoding="utf-8")
    print(f"wrote {SRC} ({len(new.encode('utf-8'))} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
