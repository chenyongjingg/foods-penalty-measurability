"""E8 -- China / US violation-type composition table (Plan v7, E8).

Two different instruments are compared, and the table says so:

* China: penalty decisions, category read by the deterministic v2 statute
  engine (`scripts/e6_descriptive.py`), restricted to the five fraud
  categories plus OTHER -- the descriptive-only extensions are not part of the
  comparison.
* US: openFDA food enforcement recalls, category read from `reason_for_recall`
  by a fixed keyword map (`config/e8_us_map.yaml`).

The two are not the same construct: an FDA recall reason states why a product
was removed from the market (most often a labelling defect or a pathogen), not
what a tribunal found. The script therefore computes the composition table and
an estimability verdict side by side: if only a small share of US records
describe deliberate falsification, E8 is reported as a **descriptive
composition of two different instrument types**, and no fraud-rate comparison
is claimed.

Usage:
    ./venv/bin/python scripts/e8_us_cn.py
Exit 0 = product written.
"""
from __future__ import annotations

import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from foods_pipeline.common import cfg, load_yaml, write_json, utc_iso  # noqa: E402

DATA = ROOT / "data"
E6 = DATA / "analysis" / "e6_descriptive.json"
OUT = DATA / "analysis" / "e8_us_cn.json"
REPORT = DATA / "reports" / "e8_table.md"
FDA_GLOB = "data/raw/openfda/*/*.json"

FRAUD_CATS = ["FORGED_INSPECTION_REPORT", "TAMPERED_TRACEABILITY", "FAKE_CERTIFICATION",
              "FALSE_LABELING", "UNLICENSED_OPERATION", "OTHER"]


def _load_map() -> dict:
    return load_yaml("config/e8_us_map.yaml")


def _us_category(reason: str, mp: dict) -> tuple[str, list[str]]:
    r = (reason or "").lower()
    hits = []
    for cat, pats in mp["rules"].items():
        for p in pats:
            if re.search(p, r):
                hits.append(cat)
                break
    fraud = [h for h in hits if h != "OTHER"]
    if len(fraud) == 1:
        return fraud[0], hits
    if len(fraud) > 1:
        return "OTHER", hits          # two claims in one reason: not separable
    return "OTHER", hits


