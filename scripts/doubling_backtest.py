"""European straight bets (the development backtest) replayed under four staking plans.

Bets: reports/euro_dev_q1q2.md, "when Pinnacle opens, EV > 2%": the best soft-book total per game at
least 2% above Pinnacle's fair price when Pinnacle opened. Plans, from a $5,000 account:
flat $100; 2% of the balance; doubling $100/$200/$400 (double after a loss, at most twice, reset
after a win or a third loss); doubling on 2% of the balance at the start of each cycle. Doubling is
replayed bet by bet (results assumed known in tip-off order) and night by night (every bet of a
night at one level, doubling after a losing night), and the bet-by-bet version over shuffled orders.

usage: python scripts/euro_staking_backtest.py   -> reports/euro_staking_backtest.md
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
    return B.sort_values("tip").reset_index(drop=True)


def run(pnl: np.ndarray, plan: str):
    acct, lvl, base, path, staked, busts = START, 0, BASE, [START], 0.0, 0
    for p in pnl:
        if plan == "flat":
            stake = BASE
        elif plan == "pct":
            stake = PCT * acct
        else:
            if lvl == 0:
                base = BASE if plan == "mg_flat" else PCT * acct
            stake = base * 2 ** lvl
        stake = min(stake, max(acct, 0.0))
        acct += stake * p
        staked += stake
        path.append(acct)
        if plan.startswith("mg"):
            busts += int(p < 0 and lvl == LEVELS - 1)
            lvl = 0 if p > 0 or lvl == LEVELS - 1 else lvl + 1
    return np.array(path), staked, busts


def run_nights(B: pd.DataFrame, plan: str):
    acct, lvl, path, staked, busts = START, 0, [START], 0.0, 0
    for _, g in B.groupby(B.tip.dt.strftime("%Y-%m-%d")):
        stake = (BASE if plan == "mg_flat" else PCT * acct) * 2 ** lvl
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
    lines = ["# European straight bets under four staking plans\n",
             f"{len(B)} backtest bets ({int(B.win.sum())} won, average price {B.price.mean():.2f}, "
             f"{B.pnl.mean():+.1%} per bet, {B.clv.mean():+.1%} against Pinnacle's close), from a ${START:,.0f} account. "
             f"{overlap} of the {len(B) - 1} later bets were placed before the previous game had finished, so "
             "bet-by-bet doubling could not be followed as replayed; night by night could.\n",
             df_to_md(pd.DataFrame(rows), "{:,.3f}"), "",
             "The same bets in 10,000 shuffled orders (ending balance):\n", df_to_md(sh, "{:,.3f}"), "",
             "Doubling raises the money staked and the swings; it does not change the return per bet."]
    (ROOT / "reports" / "euro_staking_backtest.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
