"""A season from a $10,000 account, staking a fixed share of the account on every bet: 1% and 2%.

Every bet of a day is sized from that morning's balance (bets go in before the games are played), so
the stake grows after winning days and shrinks after losing ones. A day's stakes can never exceed the
whole balance: on a slate with more picks than that allows, each bet is scaled down to fit (this only
happens at 2%, on days with more than 50 straight bets).

Same day-level bootstrap as reports/season_dollars.md: 20,000 seasons, each replaying one of the five
2021-26 seasons at real prices (its volume) with its days redrawn at random. The actual 2021-26
seasons are also replayed day by day in their real order.

Compounding runs into betting limits long before the bigger figures here. Every run is therefore also
done with a $500 cap per bet, an illustrative limit for college totals at a single book.
Writes reports/season_percent.md and reports/season_percent.json.
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
from season_dollars import PLANS, daily_table

START = 10_000.0
FRACS = (0.01, 0.02)
N_SIM, SEED = 20_000, 20261010
CHECKPOINTS = 21                      # balance recorded at every 5% of the season's days


def day_parts(g: pd.DataFrame, parts) -> tuple[np.ndarray, np.ndarray]:
    return sum(g[f"{k}_u"].values for k in parts), sum(g[f"{k}_n"].values for k in parts)


def run_days(u: np.ndarray, n: np.ndarray, f: float, cap: float | None = None) -> np.ndarray:
    """Balance path over days: each bet stakes f of the morning balance (at most `cap` dollars), and a
    day's stakes together never exceed the balance."""
    if cap is None:
        feff = np.where(n * f > 1.0, 1.0 / np.maximum(n, 1), f)
        return START * np.concatenate([[1.0], np.cumprod(1.0 + feff * u)])
    bal, path = START, [START]
    for ui, ni in zip(u, n):
        stake = min(f * bal, cap, bal / ni if ni else np.inf)
        bal += stake * ui
        path.append(bal)
    return np.array(path)


def summary(end, dd, minbal, capped):
    q = lambda x, v: float(np.percentile(x, v))                    # noqa: E731
    return {"p10": q(end, 10), "p25": q(end, 25), "p50": q(end, 50), "p75": q(end, 75), "p90": q(end, 90),
            "mean": float(end.mean()), "loss": float((end < START).mean()),
            "dd50": q(dd, 50), "dd90": q(dd, 90), "dd_over_25": float((dd > 0.25).mean()),
            "dd_over_50": float((dd > 0.50).mean()), "min10": q(minbal, 10), "capped_days": float(capped)}


def main():
    T = daily_table()
    pools = {s: g.sort_values("day") for s, g in T.groupby("season")}
    seasons = list(pools)
    rng = np.random.default_rng(SEED)
    picks = [(seasons[rng.integers(len(seasons))]) for _ in range(N_SIM)]
    draws = [rng.integers(0, len(pools[s]), len(pools[s])) for s in picks]
    res, fans, actual = {}, {}, []
    for f, cap in [(f, c) for c in (None, 500.0) for f in FRACS]:
        for p, parts in PLANS.items():
            end, dd, minbal = np.empty(N_SIM), np.empty(N_SIM), np.empty(N_SIM)
            fan = np.empty((N_SIM, CHECKPOINTS))
            capped = 0
            for i, (s, idx) in enumerate(zip(picks, draws)):
                u, n = day_parts(pools[s], parts)
                u, n = u[idx], n[idx]
                capped += int((n * f > 1.0).sum())
                path = run_days(u, n, f, cap)
                end[i] = path[-1]
                peak = np.maximum.accumulate(path)
                dd[i] = float(np.max((peak - path) / peak))
                minbal[i] = path.min()
                pos = np.linspace(0, len(path) - 1, CHECKPOINTS)
                fan[i] = np.interp(pos, np.arange(len(path)), path)
            key = f"{p}@{int(f * 100)}%" + ("" if cap is None else "+cap500")
            res[key] = summary(end, dd, minbal, capped / N_SIM)
            fans[key] = {k: [float(np.percentile(fan[:, t], v)) for t in range(CHECKPOINTS)]
                         for k, v in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))}
            for s in seasons:                                             # the real seasons, in real order
                u, n = day_parts(pools[s], parts)
                path = run_days(u, n, f, cap)
                peak = np.maximum.accumulate(path)
                actual.append({"season": s, "plan": p, "stake": f"{int(f * 100)}%" + ("" if cap is None else " cap $500"),
                               "end": float(path[-1]),
                               "worst drop": float(np.max((peak - path) / peak)), "low point": float(path.min()),
                               "bets": int(n.sum()), "busiest day": int(n.max())})
    out = {"start": START, "fracs": FRACS, "plans": res, "fans": fans, "actual": actual}
    (ROOT / "reports" / "season_percent.json").write_text(json.dumps(out, default=float))

    rows = [{"plan @ stake": k, "typical end": f"${v['p50']:,.0f}", "8 in 10 seasons": f"${v['p10']:,.0f} to ${v['p90']:,.0f}",
             "below $10,000 at the end": f"{v['loss']:.0%}", "worst drop (typical / 1 in 10)": f"{v['dd50']:.0%} / {v['dd90']:.0%}",
             "drop over 25%": f"{v['dd_over_25']:.0%}", "drop over 50%": f"{v['dd_over_50']:.1%}"} for k, v in res.items()]
    A = pd.DataFrame(actual)
    lines = ["# A season from $10,000 at 1% and 2% of the account per bet\n",
             "Each bet stakes a share of that morning's balance; a day's stakes are capped at the whole balance. "
             "20,000 seasons replayed from 2021-26 at real prices.\n",
             df_to_md(pd.DataFrame(rows)), "",
             "## The real 2021-26 seasons, replayed in order\n",
             df_to_md(A.pivot_table(index=["season", "stake"], columns="plan", values="end").round(0).reset_index()), ""]
    (ROOT / "reports" / "season_percent.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("season_percent", {"start": START, "fracs": FRACS, "n_sim": N_SIM, "seed": SEED},
                   {"plans": res})


if __name__ == "__main__":
    main()
