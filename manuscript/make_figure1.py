#!/usr/bin/env python3
"""Figure 1: the estimability ladder.

Each rung is a question the paper could ask; the middle column is the evidence that
would license an answer; the right column is the verdict. Drawn as a schematic, not a
data chart: every number printed here is also in D:\\Foods\\numbers.csv.

Run:  python make_figure1.py   ->  figure1_estimability.{png,pdf}
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OK, WARN, STOP = "#2F6F4F", "#8A6A1F", "#8C2F39"
INK, MUTE = "#1A1A1A", "#5A5A5A"

RUNGS = [
    # (question, evidence, verdict, colour)
    ("Composition within the\nsampling frame",
     "875 Chinese decisions; 604 categorised (69.0%);\nnegative control 14/50 at fine and at coarse level",
     "Conditional", WARN),
    ("Commodity dimension\n(which food?)",
     "18 categories, full text: 679/1128 documents;\n270 adjudicated hits: 0.9296 any-mention, 0.3852 subject\n(precision measured; recall not estimable — 3 attempts)",
     "Precision only", WARN),
    ("Violation category ×\nfood category",
     "15 food categories, 603/875 matched (68.9%);\ninstrument output, not a population estimate",
     "Conditional", WARN),
    ("Violation typology\n(human readers)",
     "3 readers × 80 documents: Fleiss' κ 0.0881;\nmin pairwise 0.1375 — abstention-dominated",
     "Not established", STOP),
    ("Behaviour–hazard\ntypology",
     "128 top-tier documents; dual-channel agreement 0.820;\n23 third-channel adjudications",
     "Exploratory", WARN),
    ("Case-chain /\nactor network",
     "9 of 128 documents name two parties; 9 edges =\nstructural maximum (saturation 1.0)",
     "Not estimable", STOP),
    ("Cross-genre\ncomparison",
     "US records carry no intentionality field:\n0 of 253 deliberate-fraud markers",
     "Not estimable", STOP),
    ("Temporal trend",
     "92 keyword queries; 16 exceed 200 rows (27,850);\nportal serves 200 rows per query — window, not trend",
     "Not estimable", STOP),
]

fig, ax = plt.subplots(figsize=(7.4, 6.3))
ax.set_xlim(0, 10)
ax.set_ylim(0, len(RUNGS) + 0.6)
ax.axis("off")

top = len(RUNGS)
for i, (q, ev, verdict, col) in enumerate(RUNGS):
    y = top - i - 0.5
    # rung bar
    ax.add_patch(FancyBboxPatch((0.15, y - 0.33), 9.7, 0.72,
                                boxstyle="round,pad=0.02,rounding_size=0.06",
                                linewidth=0.8, edgecolor="#DDDDDD", facecolor="#FCFCFC",
                                zorder=1))
    ax.add_patch(FancyBboxPatch((0.15, y - 0.33), 0.09, 0.72,
                                boxstyle="square,pad=0", linewidth=0,
                                facecolor=col, zorder=2))
    ax.text(0.42, y, q, ha="left", va="center", fontsize=9.2, color=INK,
            fontweight="semibold", linespacing=1.25)
    ax.text(3.30, y, ev, ha="left", va="center", fontsize=7.4, color=MUTE,
            linespacing=1.35, family="DejaVu Sans")
    ax.text(9.72, y, verdict, ha="right", va="center", fontsize=8.2, color=col,
            fontweight="bold")

ax.text(0.42, top + 0.18, "Question", fontsize=7.6, color=MUTE, fontweight="bold")
ax.text(3.30, top + 0.18, "Evidence that would license an answer", fontsize=7.6,
        color=MUTE, fontweight="bold")
ax.text(9.72, top + 0.18, "Verdict", fontsize=7.6, color=MUTE, fontweight="bold",
        ha="right")

fig.text(0.012, 0.015,
         "Frozen corpus sha256 a1deda2c… (n = 1128). Denominators as printed; every value "
         "traceable to numbers.csv.",
         fontsize=6.4, color=MUTE)

plt.subplots_adjust(left=0.01, right=0.99, top=0.94, bottom=0.06)
for ext in ("png", "pdf"):
    fig.savefig(f"figure1_estimability.{ext}", dpi=300 if ext == "png" else None,
                facecolor="white")
print("wrote figure1_estimability.png / .pdf")
