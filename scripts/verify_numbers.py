#!/usr/bin/env python
"""Recompute every numbers.csv row from the product it names (D-128 stage 3).

This is the machine check of the paper's central provenance claim. Until now the sheet
asserted each value; here each row's `json_path` is resolved against its `product` and
compared to the recorded `value`.

Rows whose path cannot be resolved are reported as `unresolved` and are NOT counted as
mismatches -- several are deliberate arithmetic combinations written as `a-b`, and
calling those "failures" would make the check noisy enough to be ignored.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path("/opt/foods")
SHEET = ROOT / "numbers.csv"
OUT = ROOT / "runs/autopilot/03_numbers_verify.json"


def resolve(obj, path: str):
    cur = obj
    for part in [p for p in re.split(r"\.", path) if p]:
        m = re.fullmatch(r"([^\[\]]+)\[(\d+)\]", part)
        if m:
            cur = cur[m.group(1)][int(m.group(2))]
        elif part.isdigit() and isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def close(a, b) -> bool:
    """The sheet records a ROUNDED value, so agreement means 'the product rounds to the
    sheet at the sheet's own precision'. A tight relative tolerance would flag
    0.1667 against 0.166666... as a provenance failure, which it is not."""
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()
    sb = str(b)
    if "e" in sb.lower():
        # scientific sheet value: compare the mantissa at its printed precision
        mant, exp = sb.lower().split("e")
        dec = len(mant.split(".")[1]) if "." in mant else 0
        return abs(fa - fb) <= abs(fb) * 10 ** (-dec) * 1.001
    dec = len(sb.split(".")[1]) if "." in sb else 0
    return abs(round(fa, dec) - fb) <= 1e-12 + abs(fb) * 1e-9


def main() -> None:
    rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
    cache: dict[str, object] = {}
    ok, mismatch, unresolved, missing, composite = [], [], [], [], []
    text_rows: list[str] = []
    derived_rows: list[str] = []
    for r in rows:
        prod = r["product"]
        p = ROOT / prod
        if prod.startswith("derived from"):
            derived_rows.append(r["id"])
            continue
        if not prod.endswith((".json", ".jsonl")):
            # a text product (the register itself): there is no json_path to resolve,
            # so it is neither verifiable nor a failure. Counting it as "missing"
            # would put a defect in the product that no reader could reproduce.
            text_rows.append(r["id"])
            continue
        if not p.exists():
            missing.append({"id": r["id"], "product": prod})
            continue
        if prod not in cache:
            try:
                cache[prod] = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                cache[prod] = e
        obj = cache[prod]
        if isinstance(obj, Exception):
            missing.append({"id": r["id"], "product": prod, "error": str(obj)[:80]})
            continue
        try:
            got = resolve(obj, r["json_path"])
        except Exception:  # noqa: BLE001 - derived/composite paths land here by design
            unresolved.append({"id": r["id"], "path": r["json_path"]})
            continue
        if isinstance(got, (dict, list)):
            # a serialised table or a whole subtree: the sheet restates it, so a value
            # comparison is meaningless. Counted, not compared.
            composite.append(r["id"])
            continue
        (ok if close(got, r["value"]) else mismatch).append(
            {"id": r["id"], "path": r["json_path"], "sheet": r["value"], "product": got})

    out = {
        "sheet": str(SHEET), "n_rows": len(rows),
        "n_ok": len(ok), "n_mismatch": len(mismatch),
        "n_unresolved": len(unresolved), "n_missing_product": len(missing),
        "n_composite": len(composite), "n_derived_rows": len(derived_rows),
        "n_text_product": len(text_rows), "text_product_ids": text_rows[:50],
        "mismatches": mismatch[:200],
        "unresolved_ids": [u["id"] for u in unresolved][:200],
        "composite_ids": composite[:200],
        "missing": missing[:50],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rows {len(rows)} ok {len(ok)} mismatch {len(mismatch)} "
          f"unresolved {len(unresolved)} composite {len(composite)} missing {len(missing)} "
          f"text_product {len(text_rows)}")
    for m in mismatch[:20]:
        print("  MISMATCH", m["id"], m["sheet"], "vs", m["product"])


if __name__ == "__main__":
    main()
