"""Data for the NCAAB doubling page (reports/doubling_backtest.html): every season of the
straight-bet backtest replayed under six staking plans (scripts/doubling_backtest.py), with each
plan's balance at the end of every betting night.

usage: python scripts/doubling_page.py   -> reports/doubling_backtest.html (from scripts/templates/)
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

from config_loader import ROOT
from doubling_backtest import START, ncaab_bets, run, run_nights

ERA = {**{f"{y}-{str(y + 1)[2:]}": "build" for y in range(2011, 2018)},
       **{f"{y}-{str(y + 1)[2:]}": "check" for y in range(2018, 2021)},
       **{f"{y}-{str(y + 1)[2:]}": "test" for y in range(2021, 2026)}}
BY_BET = ["flat", "mg_flat", "pct", "mg_pct"]


def main():
    B = ncaab_bets()
    seasons = []
    for season, g in B.groupby("season"):
        nights = g.night.values
        last = np.r_[np.nonzero(nights[1:] != nights[:-1])[0], len(nights) - 1]       # last bet of each night
        out = {"s": season, "era": ERA[season], "bets": len(g), "won": int((g.res == 1).sum()),
               "lost": int((g.res == -1).sum()), "nights": list(dict.fromkeys(nights)), "plans": {}}
        for p in BY_BET:
            path, staked, busts = run(g.pnl.values, p, nights)
            out["plans"][p] = {"end": round(path[-1], 2), "low": round(path.min(), 2), "staked": round(staked),
                               "busts": busts, "path": [START] + [round(v, 1) for v in path[1:][last]]}
        for p in ("mg_flat", "mg_pct"):
            path, staked, busts = run_nights(g, p)
            out["plans"][p + "_night"] = {"end": round(path[-1], 2), "low": round(path.min(), 2), "staked": round(staked),
                                          "busts": busts, "path": [round(v, 1) for v in path]}
        seasons.append(out)
    data = {"start": START, "seasons": seasons}
    tpl = (ROOT / "scripts" / "templates" / "doubling_backtest.html").read_text()
    page = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    (ROOT / "reports" / "doubling_backtest.html").write_text(page)
    print(len(page), "bytes;", sum(s["bets"] for s in seasons), "bets,", len(seasons), "seasons")


if __name__ == "__main__":
    main()
