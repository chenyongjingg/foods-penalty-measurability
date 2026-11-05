import json
import re
import sqlite3
import sys

sys.path.insert(0, "/opt/foods")
from foods_pipeline.clean.normalize import extract_text  # noqa: E402

c = sqlite3.connect("/opt/foods/state/foods.sqlite")
c.row_factory = sqlite3.Row
for r in c.execute("select doc_id,meta,raw_path from docs where stage='filtered_out' limit 4"):
    m = json.loads(r["meta"])
    t, kind = extract_text(r["raw_path"], m)
    print("==", r["doc_id"], m.get("case_no"), kind, "len", len(t))
    for kw in ("伪造", "虚假", "检验", "检测报告", "认证", "溯源", "食品"):
        ps = [x.start() for x in re.finditer(kw, t)][:5]
        print("  ", kw, ps)
    print("  ", repr(t[:240]))
