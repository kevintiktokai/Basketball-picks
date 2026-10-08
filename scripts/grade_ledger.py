"""Grade the forward-test ledger (reports/live_ledger.csv) from final scores on
sportsbookreview.com, and print the running two-pick record.

usage: python scripts/grade_ledger.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from calibration.calibrate import wilson
from data import sbr_live

LEDGER = Path(__file__).resolve().parents[1] / "reports" / "live_ledger.csv"
SINGLES = Path(__file__).resolve().parents[1] / "reports" / "live_ledger_singles.csv"


def finals_for(date: str) -> dict:
    out = sbr_live.RAW / "totals" / f"{date}.json"
    try:                                            # refresh: games may have finished since recording
        bid = sbr_live.build_id()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(sbr_live._get(f"https://www.sportsbookreview.com/_next/data/{bid}/"
                                      + sbr_live.PATHS["totals"].format(d=date)))
    except Exception as e:                          # noqa: BLE001
        print(f"  could not refresh {date}: {e}")
    res = {}
    for r in sbr_live._rows(out) if out.exists() else []:
        gv = r["gameView"]
        if str(gv.get("gameStatusText", "")).startswith("Final"):
            key = (gv["awayTeam"]["fullName"], gv["homeTeam"]["fullName"])
            res[key] = gv["homeTeamScore"] + gv["awayTeamScore"]
    return res


def grade_singles() -> None:
    """Singles ledger: win/push/loss at the recorded line, profit = stake x (price - 1) or -stake."""
    if not SINGLES.exists():
        return
    L = pd.read_csv(SINGLES)
    for c in ("total", "result", "profit"):
        if c not in L:
            L[c] = np.nan
    cache = {}
    for i, r in L[L.result.isna()].iterrows():
        fin = cache.setdefault(r.date, finals_for(r.date))
        tot = fin.get((r.away, r.home))
        if tot is None:
            continue
        L.at[i, "total"] = tot
        res = 0 if tot == r.line else (1 if (tot > r.line if r.side == "OVER" else tot < r.line) else -1)
        L.at[i, "result"] = res
        L.at[i, "profit"] = r.stake_frac * (r.price - 1) if res == 1 else (-r.stake_frac if res == -1 else 0.0)
    L.to_csv(SINGLES, index=False)
    g = L[L.result.notna()]
    if len(g):
        dec = g[g.result != 0]
        k, n = int((dec.result == 1).sum()), len(dec)
        lo, hi = wilson(k, n)
        print(f"[singles] graded: {len(g)}   won {k}/{n} ({k / max(n, 1):.1%}, 95% CI {lo:.1%}-{hi:.1%})   "
              f"model expected {g.p.mean():.1%}   return per unit staked {g.profit.sum() / g.stake_frac.sum():+.1%}   "
              f"bankroll change {g.profit.sum():+.2%}")
    print(f"Ungraded singles: {int(L.result.isna().sum())}")


def main():
    grade_singles()
    if not LEDGER.exists():
        sys.exit("no card ledger yet: run predict_cards.py with --record")
    L = pd.read_csv(LEDGER)
    for c in ("a_total", "b_total", "a_win", "b_win", "card_2of2"):
        if c not in L:
            L[c] = np.nan
    for i, r in L[L.card_2of2.isna()].iterrows():
        fin = finals_for(r.date)
        for leg in ("a", "b"):
            tot = fin.get((r[f"{leg}_away"], r[f"{leg}_home"]))
            if tot is None:
                continue
            L.at[i, f"{leg}_total"] = tot
            win = tot > r[f"{leg}_line"] if r[f"{leg}_side"] == "OVER" else tot < r[f"{leg}_line"]
            L.at[i, f"{leg}_win"] = int(win)
        if not (np.isnan(L.at[i, "a_win"]) or np.isnan(L.at[i, "b_win"])):
            L.at[i, "card_2of2"] = int(L.at[i, "a_win"] == 1 and L.at[i, "b_win"] == 1)
            if "combined_odds" in L and not pd.isna(L.at[i, "combined_odds"]):
                L.at[i, "profit"] = (L.at[i, "combined_odds"] - 1) if L.at[i, "card_2of2"] == 1 else -1.0
    L.to_csv(LEDGER, index=False)
    g = L[L.card_2of2.notna()]
    groups = g.groupby(g["product"].fillna("sixty")) if "product" in g else [("sixty", g)]
    for prod, gg in groups:
        k, n = int(gg.card_2of2.sum()), len(gg)
        if not n:
            continue
        lo, hi = wilson(k, n)
        line = (f"[{prod}] graded cards: {n}   both won: {k} ({k / n:.1%}, 95% CI {lo:.1%}-{hi:.1%})   "
                f"model expected {gg.joint_model.mean():.1%}")
        if "profit" in gg and gg.profit.notna().any():
            line += f"   ROI {gg.profit.mean():+.1%} over {int(gg.profit.notna().sum())} priced cards"
        print(line)
    print(f"Ungraded cards: {int(L.card_2of2.isna().sum())}")


if __name__ == "__main__":
    main()
