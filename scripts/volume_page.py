"""Data for the NCAAB volume page (reports/volume_rules.html): three betting rules from the volume
study (scripts/volume_study.py), every bet of 2011-26, replayed in money.

Rules: the current rule (P >= 55%, full stake); tiered (full stake at 55%+, half stake at 53-55%);
best 5 a day at P >= 53% (full stake). Prices: -110 for 2011-21, each side's best real opening line
and price for 2021-26 (as in the study). Money: $100 a full stake, or 2% of the balance at the start
of the night (half stake = 1%), each season from $5,000; a night never stakes more than the balance.

usage: python scripts/volume_page.py   -> reports/volume_rules.html (from scripts/templates/)
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

from config_loader import ROOT
from volume_study import DEV, TEST, at_opener, frame, top_n

START, UNIT, PCT = 5000.0, 100.0, 0.02
ERA = {**{s: "build" for s in DEV[:7]}, **{s: "check" for s in DEV[7:]}, **{s: "test" for s in TEST}}


def rule_bets(M: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for key, pick in (("current", lambda R: R[R.p_best >= 0.55]),
                      ("tiered", lambda R: R[R.p_best >= 0.53]),
                      ("best5", lambda R: top_n(R, 5, 0.53))):
        G = pd.concat([at_opener(pick(M[M.season.isin(DEV)]), real=False),
                       at_opener(pick(M[M.season.isin(TEST)]), real=True)])
        G["mult"] = np.where(G.p_best >= 0.55, 1.0, 0.5) if key == "tiered" else 1.0
        out[key] = G.sort_values(["day", "game_key"])
    return out


def season_paths(G: pd.DataFrame, nights: list) -> dict:
    """Balance after every night of the season: flat $100 a unit, and 2% of the night's opening balance."""
    by_night = {d: g for d, g in G.groupby("day")}
    flat, pct, f, p = [START], [START], START, START
    for d in nights:
        g = by_night.get(d)
        if g is not None:
            f += float((UNIT * g.mult * g.pnl).sum())
            stakes = PCT * g.mult.values * p
            if stakes.sum() > max(p, 0):
                stakes *= max(p, 0) / stakes.sum()
            p += float((stakes * g.pnl.values).sum())
        flat.append(round(f, 1))
        pct.append(round(p, 1))
    return {"flat": flat, "pct": pct}


def main():
    M = frame()
    R = rule_bets(M)
    seasons = []
    cum = {k: [] for k in R}                       # running profit in units across all seasons, by night
    run = {k: 0.0 for k in R}
    all_nights = sorted(set().union(*[set(g.day) for g in R.values()]))
    for k, G in R.items():
        u = G.groupby("day").apply(lambda g: float((g.mult * g.pnl).sum()))
        for d in all_nights:
            run[k] += u.get(d, 0.0)
            cum[k].append(round(run[k], 2))
    for s in DEV + TEST:
        nights = sorted(set().union(*[set(g[g.season == s].day) for g in R.values()]))
        row = {"s": s, "era": ERA[s], "nights": nights, "rules": {}}
        for k, G in R.items():
            g = G[G.season == s]
            dec = g[~g.push]
            paths = season_paths(g, nights)
            row["rules"][k] = {"bets": len(g), "full": int((g.mult == 1).sum()), "won": int(dec.won.sum()),
                               "lost": int((~dec.won).sum()), "units": round(float((g.mult * g.pnl).sum()), 2),
                               "staked_units": round(float(g.mult.sum()), 1),
                               "flat_end": paths["flat"][-1], "flat_low": min(paths["flat"]),
                               "pct_end": paths["pct"][-1], "pct_low": min(paths["pct"]),
                               "path_flat": paths["flat"], "path_pct": paths["pct"]}
        seasons.append(row)
    season_of = M.drop_duplicates("day").set_index("day").season
    data = {"start": START, "unit": UNIT, "pct": PCT, "seasons": seasons,
            "cum": {"nights": all_nights, "season": [season_of.get(d) for d in all_nights], **cum}}
    tpl = (ROOT / "scripts" / "templates" / "volume_rules.html").read_text()
    page = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    (ROOT / "reports" / "volume_rules.html").write_text(page)
    for k, G in R.items():
        t = G[G.season.isin(TEST)]
        print(k, len(G), "bets;", "2021-26 units a season", round(float((t.mult * t.pnl).sum()) / 5, 1))
    print(len(page), "bytes")


if __name__ == "__main__":
    main()
