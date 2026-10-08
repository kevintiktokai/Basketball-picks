"""EXPLORATORY follow-up to improvement study 1 (run after its pre-registered decision; changes
nothing in the engine). Two questions:

1. Why does the side-aware calibrator give better probabilities but not better bets? Bets the side
   term drops and adds, and a volume-matched comparison (same number of bets per season).
2. Where else could the NCAAB mean model gain? Out-of-sample residual (total - opener - mu) scanned
   against candidate signals per era; a signal is a lead only if its sign agrees in all three eras.

Writes reports/improve_explore.md. Leads found here must be pre-registered and re-tested before use.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import improve_calibration as IC
from backtest.analysis import df_to_md
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment


def roi110(w: float) -> float:
    return w * 100 / 110 - (1 - w)


def bet_groups(A: pd.DataFrame, B: pd.DataFrame) -> pd.DataFrame:
    k = A.index
    a = (A.p_best >= IC.P_MIN) & ~A.best_push
    b = (B.p_best.reindex(k) >= IC.P_MIN) & ~B.best_push.reindex(k)
    rows = []
    for era in IC.ERAS + ["POOLED"]:
        m = pd.Series(True, index=k) if era == "POOLED" else (A.era == era)
        for label, mask, src in (("kept by both", a & b & m, A), ("dropped by C1 (C0 only)", a & ~b & m, A),
                                 ("added by C1 (C1 only)", b & ~a & m, B.reindex(k))):
            x = src.loc[mask[mask].index]
            w = x.best_win.mean()
            rows.append({"era": era, "group": label, "bets": len(x), "win": w, "predicted": x.p_best.mean(),
                         "ROI @-110": roi110(w), "Under share": (x.best_side == -1).mean()})
    return pd.DataFrame(rows)


def matched_volume(res: dict) -> pd.DataFrame:
    """Each calibrator's top-N games per season by P(best side), N = the locked engine's bet count."""
    base = res["C0_locked"]
    rows = []
    for name, M in res.items():
        tops = []
        for s, g in M[~M.best_push].groupby("season"):
            n0 = int(((base.season == s) & (base.p_best >= IC.P_MIN) & ~base.best_push).sum())
            tops.append(g.sort_values("p_best", ascending=False).head(n0))
        T = pd.concat(tops)
        for era in IC.ERAS + ["POOLED"]:
            t = T if era == "POOLED" else T[T.era == era]
            w = t.best_win.mean()
            rows.append({"calibrator": name, "era": era, "bets": len(t), "win": w, "ROI @-110": roi110(w)})
    return pd.DataFrame(rows).pivot(index="calibrator", columns="era", values="ROI @-110")[IC.ERAS + ["POOLED"]]


def residual_scan(P: pd.DataFrame) -> pd.DataFrame:
    E = P[P.eligible & P.calibrated & P.season.isin(IC.ERA)].copy()
    E["era"] = E.season.map(IC.ERA)
    E["r"] = E.outcome - E.line - E.mu
    cand = {
        "mu (model's own edge)": E.mu,
        "tempo gap (fast vs slow team)": (E.rt_tempo_home - E.rt_tempo_away).abs(),
        "efficiency mismatch": ((E.rt_off_home - E.rt_def_away) - (E.rt_off_away - E.rt_def_home)).abs(),
        "games-played gap": (E.rt_n_home - E.rt_n_away).abs(),
        "home team-total gap vs spread": E.x_home_tt,
        "away team-total gap vs spread": E.x_away_tt,
        "rest difference (home - away)": (E.home_rest - E.away_rest).clip(-7, 7),
        "longest rest": np.maximum(E.home_rest, E.away_rest).clip(0, 10),
        "opening total (level)": E.line,
        "spread size": E.abs_spread,
        "neutral site": E.neutral_i,
        "Monday": (E.dow == 0).astype(float),
        "Friday": (E.dow == 4).astype(float),
        "Sunday": (E.dow == 6).astype(float),
        "November": (E.month == 11).astype(float),
        "December": (E.month == 12).astype(float),
        "January": (E.month == 1).astype(float),
        "February": (E.month == 2).astype(float),
        "March": (E.month == 3).astype(float),
        "late season (both 25+ games)": (E.rt_min_games >= 25).astype(float),
        "slate size": E.slate_size,
        "model SD": E.sd,
    }
    rows = []
    for name, x_all in cand.items():
        rec = {"signal": name}
        ts = []
        for era in IC.ERAS:
            m = (E.era == era).values & x_all.notna().values
            x = x_all.values[m] - x_all.values[m].mean()
            r = E.r.values[m]
            b = (x * r).sum() / (x ** 2).sum()
            res = r - r.mean() - b * x
            t = b / np.sqrt((res ** 2).sum() / (len(r) - 2) / (x ** 2).sum())
            rec[f"t {era}"] = t
            ts.append(t)
        rec["same sign in all eras"] = bool(np.all(np.sign(ts) == np.sign(ts[0])))
        rec["weakest abs(t)"] = float(np.min(np.abs(ts)))
        rows.append(rec)
    R = pd.DataFrame(rows).sort_values(["same sign in all eras", "weakest abs(t)"], ascending=[False, False])
    slope = E.groupby("era").apply(lambda e: np.polyfit(e.mu, e.outcome - e.line, 1)[0]).reindex(IC.ERAS)
    return R, slope


def main():
    P, cals0, calm = IC.load()
    res = {}
    for name, terms in IC.CANDS.items():
        cals = cals0 if terms == "base" else IC.refit(P, terms)
        M = main_line_probs(P, cals)
        M = M[M.eligible & M.season.isin(IC.ERA)].copy()
        M["era"] = M.season.map(IC.ERA)
        res[name] = M.set_index("game_key")
    G = bet_groups(res["C0_locked"], res["C1_side"])
    V = matched_volume(res)
    units = {n: float(np.where(M[(M.p_best >= IC.P_MIN) & ~M.best_push].best_win == 1, 100 / 110, -1.0).sum())
             for n, M in res.items()}
    R, slope = residual_scan(P)
    lines = ["# Exploratory follow-up to improvement study 1 (does not change the engine)\n",
             "_Run after the pre-registered decision in `reports/improve_calibration.md` (none adopted). "
             "Anything here is a lead for a new pre-registered study, not evidence for adoption._\n",
             "## 1. Better probabilities, not better bets: what the side term changes\n",
             f"Bets at calibrated P >= {IC.P_MIN:.0%}, locked calibrator (C0) vs side-aware (C1):\n",
             df_to_md(G, "{:.3f}"), "",
             "Same number of bets per season as the locked engine (each calibrator's most confident games), "
             "ROI at -110:\n", df_to_md(V.reset_index(), "{:.4f}"), "",
             "Total units at -110 over 2011-26 at the 55% threshold: "
             + ", ".join(f"{n} {u:+.0f}" for n, u in units.items()) + ".\n",
             "Reading: the side term moves about 1,550 marginal Overs out and about 2,750 marginal Unders in. "
             "Both groups are only slightly profitable (about +5% at -110), so the average ROI falls while the "
             "total rises with volume. At equal volume the locked ranking does better pooled (and in every "
             "era except C2 in 2011-18), so the Over tilt from overtime skew distorts probability levels without hurting the choice of games. "
             "Re-testing this on total units would be a new hypothesis, and the forward season would have to "
             "confirm it.\n",
             "## 2. Residual scan of the mean model (out of sample, per era)\n",
             "t-statistic of the slope of (total - opener - mu) on each signal; abs(t) > 2 is conventional "
             "significance for one test, but about 22 signals were scanned, so expect about one false hit per era.\n",
             df_to_md(R, "{:.2f}"), "",
             "Realised slope of (total - opener) on the model's mu (1.0 = perfectly scaled): "
             + ", ".join(f"{e} {v:.2f}" for e, v in slope.items()) + ".\n",
             "## 3. Leads for the next pre-registered study\n",
             "* **The model's edge is about 20-30% too large in points** (realised slope 0.70-0.88 in every era). "
             "The calibrator already shrinks it in probability space, so the ranking of games is unaffected; "
             "it matters mainly for the projected totals shown on the card. Low expected profit.",
             "* **Tempo mismatch goes under** (same sign in all eras, t -1.3 to -2.9): when a fast team meets a "
             "slow one, totals come in below the additive tempo forecast, consistent with the slower team "
             "controlling pace. A candidate feature for the possessions forecast, to be pre-registered with its "
             "own adoption rule (ROI at matched volume in every era).",
             "* **Efficiency mismatches go under** (same sign, weaker): blowouts with bench minutes. Overlaps "
             "with the spread size, which is already in the model.",
             "* Nothing else (rest, day of week, month, neutral site, slate size, total level) is consistent "
             "across eras: the engine already uses what these data contain.",
             "* The larger untapped sources are outside these data: injuries and lineups (decisive in the "
             "NBA/WNBA), and the time the bet is placed (lines moved toward the engine's side in 67-80% of bets; "
             "the edge decays after the opener, so speed of execution is worth more than any of the leads above)."]
    (ROOT / "reports" / "improve_explore.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("improve_explore", {"after": "improve_calibration"},
                   {"matched_volume_roi": V.reset_index().to_dict("records"), "units": units,
                    "scan": R.to_dict("records")})


if __name__ == "__main__":
    main()
