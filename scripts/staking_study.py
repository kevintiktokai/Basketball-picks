"""Staking study (decision layer, not a model change): how much to stake on each NCAAB single.

The locked v3 engine's out-of-sample bets (calibrated P >= 55% at the opener) are staked four ways,
all on a fixed 100-unit bankroll (1 unit = 1% of it; no compounding, since betting limits stop a
real bankroll compounding for long): flat 1 unit; tiered by probability; and fractional Kelly at
1/8 and 1/4 of the growth-optimal stake (each day's total capped at 25% of the bankroll). The
scheme is judged on 2011-21; 2021-26 (real best-book prices) is shown as a check, not used to choose.
Writes reports/staking_study.md.
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

from backtest.analysis import df_to_md
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import book_stats, load

P_MIN = 0.55
PERIODS = {"2011-21 (choose here)": [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2021)],
           "2021-26 (check, real prices)": [f"{y}-{str(y + 1)[2:]}" for y in range(2021, 2026)]}
TIERS = [(0.55, 1.0), (0.57, 1.5), (0.59, 2.0), (0.62, 2.5)]
DAY_CAP = 0.25


def bets() -> pd.DataFrame:
    P, cals, _ = load()
    M = main_line_probs(P, cals)
    B = M[M.eligible & (M.p_best >= P_MIN)].copy()
    B["odds"] = 1 + 100 / 110
    live = B.books_json.notna() & B.books_json.astype(str).str.startswith("{")
    st = [book_stats(bj, int(s))[:2] for bj, s in zip(B.loc[live, "books_json"], B.loc[live, "best_side"])]
    B["line_real"], B["odds_real"] = np.nan, np.nan
    if st:
        B.loc[live, ["line_real", "odds_real"]] = np.array(st, dtype=float)
    return B.sort_values("date")


def results(B: pd.DataFrame, real: bool) -> tuple[np.ndarray, np.ndarray]:
    """Per-bet decimal odds and outcome (+1 win, 0 push, -1 loss) at -110 or the best real price."""
    if real:
        ok = B.line_real.notna()
        line = np.where(ok, B.line_real, B.line)
        odds = np.where(ok, B.odds_real, 1 + 100 / 110)
    else:
        line, odds = B.line.values, B.odds.values
    win = np.where(B.best_side == 1, B.outcome > line, B.outcome < line)
    push = B.outcome.values == line
    return odds, np.where(push, 0, np.where(win, 1, -1))


def simulate(B: pd.DataFrame, scheme: str, real: bool) -> dict:
    odds, res = results(B, real)
    p = B.p_best.values
    dates = B.date.values
    bank, peak, max_dd, staked, profit = 100.0, 100.0, 0.0, 0.0, 0.0
    for day in np.unique(dates):
        idx = np.where(dates == day)[0]
        if scheme == "flat 1u":
            stakes = np.ones(len(idx))
        elif scheme == "tiered 1-2.5u":
            stakes = np.array([max(u for t, u in TIERS if p[i] >= t) for i in idx])
        else:
            frac = 0.25 if scheme == "Kelly 1/4" else 0.125
            b = odds[idx] - 1
            f = np.clip((p[idx] * (b + 1) - 1) / b, 0, None) * frac
            if f.sum() > DAY_CAP:
                f *= DAY_CAP / f.sum()
            stakes = f * 100.0                     # fixed bankroll: stakes in units of 1%
        pnl = np.where(res[idx] == 1, stakes * (odds[idx] - 1), np.where(res[idx] == -1, -stakes, 0.0))
        staked += stakes.sum()
        profit += pnl.sum()
        bank += pnl.sum()
        peak = max(peak, bank)
        max_dd = max(max_dd, peak - bank)
    return {"scheme": scheme, "bets": len(B), "avg stake (units)": staked / len(B), "staked": staked,
            "profit (units)": profit, "ROI per unit staked": profit / staked, "max drawdown (units)": max_dd,
            "profit / max drawdown": profit / max_dd}


def main():
    B = bets()
    rows = []
    for period, seasons in PERIODS.items():
        b = B[B.season.isin(seasons)]
        for scheme in ("flat 1u", "tiered 1-2.5u", "Kelly 1/8", "Kelly 1/4"):
            rows.append({"period": period, **simulate(b, scheme, real=period.startswith("2021"))})
    R = pd.DataFrame(rows)
    by_p = []
    for period, seasons in PERIODS.items():
        b = B[B.season.isin(seasons)]
        odds, res = results(b, real=period.startswith("2021"))
        for lo, hi in ((0.55, 0.57), (0.57, 0.59), (0.59, 0.62), (0.62, 1.01)):
            m = (b.p_best >= lo).values & (b.p_best < hi).values
            r, o = res[m], odds[m]
            pnl = np.where(r == 1, o - 1, np.where(r == -1, -1.0, 0.0))
            by_p.append({"period": period, "P": f"{lo:.0%}-{min(hi, 1):.0%}", "bets": int(m.sum()),
                         "win": float((r[r != 0] == 1).mean()), "predicted": float(b.p_best[m].mean()),
                         "ROI flat": float(pnl.mean())})
    lines = ["# Staking study — how much to put on each NCAAB single (locked v3 engine)\n",
             "_A decision layer on top of the unchanged engine. Bets: calibrated P >= 55% at the opener. Chosen "
             "on 2011-21 at -110; 2021-26 at the best real price is a check, not used for the choice. Fixed "
             "100-unit bankroll (1 unit = 1%), no compounding; Kelly stakes capped at 25% of the bankroll per day._\n",
             "## Win rate and ROI by the engine's probability\n", df_to_md(pd.DataFrame(by_p), "{:.3f}"), "",
             "## Staking schemes\n", df_to_md(R, "{:.3f}"), "",
             "Tiers: " + ", ".join(f"P >= {t:.0%}: {u}u" for t, u in TIERS) + "."]
    (ROOT / "reports" / "staking_study.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("staking_study", {"tiers": TIERS, "day_cap": DAY_CAP}, {"rows": R.astype(str).to_dict("records")})


if __name__ == "__main__":
    main()
