"""Pilot: does the codebook-v2 prompt set raise dual-channel agreement?

Read-only with respect to the corpus: it samples documents that already have
per-channel annotations, re-labels them with config/prompts_v2/*.txt, and
compares the new agreement with the stored v1 agreement on the *same*
documents. Nothing is written to silver.jsonl or to the manifest.

Usage: python scripts/prompt_pilot.py [n] [--lang zh]
Decision rule (fixed before running): commit to a full re-label only if the
v2 mean agreement is >= the E1 floor (0.75) on the pilot.
"""
from __future__ import annotations

import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import cfg, path_of  # noqa: E402
from foods_pipeline.label import align  # noqa: E402
from foods_pipeline.label.llm import LLMClient, parse_json  # noqa: E402
from foods_pipeline.label.silver import _cat, _clean_entities  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

V2 = ROOT / "config" / "prompts_v2"
SEED = 20261104


def render_v2(channel: str, lang: str, text: str) -> str:
    tpl = (V2 / f"{channel}_{'zh' if lang == 'zh' else 'en'}.txt").read_text(encoding="utf-8")
    n = int(cfg("label.doc_text_chars", 6000))
    return tpl.replace("<<<DOC>>>", text[:n])


def one(llm: LLMClient, text: str, lang: str) -> tuple[list[dict], str | None]:
    ca, cb = cfg("llm.channel_a"), cfg("llm.channel_b")
    ja = parse_json(llm.chat(ca["model"], render_v2("alpha", lang, text),
                             temperature=ca["temperature"], max_tokens=ca["max_tokens"])[0]) or {}
    jb = parse_json(llm.chat(cb["model"], render_v2("beta", lang, text),
                             temperature=cb["temperature"], max_tokens=cb["max_tokens"])[0]) or {}
    ea = _clean_entities(text, ja.get("entities", []))
    eb = _clean_entities(text, jb.get("entities", []))
    cat_a, _ = _cat(ja.get("violation_category"))
    cat_b, _ = _cat(jb.get("violation_category"))
    return ea, eb, cat_a, cat_b


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 60
    lang = "zh"
    if "--lang" in sys.argv:
        lang = sys.argv[sys.argv.index("--lang") + 1]
    tau = float(cfg("label.span_tau", 0.5))
    target = float(cfg("label.agreement_target", 0.85))
    floor = float(cfg("label.agreement_floor", 0.75))
    m = Manifest()
    recs = []
    with open(path_of("data") / "silver" / "silver.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("lang") == lang and "channels" in r:
                    recs.append(r)
    random.Random(SEED).shuffle(recs)
    sample = recs[:n]
    llm = LLMClient()
    if not llm.health():
        raise SystemExit("LLM not reachable")
    jobs = []
    for r in sample:
        doc = m.get(r["doc_id"])
        if doc and doc.get("text_path"):
            jobs.append((r, Path(doc["text_path"]).read_text(encoding="utf-8")))
    workers = max(1, int(cfg("label.workers", 4)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outs = list(pool.map(lambda t: one(llm, t[1], lang), jobs))
    rows = []
    types = {}
    for (r, text), (ea, eb, cat_a, cat_b) in zip(jobs, outs):
        p, rc, f1 = align.micro_f1(ea, eb, tau)
        old = (r.get("metrics") or {}).get("agreement_f1")
        anchor = (r.get("anchor") or {}).get("category")
        final_cat = cat_a if cat_a == cat_b else (cat_b or cat_a)
        anchor_pass = bool(anchor and final_cat == anchor)
        tier = ("high" if f1 >= target and (anchor_pass or lang != "zh")
                else "medium" if f1 >= floor else "low")
        rows.append({"doc_id": r["doc_id"], "f1_v1": old, "f1_v2": round(f1, 4),
                     "tier_v1": r["tier"], "tier_v2": tier,
                     "cat_agree": bool(cat_a and cat_a == cat_b)})
        for lst, key in ((ea, "a"), (eb, "b")):
            for e in lst:
                d = types.setdefault(e["type"], {"a": 0, "b": 0})
                d[key] += 1
    v1 = [x["f1_v1"] for x in rows if x["f1_v1"] is not None]
    v2 = [x["f1_v2"] for x in rows]
    res = {"lang": lang, "n": len(rows), "seed": SEED,
           "mean_v1": round(sum(v1) / len(v1), 4) if v1 else None,
           "mean_v2": round(sum(v2) / len(v2), 4) if v2 else None,
           "improved": sum(1 for x in rows if x["f1_v1"] is not None and x["f1_v2"] > x["f1_v1"]),
           "worsened": sum(1 for x in rows if x["f1_v1"] is not None and x["f1_v2"] < x["f1_v1"]),
           "tiers_v2": {t: sum(1 for x in rows if x["tier_v2"] == t) for t in ("high", "medium", "low")},
           "cat_agree_rate": round(sum(1 for x in rows if x["cat_agree"]) / len(rows), 4),
           "entity_counts_v2": types,
           "floor_met": (sum(v2) / len(v2)) >= floor,
           "at_utc": __import__("foods_pipeline.common", fromlist=["utc_iso"]).utc_iso()}
    out = path_of("data") / "metrics" / "prompt_pilot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": res, "rows": rows}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
