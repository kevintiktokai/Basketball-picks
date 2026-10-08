"""What the two-leg card strategy looks like in money, next to the straight bets.

Cards: the locked stage-3 TARGET CARD (config/stage3_locked.yaml): at most one card per slate, two
legs priced 1.40-1.90, combined odds >= 2.5, chosen for the highest chance that both legs win, and
released only when the conservative expected value is positive. Main-line legs are priced at the
best book's real opening price where per-book odds exist (2021-26) and at -110 before; alternate
lines are priced by the model of the book's price (4.5% margin off the opener). The locked
sensitivity runs (alternates at an 8% margin; alternates priced off the closing line) are kept as
"what if prices are worse" scenarios. The main-line double (real prices only) is shown for reference.

The card rules were chosen on 2011-21; 2021-26 is their first run with the rules locked (those
seasons had been used earlier for the straight-bet test, so it is a re-analysis, not untouched).

Prices follow the corrected line shopping (books more than 3 points off the median opener are ignored;
reports/stage3_corrected.md). A parlay is placed at ONE book, so each product is also run with no
shopping at all: main-line legs at -110 on the consensus opener.

Staking: 1 unit (1% of the bankroll) per card, and 1/8 Kelly on the card's model probability.
Projection: 10,000 runs of a 133-card season (the 2021-26 average; volume barely varies: 128-136)
bootstrapped from the 2021-26 cards, under five assumptions.
Writes reports/cards_extrapolation.md and reports/cards_extrapolation.json.
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

START, KELLY, N_SIM, SEED = 1000.0, 1 / 8, 10_000, 20261008
SEASONS = [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2026)]
TEST = SEASONS[-5:]
MARGIN = 0.045
PERIOD = {**{s: "rules chosen (2011-21)" for s in SEASONS[:-5]}, **{s: "locked rules, first run (2021-26)" for s in TEST}}


def kelly(p, o):
    return np.clip((p * o - 1) / (o - 1), 0, None) * KELLY


def max_drawdown(path):
    path = np.asarray(path, float)
    return float(np.max(np.maximum.accumulate(path) - path)) if len(path) else 0.0


def longest_losing_run(wins):
    best = cur = 0
    for w in wins:
        cur = 0 if w else cur + 1
        best = max(best, cur)
    return best


def season_rows(C: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s, g in C.groupby("season"):
        f = kelly(g.joint_model.values, g.combined_odds.values)
        bank, path = START, [START]
        for fi, pr in zip(f, g.profit.values):
            bank += fi * bank * pr
            path.append(bank)
        rows.append({"season": s, "period": PERIOD[s], "cards": len(g), "both won": int(g.card_win.sum()),
                     "won %": g.card_win.mean(), "avg odds": g.combined_odds.mean(),
                     "break-even %": (1 / g.combined_odds).mean(), "ROI flat": g.profit.mean(),
                     "units flat": g.profit.sum(), "units 1/8 Kelly": float((100 * f * g.profit.values).sum()),
                     "$1,000 becomes (1/8 Kelly)": bank, "worst dip in season ($)": max_drawdown(path),
                     "longest losing run": longest_losing_run(g.card_win.values)})
    return pd.DataFrame(rows)


def simulate(C: pd.DataFrame, n: int, mode: str, rng) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Bankroll after an n-card season: flat $10 a card and 1/8 Kelly compounding. mode 'real'
    replays the cards' own results; 'half' and 'none' redraw each card's result."""
    o, pr, p = C.combined_odds.values, C.profit.values, C.joint_model.values
    q_obs = C.card_win.mean()
    ek, ef = np.empty(N_SIM), np.empty(N_SIM)
    fan = np.empty((N_SIM, n + 1)) if mode == "real" else None
    for i in range(N_SIM):
        idx = rng.integers(0, len(C), n)
        if mode == "real":
            prof = pr[idx]
        else:
            q = (q_obs + 1 / o[idx]) / 2 if mode == "half" else (1 - MARGIN) ** 2 / o[idx]
            prof = np.where(rng.random(n) < q, o[idx] - 1, -1.0)
        f = kelly(p[idx], o[idx])
        bank = START
        if fan is not None:
            fan[i, 0] = bank
        for j in range(n):
            bank += f[j] * bank * prof[j]
            if fan is not None:
                fan[i, j + 1] = bank
        ek[i], ef[i] = bank, START + 10.0 * prof.sum()
    return ek, ef, fan


