"""A whole season in dollars at a flat stake ($50 or $100 a bet): the straight bets, the 2.5+ card,
the main-line double, and the straight bets plus the daily 2.5+ card together.

Day-level bootstrap from the 2021-26 seasons at real prices (the seasons with per-book prices).
Each simulated season takes one of those five seasons at random (its number of betting days and
its volume, which for straight bets ran from 88 to 1,380 bets) and redraws its days with
replacement, so busy Saturdays, quiet stretches and same-day overlap between the straight bets and
the card stay together. Everything is computed in units of the stake and scales exactly with it:
at $100 a bet every dollar figure is twice the $50 one.

Writes reports/season_dollars.md and reports/season_dollars.json.
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
from staking_study import bets, results

TEST = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
STAKES = (50, 100)
N_SIM, SEED = 20_000, 20261009
PLANS = {"straight": ("s",), "card": ("c",), "double": ("d",), "straight+card": ("s", "c")}


def daily_table() -> pd.DataFrame:
    B = bets()
    B = B[B.season.isin(TEST)]
    odds, res = results(B, real=True)
    B = B.assign(u=np.where(res == 1, odds - 1, np.where(res == -1, -1.0, 0.0)), day=B.date.dt.strftime("%Y-%m-%d"))
    P, cals, calm = load()
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    _, cards = evaluate(P, cals, calm, books, TEST)
    names = list(cards)
    C, Dd = cards[names[0]], cards[names[4]]                       # locked 2.5+ card, main-line double
    s = B.groupby(["season", "day"]).agg(s_u=("u", "sum"), s_n=("u", "size"))
    c = C.assign(day=C.date.astype(str)).groupby(["season", "day"]).agg(c_u=("profit", "sum"), c_n=("profit", "size"))
    d = Dd.assign(day=Dd.date.astype(str)).groupby(["season", "day"]).agg(d_u=("profit", "sum"), d_n=("profit", "size"))
    T = s.join(c, how="outer").join(d, how="outer").fillna(0).reset_index().sort_values("day")
    return T


def simulate(T: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    pools = {s: g for s, g in T.groupby("season")}
    seasons = list(pools)
    out = {p: {"total": np.empty(N_SIM), "dd": np.empty(N_SIM), "worst_day": np.empty(N_SIM),
               "bets": np.empty(N_SIM), "busiest": np.empty(N_SIM)} for p in PLANS}
    for i in range(N_SIM):
        g = pools[seasons[rng.integers(len(seasons))]]
        idx = rng.integers(0, len(g), len(g))
        for p, parts in PLANS.items():
            u = sum(g[f"{k}_u"].values[idx] for k in parts)
            n = sum(g[f"{k}_n"].values[idx] for k in parts)
            path = np.concatenate([[0.0], np.cumsum(u)])
            o = out[p]
            o["total"][i] = path[-1]
            o["dd"][i] = np.max(np.maximum.accumulate(path) - path)
            o["worst_day"][i] = u.min()
            o["bets"][i] = n.sum()
            o["busiest"][i] = n.max()
    return out


def main():
    T = daily_table()
    sim = simulate(T)
    q = lambda x, v: float(np.percentile(x, v))                    # noqa: E731
    rows, summary = [], {}
    for p, o in sim.items():
        r = {"plan": p, "bets per season (median)": q(o["bets"], 50), "bets (10th-90th)": (q(o["bets"], 10), q(o["bets"], 90)),
             "profit units: mean": float(o["total"].mean()), "median": q(o["total"], 50),
             "10th": q(o["total"], 10), "25th": q(o["total"], 25), "75th": q(o["total"], 75), "90th": q(o["total"], 90),
             "losing season": float((o["total"] < 0).mean()),
             "worst drop: median": q(o["dd"], 50), "worst drop: 1 in 10": q(o["dd"], 90), "worst drop: 1 in 20": q(o["dd"], 95),
             "worst day: median": q(o["worst_day"], 50), "busiest day bets (1 in 20)": q(o["busiest"], 95)}
        r["bankroll (1-in-20 drop + busiest day)"] = r["worst drop: 1 in 20"] + r["busiest day bets (1 in 20)"]
        rows.append(r)
        summary[p] = r
    actual = []
    for s, g in T.groupby("season"):
        actual.append({"season": s, "straight bets": int(g.s_n.sum()), "straight units": float(g.s_u.sum()),
                       "cards": int(g.c_n.sum()), "card units": float(g.c_u.sum()),
                       "doubles": int(g.d_n.sum()), "double units": float(g.d_u.sum())})
    A = pd.DataFrame(actual)
    out = {"stakes": STAKES, "plans": summary, "actual": actual,
           "hist": {p: np.histogram(o["total"], bins=40)[1].tolist() for p, o in sim.items()}}
    (ROOT / "reports" / "season_dollars.json").write_text(json.dumps(out, default=float))

    def dollars(stake):
        D = pd.DataFrame([{"plan": r["plan"], "bets": f"{r['bets per season (median)']:.0f}",
                           "typical season": f"${stake * r['median']:,.0f}",
                           "8 in 10 seasons": f"${stake * r['10th']:,.0f} to ${stake * r['90th']:,.0f}",
                           "losing season": f"{r['losing season']:.0%}",
                           "worst drop (typical / 1 in 10)": f"${stake * r['worst drop: median']:,.0f} / ${stake * r['worst drop: 1 in 10']:,.0f}",
                           "money staked": f"${stake * r['bets per season (median)']:,.0f}",
                           "bankroll to ride out a 1-in-20 stretch": f"${stake * r['bankroll (1-in-20 drop + busiest day)']:,.0f}"}
                          for r in rows])
        return df_to_md(D)
    lines = ["# A whole season at $50 and $100 a bet\n",
             "Day-level bootstrap of the 2021-26 seasons at real prices, 20,000 simulated seasons. Flat stakes; "
             "every figure scales with the stake.\n"]
    for st in STAKES:
        lines += [f"## ${st} a bet\n", dollars(st), ""]
    lines += ["## The five 2021-26 seasons as they happened (units; multiply by the stake)\n", df_to_md(A, "{:.1f}")]
    (ROOT / "reports" / "season_dollars.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("season_dollars", {"n_sim": N_SIM, "seed": SEED, "stakes": STAKES},
                   {"plans": {p: {k: v for k, v in r.items() if k != "plan"} for p, r in summary.items()}})


if __name__ == "__main__":
    main()
