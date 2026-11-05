"""Daily report: counts, gates, source health, disk, actions. Optional webhook."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..common import (cfg, disk_free_pct, iter_jsonl, path_of, read_json, utc_iso,
                      write_json)
from ..manifest import Manifest


def _fmt_counts(c: dict) -> list[str]:
    lines = ["| source | raw | clean | labeled | extracted | filtered | dup | failed |",
             "|---|---|---|---|---|---|---|---|"]
    for src, d in sorted(c.items()):
        lines.append(f"| {src} | {d.get('raw',0)} | {d.get('clean',0)} | {d.get('labeled',0)} | "
                     f"{d.get('extracted',0)} | {d.get('filtered_out',0)} | "
                     f"{d.get('duplicate',0)} | {d.get('failed',0)} |")
    return lines


def build() -> tuple[str, Path]:
    m = Manifest()
    now = utc_iso()
    c = m.counts()
    e1 = read_json(path_of("data") / "metrics" / "e1.json", {}) or {}
    gates = read_json(path_of("data") / "analysis" / "gates.json", {}) or {}
    lines = [f"# Foods pipeline daily report — {now}", ""]
    lines += ["## 1. 文档状态机", ""] + _fmt_counts(c) + [""]

    lines += ["## 2. E1 银标准", ""]
    if e1:
        lines += [f"- status: **{e1.get('status')}**",
                  f"- docs: {e1.get('n')}, mean agreement: {e1.get('mean_agreement')}",
                  f"- anchor F1: {(e1.get('anchor_f1') or {}).get('f1')} "
                  f"(n={(e1.get('anchor_f1') or {}).get('n')})",
                  f"- tiers: {e1.get('tier_counts')}",
                  f"- agreement scored on {e1.get('n_scored_agreement')} docs; "
                  f"{e1.get('n_zero_entities')} excluded (no entity from either channel)"]
        for lang, v in sorted((e1.get("by_lang") or {}).items()):
            lines.append(f"- {lang}: agreement {v.get('mean_agreement')} (n={v.get('n')}, "
                         f"tiers {v.get('tiers')})")
        if e1.get("tau_sensitivity"):
            lines.append("- tau sensitivity: " + json.dumps(e1["tau_sensitivity"], ensure_ascii=False))
        lad = e1.get("ladder") or {}
        if lad.get("triggered"):
            lines.append(f"- **P062 类型收缩**: stable={lad.get('stable_types')} "
                         f"shrunk agreement={lad.get('agreement_shrunk')}")
    else:
        lines += ["- not evaluated yet"]
    lines += [""]

    lines += ["## 3. 实验闸门（E1–E5）", ""]
    for k, v in (gates.get("gates") or {}).items():
        lines += [f"- **{k}**: {v.get('status')}  ",
                  f"  {json.dumps({x: y for x, y in v.items() if x != 'status'}, ensure_ascii=False)}"]
    if gates.get("actions"):
        lines += ["", "**自动降级动作**："] + [f"- {a}" for a in gates["actions"]]
    lines += [""]

    lines += ["## 4. 数据源健康", ""]
    for k in ("cfws", "openfda", "rasff", "municipal"):
        st = m.kv_get(f"source_status:{k}")
        if st:
            brief = {x: st.get(x) for x in ("ok", "new", "listed", "status", "note")
                     if x in st}
            extra = st.get("status") if isinstance(st.get("status"), str) else ""
            lines.append(f"- **{k}**: {json.dumps(brief, ensure_ascii=False)[:400]} {extra}")
    ev = m.kv_get("gov_events")
    if ev:
        lines.append(f"- **D4 治理事件**: {json.dumps(ev.get('summary'), ensure_ascii=False)[:500]}")
    lines += ["", f"- disk free: **{disk_free_pct():.1f}%**", ""]

    lines += ["## 5. 本次运行", ""]
    ladder = m.kv_get("actions:ladder") or []
    lines.append(f"- ladder actions: {json.dumps(ladder, ensure_ascii=False)}")
    lines += ["", "---", "",
              "*口径提醒：全文只写 silver standard；主分析只用 high 层，"
              "medium 仅见于 D-23 敏感性表；负结果与不显著照实报告。*"]
    text = "\n".join(lines)
    outdir = path_of("reports") / "daily"
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f"report_{now[:10]}.md"
    p.write_text(text, encoding="utf-8")
    write_json(outdir / "latest.json", {"at_utc": now, "path": str(p)})
    return text, p


def send_webhook(text: str) -> None:
    url = os.environ.get("FOODS_WEBHOOK")
    if not url:
        return
    import requests
    try:
        requests.post(url, json={"msgtype": "markdown",
                                 "markdown": {"content": text[:3800]}}, timeout=15)
    except Exception:
        pass


def run() -> dict:
    text, p = build()
    send_webhook(text)
    # L6 also renders the manuscript figures (Plan §5.1). A figure failure must
    # not take the report down with it — it is recorded and the report stands.
    figs = {}
    try:
        from .figures import run as figures_run
        figs = figures_run()
    except Exception as exc:  # noqa: BLE001
        figs = {"error": f"{type(exc).__name__}: {exc}"}
    return {"path": str(p), "chars": len(text), "at_utc": utc_iso(),
            "figures": {k: (v or {}).get("panel") for k, v in
                        (figs.get("panels") or {}).items()} or figs}


def health(summary: dict) -> dict:
    """Unattended-run self-check.

    There is no external paging channel configured (FOODS_WEBHOOK is unset),
    so a failed cycle would otherwise only be visible in a log nobody reads.
    This writes reports/ALERTS.md loudly when a stage errored or the report
    was not written, and clears it on a clean cycle.  It does not restart
    anything: a silent auto-restart is how double-label processes happen.
    """
    issues: list[str] = []
    for stage, res in (summary or {}).items():
        if isinstance(res, dict) and res.get("error"):
            issues.append(f"{stage}: {res['error']}")
    gates = read_json(path_of("data") / "analysis" / "gates.json", {}) or {}
    for name, g in (gates.get("gates") or {}).items():
        st = str(g.get("status", ""))
        if st.startswith("failed") or st.startswith("no_"):
            issues.append(f"gate {name}: {st}")
    latest = read_json(path_of("reports") / "daily" / "latest.json", {}) or {}
    if not latest.get("path"):
        issues.append("daily report missing (latest.json has no path)")
    outdir = path_of("reports") / "daily"
    p = outdir / "ALERTS.md"
    if issues:
        p.write_text("# ALERTS — " + utc_iso() + "\n\n" +
                     "\n".join(f"- {i}" for i in issues) + "\n", encoding="utf-8")
    else:
        p.write_text("# ALERTS\n\nnone at " + utc_iso() + "\n", encoding="utf-8")
    return {"n_issues": len(issues), "issues": issues, "path": str(p)}
