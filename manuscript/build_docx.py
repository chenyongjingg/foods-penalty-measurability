#!/usr/bin/env python3
"""Render the submission docx from manuscript_submission.md.

The markdown is now the source of truth: it is written by hand, its numbers are
checked against numbers.csv by _tools/check_numbers.py, and this script only
renders it. (The earlier v1 -> submission transformation is retired: it would
overwrite the manuscript it is supposed to publish.)

Refuses to build if the Figure 1 image or the manuscript is missing.

Output: manuscript_submission.docx
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "manuscript_submission.md"
OUT = HERE / "manuscript_submission.docx"
FIG = HERE / "figure1_estimability.png"

if not SRC.exists():
    sys.exit(f"missing source: {SRC}")
if not FIG.exists():
    sys.exit(f"missing figure: {FIG} — run make_figure1.py first")
if "figure1_estimability.png" not in SRC.read_text(encoding="utf-8"):
    sys.exit("manuscript no longer references Figure 1 — refusing to build")

cmd = [
    "pandoc", str(SRC), "-o", str(OUT),
    "--from", "markdown+pipe_tables+tex_math_dollars",
    # pandoc uses the platform path separator (";" on Windows), so a comma-joined
    # path is a single nonexistent directory and the figure is silently dropped.
    "--resource-path", str(HERE),
    "--highlight-style", "tango",
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    sys.exit(f"pandoc failed: {r.stderr}")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
