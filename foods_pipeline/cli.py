"""Command-line entry point for the Foods pipeline."""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback

from filelock import FileLock, Timeout

from .common import (cfg, get_logger, guard_disk, path_of, utc_iso, utcnow,
                     write_json)
from .manifest import Manifest


def _collect(source: str | None) -> dict:
    from .collect.cfws import CfwsCollector
    from .collect.municipal import MunicipalCollector
    from .collect.openfda import OpenFdaCollector
    from .collect.rasff import RasffCollector

    classes = {"cfws": CfwsCollector, "openfda": OpenFdaCollector,
               "rasff": RasffCollector, "municipal": MunicipalCollector}
    out = {}
    for name, cls in classes.items():
        if source not in (None, "all", name):
            continue
        if not cfg(f"collect.{name}.enabled", True):
            out[name] = {"skipped": "disabled"}
            continue
        try:
            out[name] = cls().run()
        except Exception as exc:  # noqa: BLE001
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _stage(name: str, fn, *args, **kwargs) -> dict:
    m = Manifest()
    run_id = f"{name}-{utcnow().strftime('%Y%m%dT%H%M%S')}"
    m.run_start(run_id, name)
    try:
        res = fn(*args, **kwargs)
        m.run_finish(run_id, "ok", res if isinstance(res, dict) else {"result": str(res)})
        return res
    except Exception as exc:  # noqa: BLE001
        m.run_finish(run_id, "error", {"error": f"{type(exc).__name__}: {exc}"})
        raise


def cmd_clean(args) -> dict:
    from .clean.normalize import Cleaner
    return _stage("clean", Cleaner().run, limit=args.limit)


def cmd_label(args) -> dict:
    from .label.silver import Labeler
    return _stage("label", Labeler().run, limit=args.limit)


def cmd_extract(args) -> dict:
    from .extract.runner import Extractor
    return _stage("extract", Extractor().run)


def cmd_events(args) -> dict:
    from .collect.gov_events import GovEventsCollector
    return _stage("events", GovEventsCollector().run)


def cmd_analyze(args) -> dict:
    from .analyze import (attack, compare, displacement, gates, hawkes, keywords,
                          network, sensitivity, shocks, survival)
    out = {}
    for name, fn in (("network", network.run), ("attack", attack.run),
                     ("survival", survival.run), ("hawkes", hawkes.run),
                     ("shocks", shocks.run), ("sensitivity", sensitivity.run),
                     ("displacement", displacement.run), ("compare", compare.run),
                     ("keywords", keywords.run)):
        try:
            out[name] = fn()
        except Exception as exc:  # noqa: BLE001
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}
    # A module that raises leaves its previous JSON on disk untouched, and the
    # gate stage then reads that stale file as if it were this cycle's result.
    # The exception itself was invisible: this loop swallowed it, the process
    # still exited 0, and chain_locked only shows the last 300 chars of stdout.
    # Persist the failure so gates.json and verify_products.py can see it (D-61).
    failed = {k: v["error"] for k, v in out.items()
              if isinstance(v, dict) and v.get("error")}
    try:
        write_json(path_of("data") / "analysis" / "_module_status.json",
                   {"failed_modules": failed, "modules_run": sorted(out),
                    "at_utc": utc_iso()})
    except Exception as exc:  # noqa: BLE001
        get_logger("cli").warning("module status not written: %s", exc)
    out["gates"] = gates.run()
    for k, v in out.items():
        if isinstance(v, dict) and "status" not in v and k != "gates":
            out[k] = {"status": "ok", **{x: v[x] for x in list(v)[:6]}}
    return out


def cmd_figures(args) -> dict:
    from .report.figures import run as figures_run
    return figures_run()


def cmd_report(args) -> dict:
    from .report.daily import run as report_run
    return report_run()


def cmd_expand(args) -> dict:
    from .analyze.expansion import run_next
    return _stage("expand", run_next)


