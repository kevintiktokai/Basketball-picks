"""Every bet of one season for the straight bets + 2.5+ card plan, as it would have been placed.

Straight bets: locked v3 engine, calibrated P >= 55% at the opener, taken at the best book's opening
number and price (books more than 3 points off the median opener ignored; -110 at the median
opener when no per-book prices exist). Card: the locked 2.5+ target card, at most one per slate.
Stakes: 1% of the morning balance on every bet, starting from $10,000 (reports/season_percent.md);
a day's stakes are capped at the balance.

usage: python scripts/season_ledger.py [season]          (default 2023-24)
Writes reports/ledger_<season>.json and reports/ledger_<season>.csv.
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

from backtest.odds_cards import best_main
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import load
from stage3_common import evaluate

SEASON = sys.argv[1] if len(sys.argv) > 1 else "2023-24"
START, FRAC, P_MIN = 10_000.0, 0.01, 0.55


def main():
    P, cals, calm = load()
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    G = P.drop_duplicates("game_key").set_index("game_key")

    M = main_line_probs(P, cals)
    S = M[M.eligible & (M.season == SEASON) & (M.p_best >= P_MIN)].copy()
    rows = []
    for _, r in S.iterrows():
        side = int(r.best_side)
        line, price, book = best_main(r.books_json, side)
        if np.isnan(line):
            line, price, book = r.line, 1 + 100 / 110, None
        res = 0 if r.outcome == line else (1 if (r.outcome > line if side == 1 else r.outcome < line) else -1)
        rows.append({"date": r.date.strftime("%Y-%m-%d"), "game_key": r.game_key, "away": r.away_name, "home": r.home_name,
                     "side": "OVER" if side == 1 else "UNDER", "opener": float(r.line), "line": float(line),
                     "price": float(price), "book": book or "", "p": float(r.p_best), "final": float(r.outcome), "res": res})
    ST = pd.DataFrame(rows)

    _, cards = evaluate(P, cals, calm, books, [SEASON])
    C = cards[list(cards)[0]].sort_values("date")
    crows = []
    for _, c in C.iterrows():
        legs = []
        for l in ("a", "b"):
            g = G.loc[c[f"game_{l}"]]
            side = int(c[f"side_{l}"])
            thr = float(c[f"thr_{l}"])
            legs.append({"away": g.away_name, "home": g.home_name, "side": "OVER" if side == 1 else "UNDER",
                         "opener": float(g.line), "line": thr, "moved": float(side * (g.line - thr)),
                         "main": bool(c[f"main_{l}"]), "odds": float(c[f"odds_{l}"]), "p": float(c[f"p_{l}"]),
                         "final": float(g.outcome), "win": bool(c[f"win_{l}"]), "push": bool(c[f"push_{l}"])})
        crows.append({"date": pd.Timestamp(c.date).strftime("%Y-%m-%d"), "legs": legs, "odds": float(c.combined_odds),
                      "p": float(c.joint_model), "profit_per_unit": float(c.profit), "won": int(c.card_win)})
    CD = pd.DataFrame(crows)

    # day by day at 1% of the morning balance
    days = sorted(set(ST.date) | set(CD.date))
    bal, peak, maxdd = START, START, 0.0
    day_rows = []
    ST["stake"], ST["pnl"] = np.nan, np.nan
    CD["stake"], CD["pnl"] = np.nan, np.nan
    for d in days:
        si = ST.index[ST.date == d]
        ci = CD.index[CD.date == d]
        n = len(si) + len(ci)
        stake = min(FRAC * bal, bal / n)
        sp = np.where(ST.loc[si, "res"] == 1, stake * (ST.loc[si, "price"] - 1), np.where(ST.loc[si, "res"] == -1, -stake, 0.0))
        cp = stake * CD.loc[ci, "profit_per_unit"].values
        ST.loc[si, "stake"], ST.loc[si, "pnl"] = stake, sp
        CD.loc[ci, "stake"], CD.loc[ci, "pnl"] = stake, cp
        start_bal = bal
        bal += sp.sum() + cp.sum()
        peak = max(peak, bal)
        maxdd = max(maxdd, 1 - bal / peak)
        dec = ST.loc[si][ST.loc[si, "res"] != 0]
        day_rows.append({"date": d, "straight": len(si), "won": int((dec.res == 1).sum()), "lost": int((dec.res == -1).sum()),
                         "card": len(ci), "card_won": int(CD.loc[ci, "won"].sum()) if len(ci) else None,
                         "pnl": float(sp.sum() + cp.sum()), "start": float(start_bal), "end": float(bal)})
    DY = pd.DataFrame(day_rows)
    dec = ST[ST.res != 0]
    summary = {"season": SEASON, "start": START, "end": float(bal), "max_drawdown": float(maxdd),
               "straight": int(len(ST)), "straight_won": int((dec.res == 1).sum()), "straight_lost": int((dec.res == -1).sum()),
               "straight_push": int((ST.res == 0).sum()), "straight_pnl": float(ST.pnl.sum()),
               "cards": int(len(CD)), "cards_won": int(CD.won.sum()), "card_pnl": float(CD.pnl.sum()),
               "days": int(len(DY)), "best_day": DY.loc[DY.pnl.idxmax()].to_dict(), "worst_day": DY.loc[DY.pnl.idxmin()].to_dict(),
               "avg_card_odds": float(CD.odds.mean()), "alt_leg_share": float(np.mean([not l["main"] for ls in CD.legs for l in ls]))}
    tag = SEASON.replace("-", "_")
    out = {"summary": summary, "days": day_rows,
           "straight": ST.drop(columns=["game_key"]).round(4).to_dict("records"),
           "cards": [{**r, "stake": round(r["stake"], 2), "pnl": round(r["pnl"], 2)} for r in CD.to_dict("records")]}
    (ROOT / "reports" / f"ledger_{tag}.json").write_text(json.dumps(out, default=float))
    flat = ST.assign(kind="straight").rename(columns={"res": "result"})
    legs = []
    for r in CD.itertuples():
        for j, l in enumerate(r.legs, 1):
            legs.append({"date": r.date, "kind": f"2.5+ card leg {j}", **{k: l[k] for k in ("away", "home", "side", "opener", "line", "final")},
                         "price": l["odds"], "p": l["p"], "result": 1 if l["win"] else (0 if l["push"] else -1),
                         "card_odds": r.odds, "card_won": r.won, "stake": r.stake if j == 1 else np.nan, "pnl": r.pnl if j == 1 else np.nan})
    pd.concat([flat, pd.DataFrame(legs)], ignore_index=True).sort_values(["date", "kind"]).to_csv(
        ROOT / "reports" / f"ledger_{tag}.csv", index=False)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("best_day", "worst_day")}, indent=1))
    print("best day", summary["best_day"]["date"], round(summary["best_day"]["pnl"]), "worst day", summary["worst_day"]["date"], round(summary["worst_day"]["pnl"]))
    log_experiment("season_ledger", {"season": SEASON, "start": START, "frac": FRAC}, {"summary": {k: v for k, v in summary.items() if not isinstance(v, dict)}})


if __name__ == "__main__":
    main()