def main():
    P, cals, calm = load()
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    _, cards = evaluate(P, cals, calm, books, SEASONS)
    names = list(cards)
    target = cards[names[0]].sort_values("date").reset_index(drop=True)          # locked target card
    margin8 = cards[names[1]].sort_values("date").reset_index(drop=True)         # sensitivity: 8% margin
    close = cards[names[2]].sort_values("date").reset_index(drop=True)           # stress: priced off the close
    double = cards[names[4]].sort_values("date").reset_index(drop=True)          # main-line double, real prices
    S = season_rows(target)
    Sd = season_rows(double)

    f_all = kelly(target.joint_model.values, target.combined_odds.values)
    target["units_flat"] = target.profit
    target["units_kelly"] = 100 * f_all * target.profit
    cum = target.assign(cum_flat=target.units_flat.cumsum(), cum_kelly=target.units_kelly.cumsum())

    _, cards1 = evaluate(P, cals, calm, None, TEST)                               # one book: -110, consensus opener
    target1 = cards1[names[0]].sort_values("date").reset_index(drop=True)
    double1 = cards1[names[4]].sort_values("date").reset_index(drop=True)

    T = target[target.season.isin(TEST)]
    n_season = int(round(T.groupby("season").size().mean()))
    rng = np.random.default_rng(SEED)
    scen, fan = [], None
    for label, src, mode in (("as tested: alternates priced at a 4.5% margin off the opener", T, "real"),
                             ("one book, no line shopping (main legs at -110)", target1, "real"),
                             ("alternates priced worse: 8% margin", margin8[margin8.season.isin(TEST)], "real"),
                             ("alternates priced off the closing line", close[close.season.isin(TEST)], "real"),
                             ("edge cut in half (win rate halfway to break-even)", T, "half"),
                             ("no skill: legs win at the book's fair odds", T, "none")):
        ek, ef, fp = simulate(src, n_season, mode, rng)
        if fan is None and fp is not None:
            fan = {k: [float(np.percentile(fp[:, t], v)) for t in range(0, n_season + 1)]
                   for k, v in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))}
        scen.append({"scenario": label, "flat $10: median": float(np.median(ef)),
                     "flat: 10th-90th": (float(np.percentile(ef, 10)), float(np.percentile(ef, 90))),
                     "flat: losing season": float((ef < START).mean()),
                     "1/8 Kelly: median": float(np.median(ek)),
                     "Kelly: 10th-90th": (float(np.percentile(ek, 10)), float(np.percentile(ek, 90))),
                     "Kelly: 25th-75th": (float(np.percentile(ek, 25)), float(np.percentile(ek, 75))),
                     "Kelly: losing season": float((ek < START).mean())})

    Dt = double[double.season.isin(TEST)]
    n_double = int(round(Dt.groupby("season").size().mean()))
    scen_d = []
    for label, src, mode in (("as tested: each leg at its best book's price", Dt, "real"),
                             ("one book, no line shopping (both legs at -110)", double1, "real"),
                             ("edge cut in half (win rate halfway to break-even)", Dt, "half"),
                             ("no skill: legs win at the book's fair odds", Dt, "none")):
        ek, ef, _ = simulate(src, n_double, mode, rng)
        scen_d.append({"scenario": label, "flat $10: median": float(np.median(ef)),
                       "flat: 10th-90th": (float(np.percentile(ef, 10)), float(np.percentile(ef, 90))),
                       "flat: losing season": float((ef < START).mean()),
                       "1/8 Kelly: median": float(np.median(ek)),
                       "Kelly: 10th-90th": (float(np.percentile(ek, 10)), float(np.percentile(ek, 90))),
                       "Kelly: 25th-75th": (float(np.percentile(ek, 25)), float(np.percentile(ek, 75))),
                       "Kelly: losing season": float((ek < START).mean())})
    one_book = {"target": {"cards": len(target1), "won_pct": float(target1.card_win.mean()), "roi": float(target1.profit.mean()),
                           "units": float(target1.profit.sum()), "avg_odds": float(target1.combined_odds.mean())},
                "double": {"cards": len(double1), "won_pct": float(double1.card_win.mean()), "roi": float(double1.profit.mean()),
                           "units": float(double1.profit.sum()), "avg_odds": float(double1.combined_odds.mean())}}
    singles = json.loads((ROOT / "reports" / "singles_extrapolation.json").read_text())
    tot = {"cards": int(len(target)), "won_pct": float(target.card_win.mean()), "avg_odds": float(target.combined_odds.mean()),
           "units_flat": float(target.units_flat.sum()), "units_kelly": float(target.units_kelly.sum()),
           "roi_flat": float(target.profit.mean()), "max_dd_flat": max_drawdown(cum.cum_flat.values),
           "max_dd_kelly": max_drawdown(cum.cum_kelly.values), "longest_losing_run": longest_losing_run(target.card_win.values),
           "slates": int(P[P.calibrated & P.eligible & P.season.isin(SEASONS)].date.nunique())}
    test = {"cards": int(len(T)), "won_pct": float(T.card_win.mean()), "avg_odds": float(T.combined_odds.mean()),
            "units_flat": float(T.profit.sum()), "roi_flat": float(T.profit.mean()),
            "leg_win": float(np.r_[T.win_a.values, T.win_b.values].mean()),
            "alt_leg_share": float(np.r_[~T.main_a.values, ~T.main_b.values].mean())}
    out = {"seasons": S.to_dict("records"), "double_seasons": Sd.to_dict("records"), "totals": tot, "test": test,
           "per_season_cards": n_season, "scenarios": scen, "fan": fan,
           "double_per_season": n_double, "double_scenarios": scen_d, "one_book_2021_26": one_book,
           "double_totals": {"cards": int(len(double)), "won_pct": float(double.card_win.mean()),
                             "units_flat": float(double.profit.sum()), "roi_flat": float(double.profit.mean()),
                             "avg_odds": float(double.combined_odds.mean())},
           "double_test": {"cards": int(len(Dt)), "won_pct": float(Dt.card_win.mean()), "units_flat": float(Dt.profit.sum()),
                           "roi_flat": float(Dt.profit.mean()), "avg_odds": float(Dt.combined_odds.mean())},
           "double_cum": [{"date": str(d.date()), "cum_flat": round(c, 2)} for d, c in zip(double.date, double.profit.cumsum())],
           "cum": [{"date": str(d.date()), "season": s, "cum_flat": round(a, 2), "cum_kelly": round(b, 2)}
                   for d, s, a, b in zip(cum.date, cum.season, cum.cum_flat, cum.cum_kelly)],
           "singles": {"seasons": singles["seasons"], "totals": singles["totals_2011_26"], "test": singles["totals_2021_26"],
                       "scenario_as_tested": singles["projection"]["scenarios_700_bets"][0]}}
    (ROOT / "reports" / "cards_extrapolation.json").write_text(json.dumps(out, default=float))

    lines = ["# Two-leg cards in money: the 2.5+ target card 2011-26, a projected season, and straight bets\n",
             "Locked target card (one per slate, legs 1.40-1.90, combined >= 2.5, highest chance both win). 1 unit = 1% "
             "of the bankroll. Main legs at real best-book prices 2021-26 and -110 before; alternate legs at the model's "
             "price (4.5% margin). Rules chosen on 2011-21; 2021-26 is their first locked run (a re-analysis).\n",
             "## Season by season (target card)\n", df_to_md(S, "{:.3f}"), "",
             f"All 15 seasons: {tot['cards']:,} cards, both legs won {tot['won_pct']:.1%} at average odds "
             f"{tot['avg_odds']:.2f}; flat +{tot['units_flat']:.0f} units (ROI {tot['roi_flat']:+.1%}), 1/8 Kelly "
             f"+{tot['units_kelly']:.0f} units; deepest dip {tot['max_dd_flat']:.0f} units; longest losing run "
             f"{tot['longest_losing_run']} cards.\n",
             f"## A {n_season}-card season from $1,000 (10,000 runs from the 2021-26 cards)\n",
             df_to_md(pd.DataFrame(scen), "{:,.2f}"), "",
             "## Main-line double (two main-line picks parlayed)\n", df_to_md(Sd, "{:.3f}"), "",
             f"A {n_double}-card season from $1,000:\n", df_to_md(pd.DataFrame(scen_d), "{:,.2f}"), "",
             "## One book, no line shopping, 2021-26 (a parlay is placed at one book)\n",
             df_to_md(pd.DataFrame(one_book).T.reset_index().rename(columns={"index": "product"}), "{:.3f}")]
    (ROOT / "reports" / "cards_extrapolation.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("cards_extrapolation", {"kelly": KELLY, "n_sim": N_SIM, "seed": SEED, "season_cards": n_season},
                   {"totals": tot, "test": test, "scenarios": scen})


if __name__ == "__main__":
    main()