def cmd_run(args) -> dict:
    log = get_logger("run")
    lock = FileLock(str(path_of("state") / "cycle.lock"), timeout=int(cfg("runtime.lock_timeout", 3600)))
    with lock:
        guard_disk(log)
        summary = {"at_utc": utc_iso(), "collect": _collect(args.source)}
        # Plan §6.2: expansion is executed by the pipeline. It runs here, at
        # the head of the cycle, because the documents it collects must be
        # cleaned and labelled in the same cycle; the decision uses the gates
        # written by the previous cycle's analyze stage. The batch list is
        # pre-registered (config/expansion_queries.yaml) and every batch is
        # logged in the manifest kv.
        try:
            summary["expand"] = cmd_expand(args)
        except Exception as exc:  # noqa: BLE001
            log.exception("stage expand failed")
            summary["expand"] = {"error": f"{type(exc).__name__}: {exc}"}
        # D4 shares the daily cadence with collection: it is a listing crawl,
        # independent of the document stages, and H2 needs it before analyze.
        if cfg("collect.gov_events.enabled", True):
            try:
                summary["events"] = cmd_events(args)
            except Exception as exc:  # noqa: BLE001
                log.exception("stage events failed")
                summary["events"] = {"error": f"{type(exc).__name__}: {exc}"}
        else:
            summary["events"] = {"skipped": "disabled"}
        for name, fn in (("clean", cmd_clean), ("label", cmd_label),
                         ("extract", cmd_extract), ("analyze", cmd_analyze),
                         ("report", cmd_report)):
            ns = argparse.Namespace(limit=args.limit, source=args.source)
            try:
                summary[name] = fn(ns)
            except Exception as exc:  # noqa: BLE001
                log.exception("stage %s failed", name)
                summary[name] = {"error": f"{type(exc).__name__}: {exc}"}
                if name == "clean":
                    break  # downstream stages would have nothing to read
        from .report.daily import health
        summary["health"] = health(summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str)[:4000])
        return summary


def cmd_status(args) -> dict:
    m = Manifest()
    out = {"at_utc": utc_iso(), "counts": m.counts(),
           "sources": {k: m.kv_get(f"source_status:{k}") for k in
                       ("cfws", "openfda", "rasff", "municipal")},
           "stages": {k: m.kv_get(f"stage_status:{k}") for k in
                      ("clean", "label", "extract")},
           "events": m.kv_get("gov_events")}
    print(json.dumps(out, ensure_ascii=False, indent=2)[:6000])
    return out


def cmd_daemon(args) -> dict:
    """Daily cycle at a fixed UTC hour; survives SSH disconnect (run under setsid).

    The triggering condition is "the hour has passed and today has no
    successful cycle", not "the wall clock is inside the 02:00 minute
    window".  A manual chain can hold the cycle lock past 02:10; with the old
    condition the day's cycle was silently skipped.  A failed or timed-out
    attempt leaves the date unset and is retried after 10 minutes.
    """
    log = get_logger("daemon")
    m = Manifest()
    hour = int(args.hour)
    log.info("daemon started; daily cycle at %02d:00 UTC", hour)
    while True:
        now = utcnow()
        today = now.strftime("%Y-%m-%d")
        if now.hour >= hour and m.kv_get("daemon:last_run_date") != today:
            try:
                cmd_run(argparse.Namespace(source=None, limit=None))
                m.kv_set("daemon:last_run_date", today)
            except Exception:  # noqa: BLE001
                log.error("cycle failed:\n%s", traceback.format_exc())
            time.sleep(600)
        time.sleep(30)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="foods")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "status", "report", "extract", "analyze", "events",
                 "expand", "figures"):
        sub.add_parser(name)
    for name in ("collect", "clean", "label", "run"):
        p = sub.add_parser(name)
        p.add_argument("--source", default=None)
        p.add_argument("--limit", type=int, default=None)
    p = sub.add_parser("daemon")
    p.add_argument("--hour", type=int, default=2)
    args = ap.parse_args(argv)

    if args.cmd == "init":
        Manifest()
        for k in ("data", "state", "logs", "reports"):
            path_of(k)
        print("initialized")
        return 0
    if args.cmd == "collect":
        print(json.dumps(_collect(args.source), ensure_ascii=False, indent=2)[:5000])
        return 0
    fn = {"clean": cmd_clean, "label": cmd_label, "extract": cmd_extract,
          "analyze": cmd_analyze, "report": cmd_report, "run": cmd_run,
          "status": cmd_status, "daemon": cmd_daemon, "events": cmd_events,
          "expand": cmd_expand, "figures": cmd_figures}[args.cmd]
    res = fn(args)
    if args.cmd in ("clean", "label", "extract", "analyze", "report", "events",
                    "figures"):
        print(json.dumps(res, ensure_ascii=False, default=str)[:4000])
    if isinstance(res, dict) and "error" in res:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
