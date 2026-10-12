"""How selective do the NCAAB straight bets have to be to win 60%? Win rate, ROI, volume and a
season's money at each probability threshold (locked v3 engine, opener), and the day's best N
ranked by value at the best book's price.

Every era is shown: 2011-18 and 2018-21 at -110, 2021-26 also at the best book's real opening
price (books more than 3 points off the median ignored; -110 at the median when no per-book price).
The engine's probabilities are calibrated, so a threshold buys win rate by giving up volume; the
season money (from $10,000 at 1% of the morning balance per bet, the 2.5+ card included) shows
what that trade costs. Writes reports/threshold_curve.md and reports/threshold_curve.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment
from diagnose_bets import load
from stage3_common import evaluate
from top_n_daily import ERAS, pnl, season_money, straight_bets

THRESHOLDS = [0.55, 0.56, 0.57, 0.58, 0.59, 0.60, 0.62]


def row(B: pd.DataFrame, n_seasons: int, real: bool) -> dict:
    d110 = B[B.res110 != 0]
    out = {"bets": len(B), "per season": len(B) / n_seasons, "avg P": float(B.p_best.mean()) if len(B) else np.nan,
           "won @-110 line": float((d110.res110 == 1).mean()) if len(d110) else np.nan,
           "ROI @-110": float(pnl(B.res110.values, 1 + 100 / 110).mean()) if len(B) else np.nan}
    if real:
        dr = B[B.res_real != 0]
        out["won at best book"] = float((dr.res_real == 1).mean()) if len(dr) else np.nan
        out["ROI best book"] = float(pnl(B.res_real.values, B.bprice.values).mean()) if len(B) else np.nan
    return out


def main():
    P, cals, calm = load()
    S = straight_bets(P, cals)                     # every P >= 55% bet, ranked within its day
    S["ev"] = S.p_best * S.bprice - 1
    S["rank_ev"] = S.groupby("day").ev.rank(ascending=False, method="first")
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    _, C = evaluate(P, cals, calm, books, sum(ERAS.values(), []))
    card = C[[k for k in C if k.startswith("TARGET")][0]].copy()
    card["day"] = pd.to_datetime(card.date).dt.strftime("%Y-%m-%d")

    rows = []
    for era, seasons in ERAS.items():
        E, real = S[S.era == era], era == "2021-26"
        for t in THRESHOLDS:
            rows.append({"era": era, "rule": f"P >= {t:.0%}", **row(E[E.p_best >= t], len(seasons), real)})
        for n in (1, 2):
            key = "rank_ev" if real else "rank"
            rows.append({"era": era, "rule": f"best {n} a day" + (" by value" if real else " by P"),
                         **row(E[E[key] <= n], len(seasons), real)})
    T = pd.DataFrame(rows)

    money = []
    for s in ERAS["2021-26"]:
        Ss, cs = S[S.season == s], card[card.season == s]
        rec = {"season": s}
        for t in (0.55, 0.57, 0.58, 0.60):
            rec[f"P >= {t:.0%}"] = season_money(Ss[Ss.p_best >= t], cs, None, True)
        rec["best 2 by value"] = season_money(Ss[Ss.rank_ev <= 2], cs, None, True)
        money.append(rec)
    MO = pd.DataFrame(money)

    out = {"rows": rows, "money_2021_26": money}
    (ROOT / "reports" / "threshold_curve.json").write_text(json.dumps(out, indent=1, default=float))
    lines = ["# How selective must the NCAAB straight bets be to win 60%?\n",
             "Locked v3 engine at the opener. 2011-18 and 2018-21 at -110; 2021-26 also at the best book's real "
             "opening price. Per season = bets a season on average.\n",
             df_to_md(T, "{:.3f}"), "",
             "A season from $10,000 at 1% of the morning balance per bet, 2021-26 at real prices, the 2.5+ card "
             "included (end balance):\n", df_to_md(MO.round(0)), ""]
    (ROOT / "reports" / "threshold_curve.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("threshold_curve", {"thresholds": THRESHOLDS}, {"rows": rows})


if __name__ == "__main__":
    main()
