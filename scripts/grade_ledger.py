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


def main():
    if not LEDGER.exists():
        sys.exit("no ledger yet: run predict_cards.py with --record")
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
    L.to_csv(LEDGER, index=False)
    g = L[L.card_2of2.notna()]
    k, n = int(g.card_2of2.sum()), len(g)
    if n:
        lo, hi = wilson(k, n)
        print(f"Graded cards: {n}   2/2: {k} ({k / n:.1%}, 95% CI {lo:.1%}-{hi:.1%})   "
              f"model expected {g.joint_model.mean():.1%}")
    print(f"Ungraded cards: {int(L.card_2of2.isna().sum())}")


if __name__ == "__main__":
    main()
