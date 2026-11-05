#!/usr/bin/env python3
"""Differential rescan between the pod tree and the local snapshot.

The hard criterion before deleting a machine: for every file under the root (the venv
excluded by construction), the path and the sha256 must agree on both sides -- zero
new, zero missing, zero changed. A file count alone does not establish that; a tarball
that unpacks to the right number of files can still hold the wrong bytes.

Usage:
  python diff_tree.py <pod_list.txt> <local_root> [--write local_list.txt]

Both inputs are `sha256sum` output with paths relative to the tree root.
"""
from __future__ import annotations

import sys
from pathlib import Path


def load(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        # "hash  ./path" or "hash *path"
        h, _, rest = line.partition(" ")
        rest = rest.strip()
        if rest.startswith("*"):
            rest = rest[1:]
        if rest.startswith("./"):
            rest = rest[2:]
        out[rest] = h
    return out


def main() -> int:
    pod = load(sys.argv[1])
    local_root = Path(sys.argv[2])
    if len(sys.argv) > 3 and sys.argv[3] == "--write":
        lines = []
        import hashlib
        for p in sorted(local_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(local_root).as_posix()
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            lines.append(f"{h}  {rel}")
        Path(sys.argv[4]).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} local hashes")
    local = load(sys.argv[-1])

    new = sorted(set(local) - set(pod))          # only on the pod, absent locally
    missing = sorted(set(pod) - set(local))      # only locally, absent on the pod
    changed = sorted(k for k in set(pod) & set(local) if pod[k] != local[k])
    print(f"pod {len(pod)} files, local {len(local)} files")
    print(f"missing_locally {len(new)}  extra_locally {len(missing)}  changed {len(changed)}")
    for label, rows in (("MISSING_LOCALLY", new[:20]), ("EXTRA_LOCALLY", missing[:20]),
                        ("CHANGED", changed[:20])):
        for r in rows:
            print(f"  {label}: {r}")
    ok = not new and not missing and not changed
    print("IDENTICAL" if ok else "DIFFERENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
