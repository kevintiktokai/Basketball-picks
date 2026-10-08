"""What the straight-bet strategy looks like in money: the locked v3 engine's singles (calibrated
P >= 55% at the opener), season by season 2011-12 .. 2025-26, and a projection for a new season.

Staking: 1/8 Kelly (reports/staking_study.md; each day's total capped at 25% of the bankroll) and,
for comparison, a flat 1% of the bankroll per bet. Prices: -110 before 2021 (no per-book prices
exist), the best book's real price 2021-26.

Projection, from the 2021-26 test seasons at real prices (bets drawn with replacement, one by one;
same-day games were measured independent, |corr| < 0.01), 10,000 runs each:
  * a full season: each run takes the bet count of one of those five seasons at random (volume
    varies a lot between seasons, 88 to 1,380 bets);
  * a 700-bet season (about the 2021-26 average) under four assumptions: as tested, without line
    shopping (-110), with the edge cut in half, and with no skill at all. The fan chart is the
    "as tested" run's bankroll path.

Writes reports/singles_extrapolation.md and reports/singles_extrapolation.json (chart data).
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
from staking_study import DAY_CAP, bets, results

START = 1000.0                 # dollars; 1 unit = 1% of the bankroll = $10
KELLY = 1 / 8
ERA = {**{f"{y}-{str(y + 1)[2:]}": "development (2011-18)" for y in range(2011, 2018)},
       **{f"{y}-{str(y + 1)[2:]}": "holdout (2018-21)" for y in range(2018, 2021)},
       **{f"{y}-{str(y + 1)[2:]}": "untouched test, real prices (2021-26)" for y in range(2021, 2026)}}
N_SIM = 10_000
SEED = 20261008


def kelly_frac(p, odds):
    return np.clip((p * odds - 1) / (odds - 1), 0, None) * KELLY


def day_fractions(p, odds, day_ids):
    """1/8 Kelly fractions with each day's total capped at DAY_CAP."""
    f = kelly_frac(p, odds)
    tot = pd.Series(f).groupby(day_ids).transform("sum").values
    return np.where(tot > DAY_CAP, f * DAY_CAP / np.where(tot > 0, tot, 1), f)


def pnl(res, odds, stake):
    return np.where(res == 1, stake * (odds - 1), np.where(res == -1, -stake, 0.0))


def max_drawdown(path):
    path = np.asarray(path, float)
    return float(np.max(np.maximum.accumulate(path) - path)) if len(path) else 0.0


