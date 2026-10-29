"""Straight bets replayed under flat, 2% and doubling (martingale) staking.

NCAAB: every straight bet of the game-totals backtest 2011-26 (reports/singles_extrapolation.md),
each season from $5,000. Europe: the development backtest's bets (reports/euro_dev_q1q2.md, "when
Pinnacle opens, EV > 2%") plus the graded live picks. Plans, from a $5,000 account:
flat $100; 2% of the balance; doubling $100/$200/$400 (double after a loss, at most twice, reset
after a win or a third loss); doubling on 2% of the balance at the start of each cycle. Doubling is
replayed bet by bet (results assumed known in tip-off order) and night by night (every bet of a
night at one level, doubling after a losing night), and the bet-by-bet version over shuffled orders.

A night's bets never stake more than the balance.

usage: python scripts/doubling_backtest.py   -> reports/doubling_backtest.md
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import euro_dev_study as D
from backtest.analysis import df_to_md
from config_loader import ROOT
from features.euro_market import close_board, fair_curve, timelines

START, BASE, PCT, LEVELS, EV_MIN = 5000.0, 100.0, 0.02, 3, 0.02
PLANS = {"flat": "Flat $100", "pct": "2% of account", "mg_flat": "Doubling $100-$400", "mg_pct": "Doubling 2%-8%"}


def bets() -> pd.DataFrame:
    T = timelines()
    T = T[(T.start >= D.DEV_FROM) & (T.start < D.DEV_TO)].drop_duplicates(["fixture_id", "book", "line", "side", "t"])
    final, _ = D.results(T)
    CC = fair_curve(close_board(T))
    first_pin = T[T.book == "pinnacle"].groupby("fixture_id").t.min()
    S = D.legs_at(T, first_pin, CC, final)
    B = S[S.ev_now > EV_MIN].sort_values("ev_now").groupby("fixture_id").tail(1)
    info = T.groupby("fixture_id")[["start", "home_name", "away_name"]].first().rename(columns={"start": "tip"})
    B = B.drop(columns=[c for c in ("home_name", "away_name", "start") if c in B]).join(info, on="fixture_id")
    B["placed"] = B.fixture_id.map(first_pin)
    L = pd.read_csv(ROOT / "reports" / "live_ledger_euro_graded.csv", parse_dates=["start"])
    L = L[(L.kind == "single") & L.result.isin(["won", "lost"])]
    live = pd.DataFrame({"tip": L.start, "placed": L.start, "home_name": L.game_key, "away_name": "", "book": L.book,
                         "side": L.side, "line": L.line, "price": L.price, "win": L.result == "won",
                         "pnl": np.where(L.result == "won", L.price - 1, -1.0), "clv": L.clv})
    return pd.concat([B, live], ignore_index=True).sort_values("tip").reset_index(drop=True)


def ncaab_bets() -> pd.DataFrame:
    from singles_extrapolation import ERA
    from staking_study import bets as nc_bets, results
    B = nc_bets()
    B = B[B.season.isin(ERA)].copy()
    real = B.season >= "2021-22"
    o110, r110 = results(B, real=False)
    orl, rrl = results(B, real=True)
    B["odds"], B["res"] = np.where(real, orl, o110), np.where(real, rrl, r110)
    B["pnl"] = np.where(B.res == 1, B.odds - 1, np.where(B.res == -1, -1.0, 0.0))
    B["tip"] = pd.to_datetime(B.tip_time, errors="coerce", utc=True)
    B["night"] = B.date.dt.strftime("%Y-%m-%d")
    return B.sort_values(["date", "tip", "game_key"]).reset_index(drop=True)


def run(pnl: np.ndarray, plan: str, nights: np.ndarray | None = None):
    acct, lvl, base, path, staked, busts = START, 0, BASE, [START], 0.0, 0
    nights = np.arange(len(pnl)) if nights is None else nights
    size = pd.Series(nights).map(pd.Series(nights).value_counts()).values
    cur, night_bal = None, START
    for p, n, k in zip(pnl, nights, size):
        if n != cur:
            cur, night_bal = n, acct
        if plan == "flat":
            stake = BASE
        elif plan == "pct":
            stake = min(PCT, 1.0 / k) * night_bal                 # a night never stakes more than the balance
        else:
            if lvl == 0:
                base = BASE if plan == "mg_flat" else PCT * acct
            stake = base * 2 ** lvl
        stake = min(stake, max(acct, 0.0))
        acct += stake * p
        staked += stake
        path.append(acct)
        if plan.startswith("mg") and p != 0:
            busts += int(p < 0 and lvl == LEVELS - 1)
            lvl = 0 if p > 0 or lvl == LEVELS - 1 else lvl + 1
    return np.array(path), staked, busts


def run_nights(B: pd.DataFrame, plan: str):
    acct, lvl, path, staked, busts = START, 0, [START], 0.0, 0
    for _, g in B.groupby(B.tip.dt.strftime("%Y-%m-%d") if "night" not in B else B.night, sort=False):
        stake = (BASE if plan == "mg_flat" else PCT * acct) * 2 ** lvl
        stake = min(stake, max(acct, 0.0) / len(g))
        net = float((stake * g.pnl).sum())
        staked += stake * len(g)
        acct += net
        path.append(acct)
        busts += int(net < 0 and lvl == LEVELS - 1)
        lvl = 0 if net >= 0 or lvl == LEVELS - 1 else lvl + 1
    return np.array(path), staked, busts


def stats(label, how, path, staked, busts):
    return {"staking": label, "doubles after": how, "ending balance": path[-1], "profit": path[-1] - START,
            "lowest": path.min(), "biggest drop": (np.maximum.accumulate(path) - path).max(), "staked": staked,
            "return per $ staked": (path[-1] - START) / staked, "lost all three": busts}


def ncaab_section() -> list[str]:
    B = ncaab_bets()
    rows = []
    for season, g in B.groupby("season"):
        for p in PLANS:
            path, staked, busts = run(g.pnl.values, p, g.night.values)
            rows.append({"season": season, "plan": f"{PLANS[p]}, each losing bet" if p.startswith("mg") else PLANS[p],
                         "bets": len(g), **{k: v for k, v in stats("", "", path, staked, busts).items() if k not in ("staking", "doubles after")}})
        for p in ("mg_flat", "mg_pct"):
            path, staked, busts = run_nights(g, p)
            rows.append({"season": season, "plan": f"{PLANS[p]}, each losing night", "bets": len(g),
                         **{k: v for k, v in stats("", "", path, staked, busts).items() if k not in ("staking", "doubles after")}})
    R = pd.DataFrame(rows)
    order = list(dict.fromkeys(R.plan))
    end = R.pivot(index="season", columns="plan", values="ending balance")[order].reset_index()
    low = R.pivot(index="season", columns="plan", values="lowest")[order].reset_index()
    over = R.groupby("plan", sort=False).agg(**{"seasons below start": ("ending balance", lambda x: int((x < START - 0.005).sum())),
                                                "seasons broke": ("lowest", lambda x: int((x <= 1).sum())),
                                                "lowest balance": ("lowest", "min"),
                                                "staked per season": ("staked", "mean")}).reset_index()
    return [f"## NCAAB game totals, {len(B):,} straight bets over {B.season.nunique()} seasons\n",
            f"Each season starts from ${START:,.0f}. Standard -110 prices before 2021-22, best real book price after.\n",
            df_to_md(over, "{:,.1f}"), "", "Ending balance by season:\n", df_to_md(end, "{:,.0f}"), "",
            "Lowest balance during each season:\n", df_to_md(low, "{:,.0f}"), ""]


def main():
    B = bets()
    P = B.pnl.values
    rows = [stats(PLANS[p], "each losing bet" if p.startswith("mg") else "never", *run(P, p)) for p in PLANS]
    rows += [stats(PLANS[p], "each losing night", *run_nights(B, p)) for p in ("mg_flat", "mg_pct")]
    rng = np.random.default_rng(1)
    ends = {p: [] for p in PLANS}
    for _ in range(10000):
        o = rng.permutation(len(P))
        for p in PLANS:
            ends[p].append(run(P[o], p)[0][-1])
    sh = pd.DataFrame([{"staking": PLANS[p], "typical": np.median(e), "10th pct": np.percentile(e, 10),
                        "90th pct": np.percentile(e, 90), "worst": np.min(e), "best": np.max(e),
                        "below start": np.mean(np.array(e) < START - 0.005)} for p, e in ends.items()])
    prev_end = B.tip.shift(1) + pd.Timedelta(hours=2)
    overlap = int((B.placed < prev_end).sum())
    lines = ["# Straight bets with doubling after a loss\n", *ncaab_section(),
             "## European game totals\n",
             f"{len(B)} bets (backtest and live) ({int(B.win.sum())} won, average price {B.price.mean():.2f}, "
             f"{B.pnl.mean():+.1%} per bet, {B.clv.mean():+.1%} against Pinnacle's close), from a ${START:,.0f} account. "
             f"{overlap} of the {len(B) - 1} later bets were placed before the previous game had finished, so "
             "bet-by-bet doubling could not be followed as replayed; night by night could.\n",
             df_to_md(pd.DataFrame(rows), "{:,.3f}"), "",
             "The same bets in 10,000 shuffled orders (ending balance):\n", df_to_md(sh, "{:,.3f}"), "",
             "Doubling raises the money staked and the swings; it does not change the return per bet."]
    (ROOT / "reports" / "doubling_backtest.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
