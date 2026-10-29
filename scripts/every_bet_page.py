"""Every NCAAB straight bet of 2011-26 under the three volume rules (reports/every_bet.html), and the
same ledger as CSV (reports/every_bet_2011_26.csv).

One row per game the engine rated 53%+ at the opener (the tiered rule's bets, which contain the other
two rules' bets), with the pick, line and price graded (-110 at the consensus opener for 2011-21; each
side's best real opening line and price for 2021-26), and for each rule (current 55%+, tiered,
best 5 a day) and doubling mode (off, after each losing bet, after each losing night) the stake at
$100 a full stake and the balance after the bet, each season from $5,000 (as scripts/volume_page.py).

usage: python scripts/every_bet_page.py
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
from config_loader import ROOT
from volume_page import ERA, LEVELS, START, UNIT
from volume_study import DEV, TEST, ODDS_110, frame, top_n

RULES = ("current", "tiered", "best5")
BOOK_NAME = {"betmgm": "BetMGM", "bet_rivers_co": "BetRivers", "draftkings": "DraftKings", "bet365": "bet365",
             "fanduel": "FanDuel", "caesars": "Caesars", "fanatics": "Fanatics", "hardrock": "Hard Rock"}
DBL = ("none", "bet", "night")


def ledger(M: pd.DataFrame) -> pd.DataFrame:
    """All 53%+ picks, graded the way the study grades them, with each rule's membership and stake size."""
    B = M[M.p_best >= 0.53].copy()
    side = B.best_side.values
    real = B.season.isin(TEST).values
    rl = np.where(side == 1, B.line_over, B.line_under)
    ro = np.where(side == 1, B.odds_over, B.odds_under)
    ok = real & ~np.isnan(rl) & ~np.isnan(ro)
    B["bet_line"] = np.where(ok, rl, B.line)
    B["price"] = np.where(ok, ro, ODDS_110)
    B["book"] = [BOOK_NAME.get(best_main(bj, s)[2], best_main(bj, s)[2]) if o else ""
                 for bj, s, o in zip(B.books_json, side, ok)]
    win = np.where(side == 1, B.outcome > B.bet_line, B.outcome < B.bet_line)
    push = B.outcome.values == B.bet_line.values
    B["result"] = np.where(push, "push", np.where(win, "won", "lost"))
    B["pnl"] = np.where(push, 0.0, np.where(win, B.price - 1, -1.0))
    B["in_current"] = B.p_best >= 0.55
    B["in_tiered"] = True
    best = top_n(M, 5, 0.53)
    B["in_best5"] = B.index.isin(best.index)
    B["mult_tiered"] = np.where(B.p_best >= 0.55, 1.0, 0.5)
    B["tip"] = pd.to_datetime(B.tip_time, errors="coerce", utc=True)
    return B.sort_values(["day", "tip", "game_key"]).reset_index(drop=True)


def replay(g: pd.DataFrame, mult: np.ndarray, dbl: str) -> tuple[np.ndarray, np.ndarray]:
    """Stake and balance after each bet of one season at $100 a full stake (same rules as volume_page)."""
    stake, bal = np.zeros(len(g)), np.zeros(len(g))
    acct, lvl = START, 0
    pnl, day = g.pnl.values, g.day.values
    i = 0
    while i < len(g):
        j = i
        while j < len(g) and day[j] == day[i]:
            j += 1
        if dbl == "bet":
            for k in range(i, j):
                st = min(UNIT * mult[k] * 2 ** lvl, max(acct, 0.0))
                acct += st * pnl[k]
                stake[k], bal[k] = st, acct
                if pnl[k] != 0:
                    lvl = 0 if pnl[k] > 0 or lvl == LEVELS - 1 else lvl + 1
        else:
            level = 2 ** lvl if dbl == "night" else 1
            st = UNIT * mult[i:j] * level
            if dbl == "night" and st.sum() > max(acct, 0):
                st = st * max(acct, 0) / st.sum()
            if acct <= 0:
                st = st * 0
            net = 0.0
            for k in range(i, j):
                net += st[k - i] * pnl[k]
                stake[k], bal[k] = st[k - i], acct + net
            acct += net
            if dbl == "night":
                lvl = 0 if net >= 0 or lvl == LEVELS - 1 else lvl + 1
        i = j
    return stake, bal