def main() -> int:
    mp = _load_map()
    e6 = json.loads(E6.read_text(encoding="utf-8"))
    cn = {k: v for k, v in e6["category_distribution"].items() if k in FRAUD_CATS}
    cn_n = sum(cn.values())
    cn_total = int(e6["n_docs"])
    cn_unresolved = int(e6["category_distribution"].get("UNRESOLVED", 0))
    if cn_n == 0:
        print("E6 distribution has no category inside the fraud framework", file=sys.stderr)
        return 1

    files = sorted(glob.glob(str(ROOT / FDA_GLOB)))
    us = collections.Counter()
    deliberate = 0
    samples = collections.defaultdict(list)
    for f in files:
        rec = json.loads(Path(f).read_text(encoding="utf-8"))
        reason = rec.get("reason_for_recall") or ""
        cat, _ = _us_category(reason, mp)
        us[cat] += 1
        if any(re.search(p, reason.lower()) for p in mp["deliberate_falsification"]):
            deliberate += 1
        if len(samples[cat]) < 3:
            samples[cat].append({"recall_number": rec.get("recall_number"),
                                 "reason": reason[:200]})
    us_n = sum(us.values())

    rows = []
    for c in FRAUD_CATS:
        a, b = cn.get(c, 0), us.get(c, 0)
        if a + b > 0:  # a category absent on both sides is a zero column
            rows.append((c, [a, b]))
    table_rows = [c for c, _ in rows]
    table = [row for _, row in rows]

    test = {}
    try:
        from scipy import stats
        chi2, p, dof, exp = stats.chi2_contingency(table)
        min_exp = float(exp.min())
        test = {"chi2": round(float(chi2), 4), "p": float(p), "dof": int(dof),
                "min_expected": round(min_exp, 3)}
        k = min(len(table), len(table[0]))
        n = sum(sum(r) for r in table)
        cramers_v = (chi2 / (n * (k - 1))) ** 0.5 if n and k > 1 else None
        test["cramers_v"] = round(float(cramers_v), 4) if cramers_v is not None else None
        test["n"] = n
        if min_exp < float(cfg("analysis.chi2_min_expected", 5)):
            # Collapse to FALSE_LABELING vs everything else, the only 2x2 that the
            # data can support, and report Fisher as the test of record.
            if "FALSE_LABELING" not in table_rows:
                raise ValueError(
                    "FALSE_LABELING absent from the collapsed table; "
                    "the pre-registered collapse is unavailable")
            i = table_rows.index("FALSE_LABELING")
            a_cn = table[i][0]
            b_us = table[i][1]
            rest_cn = sum(r[0] for j, r in enumerate(table) if j != i)
            rest_us = sum(r[1] for j, r in enumerate(table) if j != i)
            odds, fp = stats.fisher_exact([[a_cn, rest_cn], [b_us, rest_us]])
            test.update({"primary_test": "fisher_collapsed",
                         "collapsed_fisher": {"odds_ratio": float(odds), "p": float(fp),
                                              "table_cn_label_vs_rest": [a_cn, rest_cn],
                                              "table_us_label_vs_rest": [b_us, rest_us]},
                         "chi2_unreliable": {"min_expected": round(min_exp, 3)}})
        else:
            test["primary_test"] = "chi2_full"
    except Exception as exc:  # noqa: BLE001
        test = {"primary_test": "not_run", "error": str(exc)[:200]}

    us_deliberate_share = round(deliberate / us_n, 4) if us_n else None
    estimable = us_deliberate_share is not None and us_deliberate_share >= 0.10

    out = {
        "at_utc": utc_iso(),
        "cn": {"n": cn_n, "frame_total": cn_total, "unresolved": cn_unresolved,
               "source": "E6 deterministic v2, fraud framework only",
               "silver_sha256": e6["silver"]["sha256"], "counts": cn},
        "us": {"n": us_n, "source": "openFDA food enforcement, reason_for_recall keyword map",
               "files": len(files), "counts": dict(sorted(us.items())),
               "deliberate_falsification_n": deliberate,
               "deliberate_falsification_share": us_deliberate_share,
               "map_version": mp.get("version")},
        "table_rows": table_rows,
        "table": table,
        "test": test,
        "estimability": "estimable" if estimable else "not_estimable_instrument_mismatch",
        "estimability_note": (
            "An FDA recall reason is a market-withdrawal ground, not a finding of "
            "deliberate falsification; 'misbranded' is a regulatory label defect. "
            "The comparison is therefore of two document genres' violation "
            "compositions, and a difference in composition is not evidence of a "
            "difference in fraud prevalence."),
        "samples": dict(samples),
    }
    write_json(OUT, out)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(_markdown(out), encoding="utf-8")
    print(json.dumps({"e8": "ok", "cn_n": cn_n, "us_n": us_n,
                      "estimability": out["estimability"],
                      "test": test.get("primary_test")}, ensure_ascii=False))
    return 0


def _markdown(o: dict) -> str:
    L = ["# E8 中美违规类型构成对照（Results 3）", "",
         f"- 生成时刻：{o['at_utc']}",
         f"- 中国：{o['cn']['n']} 篇（确定性规则，仅造假框架内类别）",
         f"- 美国：{o['us']['n']} 条（openFDA 召回理由，关键词映射）",
         f"- 可估性：**{o['estimability']}**；美国侧明示造假线索占比 "
         f"{o['us']['deliberate_falsification_share']}", "",
         "| 类别 | 中国 | 美国 |", "|---|---:|---:|"]
    for c, (a, b) in zip(o["table_rows"], o["table"]):
        L.append(f"| {c} | {a} | {b} |")
    t = o["test"]
    L += ["", f"- 检验：{t.get('primary_test')}；Cramér's V = {t.get('cramers_v')}；"
              f"p = {t.get('p')}", "", "> " + o["estimability_note"]]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
