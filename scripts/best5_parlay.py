"""Best 5 a day plus the daily 2.5+ parlay, NCAAB 2011-26 (reports/best5_parlay.html and .md).

Straight bets: each day's five most probable picks of the locked v3 engine at P >= 53% (the volume
study's rule), graded at -110 on the consensus opener for 2011-21 and at each side's best real opening
line and price for 2021-26. Parlay: the locked 2.5+ card (scripts/stage3_common.evaluate, the TARGET
product), at most one a day and only on days the engine finds one; its legs are often moved lines
priced by our estimate of the book, as in reports/ledger_2023_24.*.
Money: each season from $5,000; $100 a straight bet and $100 a parlay, or 2% of the balance at the
start of the night for each (a night never stakes more than the balance). Doubling (optional): 1x, 2x,
4x the base stake after a loss, reset after a win or a third loss; straight bets and the parlay share
one sequence (in tip-off order; the parlay settles with its later leg). "bet": after each losing bet;
"night": every bet of the next night after a night that lost money overall.

usage: python scripts/best5_parlay.py
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
from every_bet_page import BOOK_NAME
from backtest.odds_cards import best_main
from volume_study import DEV, TEST, ODDS_110, frame, top_n

START, UNIT, PCT, LEVELS = 5000.0, 100.0, 0.02, 3
DBL = ("none", "bet", "night")
ERA = {**{s: "build" for s in DEV[:7]}, **{s: "check" for s in DEV[7:]}, **{s: "test" for s in TEST}}
PLANS = ("combo", "straight", "parlay")


def straights(M: pd.DataFrame) -> pd.DataFrame:
    B = top_n(M, 5, 0.53).copy()
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
    B["tip"] = pd.to_datetime(B.tip_time, errors="coerce", utc=True)
    return B


def parlays(P, cals, calm) -> pd.DataFrame:
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    _, C = evaluate(P, cals, calm, books, DEV + TEST)
    c = C[[k for k in C if k.startswith("TARGET")][0]].copy()
    c["day"] = pd.to_datetime(c.date).dt.strftime("%Y-%m-%d")
    g = P.drop_duplicates("game_key").set_index("game_key")
    for leg in ("a", "b"):
        c[f"away_{leg}"] = c[f"game_{leg}"].map(g.away_name)
        c[f"home_{leg}"] = c[f"game_{leg}"].map(g.home_name)
        c[f"final_{leg}"] = c[f"game_{leg}"].map(g.outcome)
        c[f"tip_{leg}"] = pd.to_datetime(c[f"game_{leg}"].map(g.tip_time), errors="coerce", utc=True)
    c["result"] = np.where(c.profit > 0, "won", np.where(c.profit < 0, "lost", "push"))
    c["pnl"] = c.profit
    return c


def replay(rows: pd.DataFrame, nights: list, stake: str, dbl: str = "none"):
    """Night-end balances, and each bet's stake, balance after it and doubling level (bets of a night
    placed together; with doubling after each losing bet, in tip-off order)."""
    acct, lvl, base, path = START, 0, UNIT, [START]
    st_out, bal_out, lv_out = np.zeros(len(rows)), np.zeros(len(rows)), np.zeros(len(rows), int)
    pnl = rows.pnl.values
    by = {d: np.nonzero(rows.day.values == d)[0] for d in nights}
    for d in nights:
        idx = by[d]
        if len(idx) and acct > 0:
            if dbl == "bet":
                for i in idx:
                    if lvl == 0:
                        base = UNIT if stake == "flat" else PCT * acct
                    st = min(base * 2 ** lvl, max(acct, 0.0))
                    acct += st * pnl[i]
                    st_out[i], bal_out[i], lv_out[i] = st, acct, lvl
                    if pnl[i] != 0:
                        lvl = 0 if pnl[i] > 0 or lvl == LEVELS - 1 else lvl + 1
            else:
                level = 2 ** lvl if dbl == "night" else 1
                st = np.full(len(idx), (UNIT if stake == "flat" else PCT * acct) * level)
                if st.sum() > max(acct, 0):
                    st *= max(acct, 0) / st.sum()
                run = acct
                for k, i in enumerate(idx):
                    run += st[k] * pnl[i]
                    st_out[i], bal_out[i], lv_out[i] = st[k], run, lvl if dbl == "night" else 0
                net = run - acct
                acct = run
                if dbl == "night":
                    lvl = 0 if net >= 0 or lvl == LEVELS - 1 else lvl + 1
        elif len(idx):
            for i in idx:
                bal_out[i] = max(acct, 0.0)
        path.append(round(max(acct, 0.0), 1))
    return path, st_out, bal_out, lv_out


def main():
    M = frame()
    P, cals, calm = load()
    S = straights(M)
    C = parlays(P, cals, calm)
    rows = pd.concat([
        pd.DataFrame({"kind": "straight", "season": S.season, "day": S.day, "tip": S.tip, "pnl": S.pnl, "result": S.result,
                      "ref": S.index, "gk": S.game_key}),
        pd.DataFrame({"kind": "parlay", "season": C.season, "day": C.day, "tip": C[["tip_a", "tip_b"]].max(axis=1),
                      "pnl": C.pnl, "result": C.result, "ref": C.index, "gk": "~"})], ignore_index=True)
    # tip-off order; games tipping together in game order (as scripts/volume_page.py), a parlay after them
    rows = rows.sort_values(["day", "tip", "gk"]).reset_index(drop=True)

    seasons, stakes = [], {}
    for s in DEV + TEST:
        R = rows[rows.season == s]
        nights = sorted(R.day.unique())
        row = {"s": s, "era": ERA[s], "nights": nights, "plans": {}}
        for plan in PLANS:
            sub = R if plan == "combo" else R[R.kind == ("straight" if plan == "straight" else "parlay")]
            dec = sub[sub.result != "push"]
            row["plans"][plan] = {"bets": len(sub), "won": int((dec.result == "won").sum()),
                                  "lost": int((dec.result == "lost").sum()), "units": round(float(sub.pnl.sum()), 2)}
            for mode in ("flat", "pct"):
                for dbl in DBL:
                    path, st, bal, lv = replay(sub, nights, mode, dbl)
                    low = min(path + [float(b) for b in bal[st > 0]]) if (st > 0).any() else min(path)
                    row["plans"][plan][f"{mode}_{dbl}"] = {"end": path[-1], "low": round(max(low, 0.0), 1), "path": path}
                    if plan == "combo":
                        stakes.setdefault(f"{mode}_{dbl}", {}).update(
                            {i: (int(round(a)), int(round(max(b, 0))), int(l)) for i, a, b, l in zip(sub.index, st, bal, lv)})
        cs = C[C.season == s]
        row["parlay_odds"] = round(float(cs.combined_odds.mean()), 3) if len(cs) else None
        seasons.append(row)

    # running profit across all seasons at $100 a base bet (no compounding; each season from $5,000)
    all_nights = [d for x in seasons for d in x["nights"]]
    cum = {p: {dbl: [] for dbl in DBL} for p in PLANS}
    for p in PLANS:
        for dbl in DBL:
            off = 0.0
            for x in seasons:
                path = x["plans"][p][f"flat_{dbl}"]["path"]
                cum[p][dbl].extend(round(off + v - START, 1) for v in path[1:])
                off += path[-1] - START

    # the ledger: every straight bet and every parlay, in order
    teams = sorted(set(S.away_name) | set(S.home_name) | set(C.away_a.dropna()) | set(C.home_a.dropna())
                   | set(C.away_b.dropna()) | set(C.home_b.dropna()))
    tix = {t: i for i, t in enumerate(teams)}
    books = sorted({b for b in S.book if b})
    L = []
    variants = [f"{m}_{d}" for m in ("flat", "pct") for d in DBL]
    lst = {v: [] for v in variants}
    for i, r in rows.iterrows():
        for v in variants:
            lst[v].append(stakes[v][i])
        base = [r.day, "wlp".index(r.result[0]), round(float(r.pnl), 4)]
        if r.kind == "straight":
            b = S.loc[r.ref]
            L.append(["s", *base, tix[b.away_name], tix[b.home_name], int(b.best_side == 1), round(float(b.bet_line), 1),
                      round(float(b.line), 1), round(float(b.price), 3), books.index(b.book) + 1 if b.book else 0,
                      int(round(b.p_best * 1000)), int(b.outcome)])
        else:
            c = C.loc[r.ref]
            legs = []
            for leg in ("a", "b"):
                legs.append([tix.get(c[f"away_{leg}"], -1), tix.get(c[f"home_{leg}"], -1), int(c[f"side_{leg}"] == 1),
                             round(float(c[f"thr_{leg}"]), 1), round(float(c[f"odds_{leg}"]), 3),
                             int(round(c[f"p_{leg}"] * 1000)),
                             None if pd.isna(c[f"final_{leg}"]) else int(c[f"final_{leg}"]),
                             "wlp"[0 if c[f"win_{leg}"] and not c[f"push_{leg}"] else 2 if c[f"push_{leg}"] else 1]])
            L.append(["p", *base, round(float(c.combined_odds), 3), int(round(c.joint_model * 1000)), legs])

    data = {"start": START, "unit": UNIT, "seasons": seasons, "teams": teams, "books": books,
            "cum": {"nights": all_nights, "season": [x["s"] for x in seasons for _ in x["nights"]], **cum}, "ledger": L,
            "lst": lst}
    tpl = (ROOT / "scripts" / "templates" / "best5_parlay.html").read_text()
    page = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    (ROOT / "reports" / "best5_parlay.html").write_text(page)

    # markdown summary
    def era_sum(plan, ss, dbl):
        r = [x["plans"][plan] for x in seasons if x["s"] in ss]
        v = [x[f"flat_{dbl}"] for x in r]
        return {"bets a season": np.mean([x["bets"] for x in r]),
                "won": sum(x["won"] for x in r) / max(1, sum(x["won"] + x["lost"] for x in r)),
                "$ a season ($100 base)": np.mean([x["end"] - START for x in v]),
                "worst season ($)": min(x["end"] - START for x in v),
                "lowest balance ($)": min(x["low"] for x in v),
                "seasons broke": sum(x["low"] <= 1 for x in v)}
    T = pd.DataFrame([{"plan": p, "doubling": dbl, "seasons": lab, **era_sum(p, ss, dbl)} for p in PLANS for dbl in DBL
                      for lab, ss in (("2011-21", DEV), ("2021-26", TEST))])
    per = pd.DataFrame([{"season": x["s"], **{f"{p} $": x["plans"][p]["flat_none"]["end"] - START for p in PLANS},
                         "parlays": x["plans"]["parlay"]["bets"], "parlays won": x["plans"]["parlay"]["won"],
                         "avg parlay odds": x["parlay_odds"]} for x in seasons])
    md = ["# Best 5 a day plus the daily 2.5+ parlay\n",
          "combo = best 5 straight bets a day (P >= 53%) plus the parlay on days it exists; each season from $5,000 at $100 a "
          "base bet. Doubling: none, after each losing bet, or after each losing night (1x, 2x, 4x; shared by straight bets and parlay).\n",
          df_to_md(T, "{:,.3f}"), "", "By season ($ profit at $100 a bet):\n", df_to_md(per, "{:,.2f}"), ""]
    (ROOT / "reports" / "best5_parlay.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(len(L), "ledger rows;", f"{len(page) / 1e6:.1f} MB page")
    log_experiment("best5_parlay", {"straights": "best 5 a day, P >= 53%", "parlay": "TARGET 2.5+ card"},
                   {"summary": T.to_dict("records")})


if __name__ == "__main__":
    main()