def main():
    M = frame()
    B = ledger(M)
    cols = {}
    for rule in RULES:
        member = B[f"in_{rule}"].values
        mult = B.mult_tiered.values if rule == "tiered" else np.ones(len(B))
        for dbl in DBL:
            st_all, bal_all = np.full(len(B), np.nan), np.full(len(B), np.nan)
            for s in DEV + TEST:
                idx = np.nonzero(member & (B.season.values == s))[0]
                if len(idx):
                    st, bal = replay(B.iloc[idx], mult[idx], dbl)
                    st_all[idx], bal_all[idx] = st, bal
            cols[f"{rule}_{dbl}"] = (st_all, bal_all)

    # check against the page that shows the season totals
    vp = json.loads((lambda t: t[t.index('id="data">') + 10:t.index("</script>", t.index('id="data">'))])(
        (ROOT / "reports" / "volume_rules.html").read_text()))
    worst = 0.0
    for srow in vp["seasons"]:
        for rule in RULES:
            for dbl in DBL:
                bal = cols[f"{rule}_{dbl}"][1][(B.season.values == srow["s"]) & B[f"in_{rule}"].values]
                end = bal[-1] if len(bal) else START
                worst = max(worst, abs(max(end, 0) - srow["rules"][rule]["v"][f"flat_{dbl}"]["end"]))
    print(f"largest season-end difference against the volume page: ${worst:.2f}")

    out = pd.DataFrame({"season": B.season, "date": B.day, "away": B.away_name, "home": B.home_name,
                        "pick": np.where(B.best_side == 1, "Over", "Under"), "line": B.bet_line, "opener": B.line,
                        "price": B.price.round(3), "book": B.book, "engine_p": B.p_best.round(4),
                        "final_total": B.outcome, "result": B.result,
                        "in_current": B.in_current, "in_best5": B.in_best5, "tiered_stake": B.mult_tiered})
    for k, (st, bal) in cols.items():
        out[f"stake_{k}"], out[f"balance_{k}"] = np.round(st, 2), np.round(bal, 2)
    out.to_csv(ROOT / "reports" / "every_bet_2011_26.csv", index=False)

    # compact page data: one array per column; stakes/balances as integers, missing = null
    def arr(x, nd=0):
        return [None if (isinstance(v, float) and np.isnan(v)) else (round(float(v), nd) if nd else int(round(v)))
                for v in x]
    seasons = DEV + TEST
    books = sorted({b for b in B.book if b})
    teams = sorted(set(B.away_name) | set(B.home_name))
    tix = {t: i for i, t in enumerate(teams)}
    data = {"start": START, "unit": UNIT, "seasons": seasons, "era": {s: ERA[s] for s in seasons},
            "teams": teams, "books": books,
            "s": [seasons.index(s) for s in B.season], "d": list(B.day),
            "a": [tix[t] for t in B.away_name], "h": [tix[t] for t in B.home_name],
            "o": [int(v == 1) for v in B.best_side], "l": arr(B.bet_line, 1), "op": arr(B.line, 1),
            "pr": arr(B.price, 3), "bk": [books.index(b) + 1 if b else 0 for b in B.book],
            "p": arr(B.p_best * 1000), "f": arr(B.outcome), "r": ["wlp".index(r[0]) for r in B.result],
            "cur": [int(x) for x in B.in_current], "b5": [int(x) for x in B.in_best5],
            "x": {k: {"st": arr(v[0]), "bal": arr(v[1])} for k, v in cols.items()}}
    tpl = (ROOT / "scripts" / "templates" / "every_bet.html").read_text()
    page = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    (ROOT / "reports" / "every_bet.html").write_text(page)
    print(len(B), "bets;", f"{len(page) / 1e6:.1f} MB page;", "current", int(B.in_current.sum()), "best 5", int(B.in_best5.sum()))


if __name__ == "__main__":
    main()
