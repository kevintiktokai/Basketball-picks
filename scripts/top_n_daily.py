"""Only the day's best N straight bets, against every bet that meets the system's requirements.

Straight bets: the locked v3 NCAAB engine, calibrated P >= 55% at the opener (the requirement).
"Best" = highest calibrated P that day (known before the games). Each day keeps its top 1, 2 or 3,
or all of them. The 2.5+ card (at most one a day) is the same in every plan.
Prices: -110 for every era; the best book's opening number and price for 2021-26 (books more than
3 points off the median opener ignored; -110 at the median opener when no per-book price exists),
as in reports/ledger_2023_24.*. Money: a season from $10,000 at 1% of the morning balance per bet.
Writes reports/top_n_daily.md and reports/top_n_daily.json.
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
from backtest.odds_cards import best_main
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import load
from stage3_common import evaluate

P_MIN, START, FRAC = 0.55, 10_000.0, 0.01
ERAS = {"2011-18": [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2018)],
        "2018-21": [f"{y}-{str(y + 1)[2:]}" for y in range(2018, 2021)],
        "2021-26": [f"{y}-{str(y + 1)[2:]}" for y in range(2021, 2026)]}
PLANS = {"top 1": 1, "top 2": 2, "top 3": 3, "all that qualify": None}


def straight_bets(P, cals) -> pd.DataFrame:
    M = main_line_probs(P, cals)
    S = M[M.eligible & (M.p_best >= P_MIN) & M.season.isin(sum(ERAS.values(), []))].copy()
    S["era"] = S.season.map({s: e for e, ss in ERAS.items() for s in ss})
    S["day"] = S.date.dt.strftime("%Y-%m-%d")
    side = S.best_side.astype(int)
    S["res110"] = np.where(S.best_push, 0, np.where(S.best_win == 1, 1, -1))
    lines, prices = [], []
    for bj, sd, ln in zip(S.books_json, side, S.line):
        l, p, _ = best_main(bj, int(sd))
        lines.append(ln if np.isnan(l) else l)
        prices.append(1 + 100 / 110 if np.isnan(l) else p)
    S["bline"], S["bprice"] = lines, prices
    won = np.where(side == 1, S.outcome > S.bline, S.outcome < S.bline)
    S["res_real"] = np.where(S.outcome == S.bline, 0, np.where(won, 1, -1))
    S["rank"] = S.groupby("day").p_best.rank(ascending=False, method="first")
    return S


def pnl(res, price):
    return np.where(res == 1, price - 1, np.where(res == -1, -1.0, 0.0))


def summary(B: pd.DataFrame, real: bool) -> dict:
    dec = B[B.res110 != 0]
    out = {"bets": len(B), "days": B.day.nunique(), "per day": len(B) / max(B.day.nunique(), 1),
           "won": float((dec.res110 == 1).mean()), "avg P": float(B.p_best.mean()),
           "ROI @-110": float(pnl(B.res110.values, 1 + 100 / 110).mean())}
    if real:
        d2 = B[B.res_real != 0]
        out["won (best book)"] = float((d2.res_real == 1).mean())
        out["ROI real price"] = float(pnl(B.res_real.values, B.bprice.values).mean())
    return out


def season_money(S: pd.DataFrame, cards: pd.DataFrame, n: int | None, real: bool) -> float:
    """One season from $10,000, 1% of the morning balance per bet, the 2.5+ card included."""
    B = S if n is None else S[S["rank"] <= n]
    u = pnl(B.res_real.values, B.bprice.values) if real else pnl(B.res110.values, 1 + 100 / 110)
    day_u = pd.Series(u, index=B.day.values).groupby(level=0).sum()
    day_n = pd.Series(1, index=B.day.values).groupby(level=0).sum()
    if len(cards):
        cu = cards.groupby("day").profit.sum()
        cn = cards.groupby("day").size()
        day_u = day_u.add(cu, fill_value=0.0)
        day_n = day_n.add(cn, fill_value=0)
    bal = START
    for d in sorted(day_u.index):
        stake = min(FRAC * bal, bal / day_n[d])
        bal += stake * day_u[d]
    return bal


def main():
    P, cals, calm = load()
    S = straight_bets(P, cals)
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    _, C = evaluate(P, cals, calm, books, sum(ERAS.values(), []))
    card = C[[k for k in C if k.startswith("TARGET")][0]].copy()
    card["day"] = pd.to_datetime(card.date).dt.strftime("%Y-%m-%d")
    card["era"] = card.season.map({s: e for e, ss in ERAS.items() for s in ss})

    rows = []
    for era in ERAS:
        E = S[S.era == era]
        for plan, n in PLANS.items():
            B = E if n is None else E[E["rank"] <= n]
            rows.append({"era": era, "plan": plan, **summary(B, real=(era == "2021-26"))})
    T = pd.DataFrame(rows)

    # by-P ranking vs the real price: the best 2 by expected value at the best book (2021-26)
    E = S[S.era == "2021-26"].copy()
    E["ev"] = E.p_best * E.bprice - 1
    E["rank_ev"] = E.groupby("day").ev.rank(ascending=False, method="first")
    ev2 = summary(E[E.rank_ev <= 2], real=True)

    cards = []
    for era in ERAS:
        c = card[card.era == era]
        cards.append({"era": era, "cards": len(c), "won": float(c.card_win.mean()), "avg odds": float(c.combined_odds.mean()),
                      "ROI": float(c.profit.mean())})

    money = []
    for s in sum(ERAS.values(), []):
        Ss, cs = S[S.season == s], card[card.season == s]
        real = s in ERAS["2021-26"]
        rec = {"season": s, "prices": "best book" if real else "-110"}
        for plan, n in PLANS.items():
            rec[plan] = season_money(Ss, cs, n, real)
        rec["card only"] = season_money(Ss.iloc[0:0], cs, None, real)
        money.append(rec)
    MO = pd.DataFrame(money)

    out = {"plans": rows, "ev_top2_2021_26": ev2, "cards": cards, "money": money}
    (ROOT / "reports" / "top_n_daily.json").write_text(json.dumps(out, indent=1, default=float))
    lines = ["# Only the day's best N straight bets vs every qualifying bet (NCAAB, locked v3)\n",
             "Qualifying = calibrated P >= 55% at the opener. Best = highest P that day. The 2.5+ card is the same in every plan.\n",
             df_to_md(T, "{:.3f}"), "",
             "2021-26, best two by expected value at the best book's price instead of by P: "
             + ", ".join(f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}" for k, v in ev2.items()) + "\n",
             "2.5+ card (at most one a day):\n", df_to_md(pd.DataFrame(cards), "{:.3f}"), "",
             "A season from $10,000 at 1% of the morning balance per bet, straight bets plus the 2.5+ card (end balance):\n",
             df_to_md(MO.round(0)), ""]
    (ROOT / "reports" / "top_n_daily.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("top_n_daily", {"p_min": P_MIN, "plans": list(PLANS), "start": START, "frac": FRAC},
                   {"plans": rows, "ev_top2": ev2, "cards": cards})


if __name__ == "__main__":
    main()
