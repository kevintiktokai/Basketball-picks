"""Dependence between Over outcomes of games on the same slate.

We never assume independence. For every pair of games on the same date we
measure, on historical data only:
  * correlation of Over indicators (excluding pushes)
  * correlation of standardized model errors (resid - mu) / sd
  * the joint 2/2 rate vs the product of marginals
with date-clustered bootstrap confidence intervals.

The joint probability of a candidate pair is modelled with a Gaussian copula
on the latent standardized errors, using rho and its confidence band.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def same_day_pairs(pred: pd.DataFrame) -> pd.DataFrame:
    d = pred[~pred.push].copy()
    d["z"] = (d.resid - d.mu_resid) / d.sd
    rows = []
    for date, day in d.groupby("date"):
        if len(day) < 2:
            continue
        a = day[["game_id", "over", "z", "p_cal", "home", "away"]].to_numpy()
        n = len(a)
        i, j = np.triu_indices(n, 1)
        rows.append(pd.DataFrame({
            "date": date, "season": day.season.iloc[0],
            "over_a": a[i, 1].astype(int), "over_b": a[j, 1].astype(int),
            "z_a": a[i, 2].astype(float), "z_b": a[j, 2].astype(float),
            "p_a": a[i, 3].astype(float), "p_b": a[j, 3].astype(float),
        }))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def dependence_summary(pairs: pd.DataFrame, n_boot: int = 300, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)

    def stat(p):
        oa, ob = p.over_a.values, p.over_b.values
        joint = np.mean(oa & ob)
        prod = np.mean(oa) * np.mean(ob)
        return (np.corrcoef(oa, ob)[0, 1], np.corrcoef(p.z_a, p.z_b)[0, 1], joint - prod, joint)

    base = stat(pairs)
    dates = pairs.date.unique()
    groups = {d: g for d, g in pairs.groupby("date")}
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(dates, len(dates), replace=True)
        boots.append(stat(pd.concat([groups[d] for d in pick], ignore_index=True)))
    boots = np.array(boots)
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return {
        "n_pairs": int(len(pairs)), "n_dates": int(len(dates)),
        "over_corr": base[0], "over_corr_ci": (lo[0], hi[0]),
        "z_corr": base[1], "z_corr_ci": (lo[1], hi[1]),
        "joint_minus_product": base[2], "jmp_ci": (lo[2], hi[2]),
        "joint_over_rate": base[3],
    }


def joint_probability(p_a, p_b, rho):
    """P(A and B) for Bernoulli marginals p_a, p_b linked by a Gaussian copula."""
    p_a = np.clip(np.asarray(p_a, float), 1e-6, 1 - 1e-6)
    p_b = np.clip(np.asarray(p_b, float), 1e-6, 1 - 1e-6)
    za, zb = stats.norm.ppf(p_a), stats.norm.ppf(p_b)
    out = np.empty(np.broadcast(za, zb).shape)
    cov = [[1.0, rho], [rho, 1.0]]
    mvn = stats.multivariate_normal(mean=[0, 0], cov=cov)
    flat_a, flat_b = np.broadcast_arrays(za, zb)
    for k, (x, y) in enumerate(zip(flat_a.ravel(), flat_b.ravel())):
        out.ravel()[k] = mvn.cdf([x, y])
    return out if out.shape else float(out)


def required_individual_probability(target: float, rho: float) -> float:
    """Symmetric individual probability p such that P(both) = target."""
    lo, hi = target, 1.0 - 1e-9
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if joint_probability(mid, mid, rho) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
