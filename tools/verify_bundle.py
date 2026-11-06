#!/usr/bin/env python3
"""Verify the shipped supplementary bundle against its own manifest.

Three checks, no third-party packages:

1. every file listed in `supplementary/MANIFEST.md` exists and hashes to the value
   printed there, and no product file is present that the manifest does not list;
2. `numbers.csv` carries the number of data rows the manifest claims;
3. every product path named by a `numbers.csv` row exists inside the repository,
   except the classes the repository documents as not shipped (derived arithmetic
   rows and rows pointing at the register itself, which is a text product).

Usage:  python tools/verify_bundle.py
Exit code 0 if every check passes, 1 otherwise. Used by CI and by reviewers.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "supplementary"
MANIFEST = SUP / "MANIFEST.md"


def manifest_entries() -> list[tuple[str, str]]:
    text = MANIFEST.read_text(encoding="utf-8")
    block = text.split("```sh", 1)[1].split("```", 1)[0]
    rows = re.findall(r"^([0-9a-f]{64})  (\S+)$", block, re.M)
    if not rows:
        raise SystemExit("manifest: no sha256sum block found")
    return [(h, p) for h, p in rows]


def main() -> int:
    failures: list[str] = []

    entries = manifest_entries()
    listed = {p for _, p in entries}
    for h, rel in entries:
        p = SUP / rel
        if not p.exists():
            failures.append(f"missing file: {rel}")
            continue
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != h:
            failures.append(f"hash mismatch: {rel} manifest {h[:12]} file {got[:12]}")
    on_disk = {p.relative_to(SUP).as_posix() for p in SUP.rglob("*")
               if p.is_file() and p.name != "MANIFEST.md"}
    for extra in sorted(on_disk - listed):
        failures.append(f"unlisted file in bundle: {extra}")
    print(f"[bundle] {len(entries)} listed, {len(on_disk)} on disk")

    rows = list(csv.DictReader(open(ROOT / "numbers.csv", encoding="utf-8-sig")))
    claimed = re.search(r"\*\*(\d+) rows\*\*", MANIFEST.read_text(encoding="utf-8"))
    want = int(claimed.group(1)) if claimed else None
    if want is not None and len(rows) != want:
        failures.append(f"numbers.csv rows {len(rows)} != manifest {want}")
    print(f"[sheet ] {len(rows)} data rows (manifest says {want})")

    # Product paths, classified rather than counted: a row either resolves to a file in
    # this repository, points at a bundled product, is a derived arithmetic row, or is
    # the register itself (a text product with no JSON path to resolve). Anything else
    # is a real gap and fails the check -- a bare "572 present" would hide which.
    classes = {"in_repo": 0, "derived": 0, "text": 0, "missing": []}
    for r in rows:
        prod = r["product"]
        if prod.startswith("derived from"):
            classes["derived"] += 1
        elif not prod.endswith((".json", ".jsonl")):
            classes["text"] += 1
        elif (ROOT / prod).exists() or (SUP / prod).exists():
            classes["in_repo"] += 1
        else:
            classes["missing"].append(prod)
    print(f"[paths ] {classes['in_repo']} resolve in the repository, "
          f"{classes['derived']} derived arithmetic rows, {classes['text']} register rows, "
          f"{len(classes['missing'])} missing")
    for prod in sorted(set(classes["missing"])):
        failures.append(f"numbers.csv names a product that is not here: {prod}")

    if failures:
        print(f"FAILURES: {len(failures)}")
        for f in failures:
            print("  -", f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
