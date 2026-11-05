"""H2 anchoring on the D4 governance-event timeline (Plan Table 2, D4).

H2 states that after a governance shock the ecosystem shows suppression ->
displacement -> regeneration.  Hawkes (analyze/hawkes.py) only models the
rhythm of penalty events; it cannot tell whether that rhythm changed *because
of* a governance action.  This module supplies the anchoring half: given
dated governance events (D4), compare the rate of corpus penalty events in a
window before and after each event.

The test is deliberately conservative:
  * only food-specific governance events are used;
  * both windows must contain at least `min_window_events` corpus events,
    otherwise the contrast is reported as `insufficient`;
  * the rate comparison is an exact binomial test under equal exposure
    (scipy.stats.binomtest), not a normal approximation;
  * a rate ratio is reported with its 95% exact CI, so a point estimate
    cannot be read as a finding on its own.

What this cannot do is establish the three-phase pattern itself: that needs
post-shock observation long enough to see regeneration, which the corpus may
not cover.  The output says so explicitly in `interpretation`.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from scipy import stats

from ..common import as_date, cfg, get_logger, path_of, read_json, utc_iso, write_json
from ..manifest import Manifest


def _d(s: str | None) -> date | None:
    return as_date(s)


def corpus_event_dates() -> list[date]:
    """CN main-corpus penalty dates only (D-16: D3a is comparison-only)."""
    m = Manifest()
    out: list[date] = []
    for doc in m.iter_stage("extracted"):
        if doc.get("source") not in ("cfws", "municipal"):
            continue
        meta = {}
        try:
            meta = json.loads(doc.get("meta") or "{}")
        except Exception:
            meta = {}
        d = _d(meta.get("date")) or _d(doc.get("published"))
        if d:
            out.append(d)
    return sorted(out)


def governance_events(food_only: bool = True) -> list[dict]:
    """Only events with an exact date and a decision-bearing type enter H2.

    `announcement`/`other` are kept in the D4 file but carry no regime signal,
    and including them would let a busy news month masquerade as a shock.
    """
    path = path_of("data") / "events" / "gov_events.jsonl"
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if not _d(r.get("date")):
                continue
            if food_only and not r.get("food_specific"):
                continue
            if r.get("event_type") not in {"crackdown", "policy", "case_series",
                                           "judicial", "inspection"}:
                continue
            rows.append(r)
    return sorted(rows, key=lambda r: r["date"])


_CJK_PUNCT = "“”\"'「」《》〈〉（）()【】[]，,。.、：:；;！!？?——-…·"


def _norm_title(t: str) -> str:
    t = "".join(ch for ch in str(t) if ch not in _CJK_PUNCT and not ch.isspace())
    for prefix in ("最高人民法院最高人民检察院", "最高人民法院", "最高人民检察院",
                   "两高", "市场监管总局", "最高检", "最高法"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t


def _similar(a: str, b: str) -> bool:
    """Same release reported by two sites, or re-reported a day later."""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(1, len(sa | sb)) >= 0.75


def canonical_events(rows: list[dict], span_days: int = 7) -> list[dict]:
    """Collapse the same governance action reported by several outlets.

    Counting court.gov.cn and spp.gov.cn copies of one joint release as two
    shocks would inflate the number of "events" and make the H2 calendar look
    denser than the governance record.  Events merge when their normalised
    titles are similar and their dates are within `span_days`; the earliest
    date is kept (the announcement, not the reprint).
    """
    rows = sorted(rows, key=lambda r: r["date"])
    out: list[dict] = []
    for r in rows:
        nt = _norm_title(r["title"])
        d = _d(r["date"])
        for c in out:
            if abs((d - _d(c["date"])).days) <= span_days and _similar(nt, c["_nt"]):
                c["merged_urls"].append(r["url"])
                c["merged_sites"].add(r["site"] or "")
                c["food_specific"] = c["food_specific"] or bool(r.get("food_specific"))
                break
        else:
            out.append({"event_id": r["event_id"], "date": r["date"],
                        "title": r["title"], "type": r["event_type"],
                        "food_specific": bool(r.get("food_specific")),
                        "url": r["url"], "merged_urls": [], "merged_sites": {r["site"] or ""},
                        "_nt": nt})
    for c in out:
        c["merged_sites"] = sorted(c.pop("merged_sites"))
        c.pop("_nt", None)
        c["n_sources"] = 1 + len(c["merged_urls"])
    return out


def _exact_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else float(stats.beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def run() -> dict:
    window = int(cfg("analysis.shock_window_days", 90))
    min_n = int(cfg("analysis.shock_min_window_events", 5))
    outdir = path_of("data") / "analysis"
    raw_ev = governance_events(food_only=True)
    ev = canonical_events(raw_ev)
    ce = corpus_event_dates()
    res = {"n_gov_events_raw": len(raw_ev), "n_gov_events": len(ev),
           "n_corpus_events": len(ce),
           "window_days": window, "at_utc": utc_iso()}
    if not ev:
        res.update({"status": "no_events",
                    "note": "D4 collector has not produced dated food-specific events"})
        write_json(outdir / "shocks.json", res)
        return res
    if not ce:
        res.update({"status": "no_corpus_events",
                    "note": "no extracted documents carry a usable date"})
        write_json(outdir / "shocks.json", res)
        return res

    tests = []
    for e in ev:
        d = _d(e["date"])
        before = [x for x in ce if d - timedelta(days=window) <= x < d]
        after = [x for x in ce if d < x <= d + timedelta(days=window)]
        nb, na = len(before), len(after)
        rec = {"event_id": e["event_id"], "date": e["date"], "title": e["title"][:80],
               "type": e["type"], "sites": e.get("merged_sites"),
               "n_before": nb, "n_after": na}
        if nb < min_n or na < min_n:
            rec["status"] = "insufficient"
        else:
            bt = stats.binomtest(na, nb + na, 0.5)
            lo, hi = _exact_ci(na, nb + na)
            ratio = na / nb
            rec.update({"status": "ok", "rate_ratio": round(ratio, 4),
                        "p_value": float(bt.pvalue),
                        "ratio_ci95": [round(lo / (1 - lo), 4),
                                       round(hi / (1 - hi), 4) if hi < 1 else None],
                        "direction": ("suppressed" if ratio < 1 and bt.pvalue < 0.05
                                      else "regenerated" if ratio > 1 and bt.pvalue < 0.05
                                      else "no_detectable_change")})
        tests.append(rec)

    ok = [t for t in tests if t["status"] == "ok"]
    # Monthly governance-event calendar: the descriptive half of D4, usable in
    # the paper even when the corpus is too small for a per-shock test.
    series: dict[str, int] = {}
    for e in ev:
        m = e["date"][:7]
        series[m] = series.get(m, 0) + 1
    corpus_series: dict[str, int] = {}
    for d in ce:
        m = d.isoformat()[:7]
        corpus_series[m] = corpus_series.get(m, 0) + 1
    res.update({"status": "ok" if ok else "insufficient",
                "n_tested": len(tests), "n_evaluable": len(ok),
                "monthly_series": dict(sorted(series.items())),
                "corpus_monthly": dict(sorted(corpus_series.items())),
                "tests": tests,
                "interpretation": (
                    "Per-shock before/after contrasts only. A suppression or "
                    "regeneration verdict at p<0.05 is a rate change, not proof "
                    "of the three-phase H2 trajectory; the regeneration phase "
                    "requires events after the window to be observable."),
                "caveat": f"windows of {window} days, min {min_n} events per side",
                "design_caveat": (
                    "Corpus exposure is not uniform: the CFWS portal returns at "
                    "most 200 rows per query, so the newest documents are "
                    "over-represented. A before/after rate change can therefore "
                    "reflect collection coverage, not governance. Read the "
                    "contrast together with corpus_monthly. Windows of nearby "
                    "events overlap and are not independent tests.")})
    if not ok:
        res["note"] = ("no shock had enough corpus events on both sides; "
                       "H2 remains untestable on the current corpus, and the "
                       "gap is a sample-size fact, not a null result")
    write_json(outdir / "shocks.json", res)
    get_logger("analyze.shocks").info("shocks: %s (%d/%d evaluable)",
                                      res["status"], len(ok), len(tests))
    return res
