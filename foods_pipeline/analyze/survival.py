"""Cox survival of node recurrence (Plan §6.1 E3).

Unit = entity node. Time origin = first observed penalty case involving the
node. Event = the node reappears in a later case (recurrence). Nodes observed
once are right-censored at the dataset's last observation date. Covariates:
node type (intermediary vs terminal), degree. Bootstrap CIs (200 reps, fixed
seed). If events < analysis.survival_min_events the estimate is reported as
INCONCLUSIVE rather than fitted (Plan §6.2 E3).
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np

from ..common import as_date, cfg, get_logger, path_of, utc_iso, write_json
from ..manifest import Manifest


def _d(s: str) -> date | None:
    return as_date(s)


def build_table() -> list[dict]:
    # The silver dataset carries grounded entity names; dates come from the
    # manifest metadata written at collection time.
    from .network import load_edges, normalize_name
    docs, _ = load_edges()
    m = Manifest()
    node_dates: dict[str, list[date]] = {}
    node_type: dict[str, str] = {}
    for d in docs:
        rec = m.get(d["doc_id"])
        meta = json.loads(rec.get("meta") or "{}") if rec else {}
        dt = _d(meta.get("date") or rec.get("published") or "") if rec else None
        if not dt:
            continue
        seen = set()
        for e in d["entities"]:
            if e["entity_type"] not in ("SERVICE_PROVIDER", "END_USER"):
                continue
            name = normalize_name(e["normalized"])
            if not name or name in seen:
                continue
            seen.add(name)
            node_dates.setdefault(name, []).append(dt)
            node_type.setdefault(name, e["entity_type"])
    return [{"node": k, "dates": sorted(v), "ntype": node_type[k]} for k, v in node_dates.items()]


def run() -> dict:
    import pandas as pd
    from lifelines import CoxPHFitter

    rows = build_table()
    rows = [r for r in rows if len(r["dates"]) >= 1]
    outdir = path_of("data") / "analysis"
    res = {"n_nodes": len(rows), "at_utc": utc_iso()}
    if not rows:
        res["status"] = "no_data"
        write_json(outdir / "survival.json", res)
        return res
    last = max(r["dates"][-1] for r in rows)
    data = []
    for r in rows:
        t0 = r["dates"][0]
        if len(r["dates"]) >= 2:
            dur = (r["dates"][1] - t0).days
            event = 1
        else:
            dur = (last - t0).days
            event = 0
        data.append({"duration": max(1, dur), "event": event,
                     "intermediary": 1 if r["ntype"] == "SERVICE_PROVIDER" else 0})
    df = pd.DataFrame(data)
    n_events = int(df["event"].sum())
    res["n_events"] = n_events
    if n_events < int(cfg("analysis.survival_min_events", 20)):
        res.update({"status": "inconclusive",
                    "note": f"events={n_events} < min={cfg('analysis.survival_min_events')}; "
                            "reported as inconclusive per Plan §6.2 E3"})
        write_json(outdir / "survival.json", res)
        return res
    try:
        cph = CoxPHFitter()
        cph.fit(df, duration_col="duration", event_col="event")
        summary = cph.summary.reset_index().to_dict(orient="records")
        # bootstrap CI over rows
        rng = np.random.default_rng(int(cfg("analysis.seed", 20261104)))
        boots = []
        for _ in range(int(cfg("analysis.bootstrap", 200))):
            idx = rng.integers(0, len(df), len(df))
            try:
                c = CoxPHFitter().fit(df.iloc[idx], duration_col="duration", event_col="event")
                boots.append(float(c.params_.get("intermediary", np.nan)))
            except Exception:
                continue
        coef = float(cph.params_.get("intermediary", np.nan))
        lo, hi = (float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))) \
            if boots else (None, None)
        res.update({"status": "ok", "coef_intermediary": coef,
                    "hr_intermediary": float(np.exp(coef)) if coef == coef else None,
                    "p_intermediary": float(cph.summary.loc["intermediary", "p"]) if "intermediary" in cph.summary.index else None,
                    "boot_ci95": [lo, hi], "n_boot": len(boots),
                    "summary": summary})
    except Exception as exc:  # noqa: BLE001
        res.update({"status": "fit_failed", "error": str(exc)[:300]})
    write_json(outdir / "survival.json", res)
    get_logger("analyze.survival").info("survival: %s", res.get("status"))
    return res