def main():
    B = bets()
    B = B[B.season.isin(ERA)].sort_values(["date", "game_key"]).reset_index(drop=True)
    real = B.season >= "2021-22"
    odds_110, res_110 = results(B, real=False)
    odds_r, res_r = results(B, real=True)
    B["odds"] = np.where(real, odds_r, odds_110)
    B["res"] = np.where(real, res_r, res_110)
    day = B.date.dt.strftime("%Y-%m-%d").values
    f = day_fractions(B.p_best.values, B.odds.values, day)
    B["flat_units"] = pnl(B.res.values, B.odds.values, 1.0)                 # 1 unit = 1% of a fixed bankroll
    B["kelly_units"] = pnl(B.res.values, B.odds.values, 100 * f)            # same fixed bankroll, Kelly-sized

    # season by season; the $ column re-sizes stakes to the current bankroll within the season
    seasons = []
    for s, g in B.groupby("season"):
        bank = START
        path = [bank]
        gd = g.date.dt.strftime("%Y-%m-%d").values
        fg = day_fractions(g.p_best.values, g.odds.values, gd)
        for d in pd.unique(gd):
            m = gd == d
            bank += pnl(g.res.values[m], g.odds.values[m], fg[m] * bank).sum()
            path.append(bank)
        dec = g[g.res != 0]
        seasons.append({"season": s, "era": ERA[s], "bets": len(g), "won": int((dec.res == 1).sum()),
                        "lost": int((dec.res == -1).sum()), "pushed": int((g.res == 0).sum()),
                        "win %": (dec.res == 1).mean(), "ROI flat": g.flat_units.mean(),
                        "units flat": g.flat_units.sum(), "units 1/8 Kelly": g.kelly_units.sum(),
                        "$1,000 becomes (1/8 Kelly)": bank, "worst dip in season ($)": max_drawdown(path)})
    S = pd.DataFrame(seasons)

    # cumulative path by betting day (fixed-bankroll units, so seasons add up)
    daily = B.groupby(B.date.dt.strftime("%Y-%m-%d")).agg(flat=("flat_units", "sum"), kelly=("kelly_units", "sum"),
                                                          season=("season", "first"), n=("res", "size"))
    daily["cum_flat"], daily["cum_kelly"] = daily.flat.cumsum(), daily.kelly.cumsum()

    # projection from the 2021-26 test seasons at real prices
    T = B[real].reset_index(drop=True)
    counts = T.groupby("season").size().values
    rng = np.random.default_rng(SEED)
    n_max = int(counts.max())
    paths = np.full((N_SIM, n_max + 1), np.nan)
    end_k, end_f, dd_k, n_bets = np.empty(N_SIM), np.empty(N_SIM), np.empty(N_SIM), np.empty(N_SIM, int)
    p, o, r = T.p_best.values, T.odds.values, T.res.values
    fk = kelly_frac(p, o)                     # one bet at a time: the day cap never binds for a single bet
    for i in range(N_SIM):
        n = int(rng.choice(counts))
        idx = rng.integers(0, len(T), n)
        bank, path = START, [START]
        for j in idx:
            bank += pnl(r[j], o[j], fk[j] * bank)
            path.append(bank)
        paths[i, :n + 1] = path
        end_k[i], dd_k[i], n_bets[i] = bank, max_drawdown(path), n
        end_f[i] = START + 10.0 * pnl(r[idx], o[idx], 1.0).sum()
    q = lambda x: {k: float(np.percentile(x, v)) for k, v in (("p10", 10), ("p25", 25), ("p50", 50),  # noqa: E731
                                                               ("p75", 75), ("p90", 90))}
    N_FAN = 700                               # about an average 2021-26 season

    # what if the future is worse than the test? one fixed 700-bet season under four assumptions
    o110, r110 = results(T, real=False)
    dec = T.res != 0
    q_obs = float((T.res[dec] == 1).mean())
    push_rate = float((T.res == 0).mean())
    scen = []
    for name, src in (("as tested: 2021-26 bets at the best book's price", "real"),
                      ("no line shopping: same bets at -110", "110"),
                      ("edge cut in half (win rate halfway to break-even)", "half"),
                      ("no skill: coin-flip picks, you pay the vig", "zero")):
        rng3 = np.random.default_rng(SEED + 2)
        ek, ef = np.empty(N_SIM), np.empty(N_SIM)
        keep_path = src == "real"                     # the fan chart is this scenario's bankroll paths
        if keep_path:
            fanpaths = np.empty((N_SIM, N_FAN // 10 + 1))
        for i in range(N_SIM):
            idx = rng3.integers(0, len(T), N_FAN)
            if src == "110":
                oo, rr = o110[idx], r110[idx]
            else:
                oo, rr = o[idx], r[idx]
                if src in ("half", "zero"):
                    be = 1 / oo
                    qq = (q_obs + be) / 2 if src == "half" else np.full(N_FAN, 0.5)
                    u = rng3.random(N_FAN)
                    rr = np.where(u < push_rate, 0, np.where(rng3.random(N_FAN) < qq, 1, -1))
            ff = kelly_frac(p[idx], oo)
            bank = START
            if keep_path:
                fanpaths[i, 0] = bank
            for j in range(N_FAN):
                bank += pnl(rr[j], oo[j], ff[j] * bank)
                if keep_path and (j + 1) % 10 == 0:
                    fanpaths[i, (j + 1) // 10] = bank
            ek[i], ef[i] = bank, START + 10.0 * pnl(rr, oo, 1.0).sum()
        if keep_path:
            fan = {k: [float(np.percentile(fanpaths[:, t], v)) for t in range(fanpaths.shape[1])]
                   for k, v in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))}
        scen.append({"scenario": name, "flat $10: median": float(np.median(ef)),
                     "flat: 10th-90th": (float(np.percentile(ef, 10)), float(np.percentile(ef, 90))),
                     "flat: losing season": float((ef < START).mean()),
                     "1/8 Kelly: median": float(np.median(ek)),
                     "Kelly: 10th-90th": (float(np.percentile(ek, 10)), float(np.percentile(ek, 90))),
                     "Kelly: losing season": float((ek < START).mean())})

    proj = {"season_volume": [int(c) for c in counts], "end_kelly": q(end_k), "end_flat": q(end_f),
            "scenarios_700_bets": scen, "win_rate_2021_26": q_obs,
            "p_loss_kelly": float((end_k < START).mean()), "p_loss_flat": float((end_f < START).mean()),
            "worst_dip_kelly": q(dd_k), "fan_every_10_bets": fan}
    tot = {"bets": int(len(B)), "win_pct": float((B[B.res != 0].res == 1).mean()),
           "units_flat": float(B.flat_units.sum()), "units_kelly": float(B.kelly_units.sum()),
           "roi_flat": float(B.flat_units.mean()), "roi_kelly": float(B.kelly_units.sum() / (100 * f).sum()),
           "max_dd_flat": max_drawdown(daily.cum_flat.values), "max_dd_kelly": max_drawdown(daily.cum_kelly.values)}
    test = B[real]
    tot_test = {"bets": int(len(test)), "win_pct": float((test[test.res != 0].res == 1).mean()),
                "units_flat": float(test.flat_units.sum()), "units_kelly": float(test.kelly_units.sum()),
                "roi_flat": float(test.flat_units.mean())}
    out = {"seasons": S.to_dict("records"), "totals_2011_26": tot, "totals_2021_26": tot_test, "projection": proj,
           "daily": [{"date": d, "season": r_.season, "cum_flat": round(r_.cum_flat, 2), "cum_kelly": round(r_.cum_kelly, 2)}
                     for d, r_ in daily.iterrows()]}
    (ROOT / "reports" / "singles_extrapolation.json").write_text(json.dumps(out, default=float))

    pe, pf = proj["end_kelly"], proj["end_flat"]
    lines = ["# Straight bets in money: the singles strategy 2011-26 and a projected season\n",
             "Locked v3 engine, singles at calibrated P >= 55% on the opener. 1 unit = 1% of the bankroll. "
             "Prices: -110 before 2021, best real book price 2021-26. 1/8 Kelly stakes, each day capped at 25%.\n",
             "## Season by season\n", df_to_md(S, "{:.3f}"), "",
             f"All 15 seasons: {tot['bets']:,} bets, won {tot['win_pct']:.1%}, flat +{tot['units_flat']:.0f} units "
             f"(ROI {tot['roi_flat']:+.1%}), 1/8 Kelly +{tot['units_kelly']:.0f} units; deepest dip "
             f"{tot['max_dd_flat']:.0f} units flat, {tot['max_dd_kelly']:.0f} units Kelly.\n",
             "## A new season, projected from the 2021-26 test seasons (10,000 runs)\n",
             f"Bets per season in 2021-26: {', '.join(map(str, proj['season_volume']))}.\n",
             f"Starting $1,000, 1/8 Kelly: median end ${pe['p50']:,.0f}; middle half ${pe['p25']:,.0f}-${pe['p75']:,.0f}; "
             f"10th-90th percentile ${pe['p10']:,.0f}-${pe['p90']:,.0f}; chance of a losing season "
             f"{proj['p_loss_kelly']:.0%}.",
             f"Flat $10 a bet: median end ${pf['p50']:,.0f}; 10th-90th ${pf['p10']:,.0f}-${pf['p90']:,.0f}; "
             f"chance of a losing season {proj['p_loss_flat']:.0%}.",
             "",
             "## If the future is worse than the test (one 700-bet season from $1,000)\n",
             df_to_md(pd.DataFrame(scen), "{:,.2f}")]
    (ROOT / "reports" / "singles_extrapolation.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("singles_extrapolation", {"kelly": KELLY, "day_cap": DAY_CAP, "n_sim": N_SIM, "seed": SEED},
                   {"totals": tot, "test": tot_test, "projection": {k: v for k, v in proj.items() if k != "fan_every_10_bets"}})


if __name__ == "__main__":
    main()
