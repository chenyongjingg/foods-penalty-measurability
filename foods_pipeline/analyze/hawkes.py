"""Hawkes self-excitation fit for regeneration rhythm (Plan §6.1 E3, H2).

Exponential-kernel Hawkes process:
    lambda(t) = mu + sum_{ti < t} alpha * exp(-beta (t - ti))
Fitted by maximum likelihood on penalty-event dates (days). The branching
ratio n = alpha / beta measures self-excitation (n -> 0 is Poisson). Nested
likelihood-ratio test against a homogeneous Poisson (df = 2). If the fit does
not converge, the fallback is nonparametric: KS test of inter-event times
against the exponential distribution implied by the Poisson null.
"""
from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
from scipy import optimize, stats

from ..common import as_date, cfg, get_logger, path_of, utc_iso, write_json
from ..manifest import Manifest


def event_days() -> list[float]:
    """Penalty-event dates from the main (Chinese) corpus only.

    D3a openFDA is a comparison corpus (DEVIATIONS.md D-16); letting 246 US
    recall dates into the Hawkes fit would replace the CN enforcement rhythm
    with the US one and make any branching-ratio estimate uninterpretable.
    """
    m = Manifest()
    days: list[date] = []
    for doc in m.iter_stage("extracted"):
        if doc.get("source") not in ("cfws", "municipal"):
            continue
        meta = json.loads(doc.get("meta") or "{}")
        d = as_date(meta.get("date") or doc.get("published"))
        if d:
            days.append(d)
    uniq = sorted(set(days))
    if not uniq:
        return []
    t0 = uniq[0]
    return sorted((d - t0).days for d in days)


def _nll(params, t, T):
    mu, alpha, beta = params
    if mu <= 0 or alpha < 0 or beta <= 0:
        return 1e12
    ll = 0.0
    for i in range(len(t)):
        prev = t[:i]
        excite = np.sum(alpha * np.exp(-beta * (t[i] - prev))) if len(prev) else 0.0
        lam = mu + excite
        if lam <= 0:
            return 1e12
        ll += math.log(lam)
    integ = mu * T + np.sum(alpha / beta * (1 - np.exp(-beta * (T - t))))
    return -(ll - integ)


def run() -> dict:
    t = event_days()
    outdir = path_of("data") / "analysis"
    res = {"n_events": len(t), "at_utc": utc_iso()}
    if len(t) < 10:
        res.update({"status": "insufficient_events",
                    "note": "fewer than 10 dated penalty events"})
        write_json(outdir / "hawkes.json", res)
        return res
    T = max(t) + 1e-6
    t = np.array(t, dtype=float)
    # Poisson null: MLE mu = N / T
    mu0 = len(t) / T
    nll0 = -(np.sum(np.log(np.full(len(t), mu0))) - mu0 * T)
    best = None
    for alpha0 in (0.05, 0.2, 0.5):
        for beta0 in (0.01, 0.05, 0.2):
            x0 = np.array([mu0 * 0.5, alpha0, beta0])
            try:
                r = optimize.minimize(_nll, x0, args=(t, T), method="L-BFGS-B",
                                      bounds=[(1e-9, None), (0, None), (1e-6, None)],
                                      options={"maxiter": 500})
            except Exception:
                continue
            if r.success and (best is None or r.fun < best.fun):
                best = r
    if best is None:
        # Nonparametric fallback: KS of inter-event times vs exponential
        iet = np.diff(np.sort(t))
        if len(iet) >= 5:
            ks = stats.kstest(iet, "expon", args=(0, iet.mean()))
            res.update({"status": "nonparametric_fallback",
                        "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue),
                        "interpretation": "p<0.05 => inter-event times not exponential => clustering"})
        else:
            res.update({"status": "fit_failed"})
        write_json(outdir / "hawkes.json", res)
        return res
    mu, alpha, beta = [float(x) for x in best.x]
    ll1 = -best.fun
    lr = 2 * (ll1 - (-nll0))
    p = float(stats.chi2.sf(max(0.0, lr), 2))
    br = alpha / beta if beta else float("inf")
    timescale_days = 1.0 / beta if beta > 0 else float("inf")
    # A fit whose kernel decays in milliseconds on day-resolution data, or
    # whose branching ratio is at the critical value, is an optimizer artifact,
    # not evidence of self-excitation. Report it as degenerate instead of
    # quoting alpha/beta and a p-value that would look like a finding.
    degenerate = (not math.isfinite(br)) or br > 0.95 or timescale_days < 0.01
    res.update({"status": "degenerate_fit" if degenerate else "ok",
                "mu": mu, "alpha": alpha, "beta": beta,
                "branching_ratio": br, "kernel_timescale_days": timescale_days,
                "loglik": ll1, "loglik_poisson": -nll0,
                "lr_stat": float(lr), "lr_p": p,
                "self_exciting": bool(not degenerate and p < 0.05 and br > 0.05)})
    if degenerate:
        res["note"] = ("alpha/beta are not identified at this event resolution; "
                       "report as inconclusive, not as self-excitation")
        # Plan §6.1 fallback is a nonparametric check.  Inter-event times are
        # reported with the tie share because same-day penalties create zero
        # gaps, which the exponential KS treats as evidence of clustering.
        iet = np.diff(np.sort(t))
        pos = iet[iet > 0]
        np_out: dict = {"tie_share": round(float((iet == 0).mean()), 4)}
        if len(pos) >= 5:
            ks = stats.kstest(pos, "expon", args=(0, pos.mean()))
            np_out.update({"ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue),
                           "ks_n": int(len(pos))})
        # Dispersion index of daily counts: var/mean.  Under a homogeneous
        # Poisson process it is ~1; >>1 means clustering, <1 means the process
        # is more regular than Poisson.  Chi-square reference with n-1 df.
        counts = np.bincount(t.astype(int), minlength=int(T) + 1)
        mean = counts.mean()
        if mean > 0 and len(counts) > 2:
            disp = float(counts.var(ddof=1) / mean)
            # The chi-square reference is unreliable when the daily mean is
            # far below 1, so the p-value comes from a Monte Carlo null with
            # the same mean and number of days.
            rng = np.random.default_rng(int(cfg("analysis.seed", 20261104)))
            sims = rng.poisson(mean, size=(1000, len(counts)))
            sim_d = sims.var(axis=1, ddof=1) / mean
            np_out.update({"dispersion_index": round(disp, 4),
                           "dispersion_p_mc": float((sim_d >= disp).mean()),
                           "dispersion_mc_reps": 1000,
                           "dispersion_days": int(len(counts)),
                           "dispersion_mean_per_day": round(float(mean), 4)})
        np_out["note"] = ("KS uses positive gaps only; zero gaps (same-day "
                          "penalties) are reported separately as tie_share")
        res["nonparametric"] = np_out
    write_json(outdir / "hawkes.json", res)
    get_logger("analyze.hawkes").info("hawkes: %s", res["status"])
    return res
