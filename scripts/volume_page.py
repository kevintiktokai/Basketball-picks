"""Data for the NCAAB volume page (reports/volume_rules.html): three betting rules from the volume
study (scripts/volume_study.py), every bet of 2011-26, replayed in money.

Rules: the current rule (P >= 55%, full stake); tiered (full stake at 55%+, half stake at 53-55%);
best 5 a day at P >= 53% (full stake). Prices: -110 for 2011-21, each side's best real opening line
and price for 2021-26 (as in the study). Money: $100 a full stake, or 2% of the balance at the start
of the night (half stake = 1%), each season from $5,000; a night never stakes more than the balance.
Each rule is also replayed with doubling (1x, 2x, 4x the bet's own stake, then reset after a win or a
third loss): after each losing bet in tip-off order, or after each losing night.

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

START, UNIT, PCT, LEVELS = 5000.0, 100.0, 0.02, 3
VARIANTS = [(st, dbl) for st in ("flat", "pct") for dbl in ("none", "bet", "night")]
ERA = {**{s: "build" for s in DEV[:7]}, **{s: "check" for s in DEV[7:]}, **{s: "test" for s in TEST}}


def rule_bets(M: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for key, pick in (("current", lambda R: R[R.p_best >= 0.55]),
                      ("tiered", lambda R: R[R.p_best >= 0.53]),
                      ("best5", lambda R: top_n(R, 5, 0.53))):
        G = pd.concat([at_opener(pick(M[M.season.isin(DEV)]), real=False),
                       at_opener(pick(M[M.season.isin(TEST)]), real=True)])
        G["mult"] = np.where(G.p_best >= 0.55, 1.0, 0.5) if key == "tiered" else 1.0
        G["tip"] = pd.to_datetime(G.tip_time, errors="coerce", utc=True)
        out[key] = G.sort_values(["day", "tip", "game_key"])
    return out


def season_paths(G: pd.DataFrame, nights: list, stake: str, dbl: str) -> tuple[list, int]:
    """Balance after every night of the season and the doubling runs that lost all three.
    stake: 'flat' ($100 a full stake) or 'pct' (2% of the balance); dbl: 'none', 'bet' or 'night'."""
    by_night = {d: g for d, g in G.groupby("day")}
    acct, lvl, base, busts, path = START, 0, UNIT, 0, [START]
    for d in nights:
        g = by_night.get(d)
        if g is not None and acct > 0:
            mult, pnl = g.mult.values, g.pnl.values
            night_bal = acct
            if dbl == "bet":
                for m, p in zip(mult, pnl):
                    if lvl == 0:
                        base = UNIT if stake == "flat" else PCT * acct
                    st = min(base * m * 2 ** lvl, max(acct, 0.0))
                    acct += st * p
                    if p != 0:
                        busts += int(p < 0 and lvl == LEVELS - 1)
                        lvl = 0 if p > 0 or lvl == LEVELS - 1 else lvl + 1
            else:
                level = 2 ** lvl if dbl == "night" else 1
                stakes = (UNIT if stake == "flat" else PCT * night_bal) * mult * level
                if stake == "pct" or dbl == "night":
                    if stakes.sum() > max(acct, 0):
                        stakes = stakes * max(acct, 0) / stakes.sum()
                net = float((stakes * pnl).sum())
                acct += net
                if dbl == "night":
                    busts += int(net < 0 and lvl == LEVELS - 1)
                    lvl = 0 if net >= 0 or lvl == LEVELS - 1 else lvl + 1
        path.append(round(max(acct, 0.0), 1))
    return path, busts


def main():
    M = frame()
    R = rule_bets(M)
    seasons = []
    all_nights = sorted(set().union(*[set(g.day) for g in R.values()]))
    cum = {k: {dbl: [] for dbl in ("none", "bet", "night")} for k in R}   # running profit ($100 base) over all seasons
    for s in DEV + TEST:
        nights = sorted(set().union(*[set(g[g.season == s].day) for g in R.values()]))
        row = {"s": s, "era": ERA[s], "nights": nights, "rules": {}}
        for k, G in R.items():
            g = G[G.season == s]
            dec = g[~g.push]
            r = {"bets": len(g), "full": int((g.mult == 1).sum()), "won": int(dec.won.sum()),
                 "lost": int((~dec.won).sum()), "units": round(float((g.mult * g.pnl).sum()), 2), "v": {}}
            for st, dbl in VARIANTS:
                path, busts = season_paths(g, nights, st, dbl)
                r["v"][f"{st}_{dbl}"] = {"end": path[-1], "low": min(path), "busts": busts, "path": path}
                if st == "flat":
                    offset = cum[k][dbl][-1] if cum[k][dbl] else 0.0
                    cum[k][dbl].extend(round(offset + v - START, 1) for v in path[1:])
            row["rules"][k] = r
        seasons.append(row)
    season_of = [s["s"] for s in seasons for _ in s["nights"]]
    nights_all = [d for s in seasons for d in s["nights"]]
    data = {"start": START, "unit": UNIT, "pct": PCT, "seasons": seasons,
            "cum": {"nights": nights_all, "season": season_of, **cum}}
    tpl = (ROOT / "scripts" / "templates" / "volume_rules.html").read_text()
    page = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    (ROOT / "reports" / "volume_rules.html").write_text(page)
    for k in R:
        for st, dbl in VARIANTS:
            t = [x["rules"][k]["v"][f"{st}_{dbl}"] for x in seasons if x["era"] == "test"]
            allv = [x["rules"][k]["v"][f"{st}_{dbl}"] for x in seasons]
            print(f"{k:8s} {st}_{dbl:6s} 2021-26 avg profit {np.mean([v['end'] - START for v in t]):10,.0f}  "
                  f"broke {sum(v['low'] <= 1 for v in allv):2d}  below start {sum(v['end'] < START for v in allv):2d}  "
                  f"lowest {min(v['low'] for v in allv):8,.0f}")
    print(len(page), "bytes")


if __name__ == "__main__":
    main()
