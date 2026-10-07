"""Glue: walk-forward dependence estimation + card engine over many seasons."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from backtest.cards import SelectionParams, run_card_backtest
from backtest.dependence import dependence_summary, joint_probability, same_day_pairs


def rho_by_season(pred: pd.DataFrame, n_boot: int = 200) -> dict[str, tuple[float, float]]:
    """rho (point, lower 2.5%) for each season, from SAME-DAY pairs of earlier seasons only."""
    seasons = list(dict.fromkeys(pred.sort_values("date").season))
    pairs = same_day_pairs(pred[pred.eligible_data])
    out = {}
    for i, s in enumerate(seasons):
        hist = pairs[pairs.season.isin(seasons[:i])]
        if len(hist) < 2000:
            out[s] = (np.nan, np.nan)
            continue
        d = dependence_summary(hist, n_boot=n_boot)
        out[s] = (d["z_corr"], d["z_corr_ci"][0])
    return out


def run_engine(pred: pd.DataFrame, base: SelectionParams, seasons: list[str]):
    rhos = rho_by_season(pred)
    slates, picks = [], []
    for s in seasons:
        sub = pred[pred.season == s]
        if sub.empty or not sub.calibrated.any():
            continue
        rho, rho_lo = rhos.get(s, (np.nan, np.nan))
        if np.isnan(rho):
            # no reliable dependence estimate: be conservative (no independence assumption):
            # use rho = 0 for the point estimate and a negative lower bound
            rho, rho_lo = 0.0, -0.05
        sp = replace(base, rho_hat=rho, rho_lo=rho_lo)
        a, b = run_card_backtest(sub, sp)
        a["rho_hat"], a["rho_lo"] = rho, rho_lo
        slates.append(a)
        picks.append(b)
    return (pd.concat(slates, ignore_index=True),
            pd.concat(picks, ignore_index=True) if picks else pd.DataFrame())


def forced_best_pair(pred: pd.DataFrame, rho: float, min_p: float = 0.0) -> pd.DataFrame:
    """DIAGNOSTIC ONLY (not the engine): every slate, take the pair of eligible games
    with the highest calibrated joint probability among games with p_cal >= min_p.
    Shows the empirical ceiling of 2/2 rates the model can reach if forced to bet."""
    rows = []
    d = pred[pred.calibrated & pred.eligible_data & (pred.p_cal >= min_p)]
    for date, day in d.groupby("date"):
        if len(day) < 2:
            continue
        top = day.nlargest(2, "p_cal")    # with a common rho the max-joint pair = top-2 marginals
        a, b = top.iloc[0], top.iloc[1]
        res = [("W" if r.total > r.line else "P" if r.total == r.line else "L") for r in (a, b)]
        rows.append({"date": date, "season": a.season, "p_a": a.p_cal, "p_b": b.p_cal,
                     "joint_cal": float(joint_probability(a.p_cal, b.p_cal, rho)),
                     "card_2of2": int(res == ["W", "W"]),
                     "card_wins": sum(r == "W" for r in res),
                     "double_profit": (-1.0 if "L" in res else
                                       np.prod([1.909 if r == "W" else 1.0 for r in res]) - 1.0)})
    return pd.DataFrame(rows)
