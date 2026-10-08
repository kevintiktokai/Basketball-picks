"""Where does the NCAAB edge come from, and where does it leak? A post-mortem of every bet the
locked v3 engine would have made, out of sample (walk-forward), 2011-12 .. 2025-26.

Unit: the main-line single at the OPENING line on the model's side when its calibrated
probability is >= 55% (the stage-2b singles product), plus the 2.5+ target-card legs (2021-26).
Each slice reports win rate against the model's own prediction, ROI (-110 for all seasons; the
best book's real price where prices exist, 2021-26) and closing-line value (points the market
moved toward the bet between open and close).

Eras are kept apart so a pattern can be checked across time: development 2011-18, holdout
2018-21, re-analysis 2021-26. Nothing here changes the engine; it lists candidates to test.
Writes reports/bet_diagnostics.md.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml

from backtest.analysis import df_to_md
from backtest.odds_cards import best_main
from backtest.wf2 import main_line_probs
from calibration.calibrate import wilson
from config_loader import ROOT, log_experiment

ERA = {**{s: "dev 2011-18" for s in ["2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17", "2017-18"]},
       **{s: "holdout 2018-21" for s in ["2018-19", "2019-20", "2020-21"]},
       **{s: "re-analysis 2021-26" for s in ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]}}
P_MIN = 0.55


def load():
    from data.ncaab_unify import unify
    from features.ncaab_features import market_frame
    from features.store import cached_walk_forward, fingerprint, get_features
    u, box, _ = unify(write=False, include_live=True)
    f = get_features("ncaab", u, box, verbose=False)
    d = market_frame(f, "open")
    v2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())["model"]
    v3 = yaml.safe_load((ROOT / "config" / "stage3_v3_locked.yaml").read_text())["changes_vs_v2"]
    spec = dict(v2, train_decay=v3["train_decay"], calib_decay=v3["calib_decay"])
    return cached_walk_forward(d, spec, sorted(d.season.unique()), fingerprint(u, box))


def book_stats(bj, side):
    """Real best-book line+price for the side, cross-book dispersion of openers, n books."""
    line, price, _ = best_main(bj, side)
    try:
        opens = [v.get("open") for v in json.loads(bj).values() if v.get("open") is not None]
    except Exception:  # noqa: BLE001
        opens = []
    return line, price, (float(np.std(opens)) if len(opens) >= 2 else np.nan), len(opens)


def slice_table(B: pd.DataFrame, by: str, order=None) -> pd.DataFrame:
    rows = []
    groups = B.groupby(by, observed=True)
    keys = order if order is not None else sorted(groups.groups)
    for k in keys:
        if k not in groups.groups:
            continue
        g = groups.get_group(k)
        n, w = len(g), int(g.win.sum())
        lo, hi = wilson(w, n)
        rows.append({by: k, "bets": n, "win": w / n, "win 95% CI": (lo, hi), "predicted": g.p_best.mean(),
                     "win - predicted": w / n - g.p_best.mean(), "ROI @-110": g.pnl110.mean(),
                     "ROI real price": g.pnl_real.mean() if g.pnl_real.notna().any() else np.nan,
                     "CLV pts": g.clv.mean(), "moved our way": (g.clv > 0).mean()})
    return pd.DataFrame(rows)


def main():
    P, cals, calm = load()
    M = main_line_probs(P, cals)
    M = M[M.eligible & ~M.best_push & M.season.isin(ERA)].copy()
    M["era"] = M.season.map(ERA)
    M["win"] = M.best_win.astype(int)
    M["pnl110"] = np.where(M.win == 1, 100 / 110, -1.0)
    M["clv"] = M.best_side * (M.line_close - M.line_open)
    B = M[M.p_best >= P_MIN].copy()

    # real prices / book structure where SBR per-book odds exist (2021-26)
    live = B.books_json.notna() & B.books_json.astype(str).str.startswith("{")
    st = [book_stats(bj, int(s)) for bj, s in zip(B.loc[live, "books_json"], B.loc[live, "best_side"])]
    B["best_line"], B["best_price"], B["book_sd"], B["n_books"] = np.nan, np.nan, np.nan, np.nan
    if st:
        B.loc[live, ["best_line", "best_price", "book_sd", "n_books"]] = np.array(st, dtype=float)
    win_real = np.where(B.best_side == 1, B.outcome > B.best_line, B.outcome < B.best_line)
    push_real = B.outcome == B.best_line
    B["pnl_real"] = np.where(B.best_line.isna(), np.nan,
                             np.where(push_real, 0.0, np.where(win_real, B.best_price - 1, -1.0)))
    B["public_on_side"] = np.where(B.best_side == 1, B.over_pick_pct, 100 - B.over_pick_pct)

    # slices
    B["side"] = np.where(B.best_side == 1, "Over", "Under")
    B["p bucket"] = pd.cut(B.p_best, [0.55, 0.57, 0.59, 0.62, 1.0], right=False).astype(str)
    B["total (opener)"] = pd.qcut(B.line, 5, labels=["lowest", "low", "mid", "high", "highest"])
    B["|spread|"] = pd.cut(B.abs_spread, [-0.1, 4, 8, 14, 60], labels=["0-4", "4-8", "8-14", "14+"])
    B["month"] = B.date.dt.month.map({11: "1 Nov", 12: "2 Dec", 1: "3 Jan", 2: "4 Feb", 3: "5 Mar", 4: "6 Apr"})
    B["season phase"] = np.where(B.early == 1, "early (<6 games)", "rest of season")
    B["site"] = np.where(B.neutral_i == 1, "neutral", "home court")
    B["model edge"] = pd.qcut((B.mu / B.sd).abs(), 4, labels=["smallest", "small", "large", "largest"])
    B["CLV"] = np.select([B.clv > 0.25, B.clv < -0.25], ["moved our way", "moved against"], "no move")
    L = B[B.era == "re-analysis 2021-26"].copy()
    L["books at open"] = pd.cut(L.n_books, [0, 3, 5, 99], labels=["1-3", "4-5", "6+"])
    L["book disagreement"] = pd.cut(L.book_sd, [-0.01, 0.25, 0.75, 1.5, 99], labels=["none", "small", "medium", "large"])
    L["public on our side"] = pd.cut(L.public_on_side, [-1, 35, 50, 65, 101], labels=["<35%", "35-50%", "50-65%", ">65%"])

    sections = []
    sections.append(("By era (every bet with P >= 55%)", slice_table(B, "era", list(dict.fromkeys(ERA.values())))))
    sections.append(("By season", slice_table(B, "season")))
    for col in ("p bucket", "side", "total (opener)", "|spread|", "month", "season phase", "site", "model edge", "CLV"):
        T = pd.concat([slice_table(B[B.era == e], col).assign(era=e) for e in dict.fromkeys(ERA.values())])
        sections.append((f"By {col}, per era", T))
    for col in ("books at open", "book disagreement", "public on our side"):
        sections.append((f"By {col} (2021-26, where per-book odds exist)", slice_table(L, col)))

    # calibration of every eligible game (not only bets)
    M["p decile"] = pd.qcut(M.p_best, 10, duplicates="drop")
    cal = M.groupby(["era", "p decile"], observed=True).agg(games=("win", "size"), predicted=("p_best", "mean"),
                                                            actual=("win", "mean")).reset_index()
    cal["p decile"] = cal["p decile"].astype(str)

    # 2.5+ target cards, 2021-26 (leg level)
    cards = pd.read_csv(ROOT / "reports" / "stage3_ncaab_cards_target.csv")
    card_lines = []
    if len(cards):
        Fi = P.set_index("game_key")
        legs = []
        for l in ("a", "b"):
            g = Fi.loc[cards[f"game_{l}"]]
            legs.append(pd.DataFrame({"season": cards.season.values, "p": cards[f"p_{l}"].values if f"p_{l}" in cards else np.nan,
                                      "odds": cards[f"odds_{l}"].values if f"odds_{l}" in cards else np.nan,
                                      "win": cards[f"win_{l}"].values if f"win_{l}" in cards else np.nan,
                                      "side": cards[f"side_{l}"].values,
                                      "clv": cards[f"side_{l}"].values * (g.line_close.values - g.line_open.values)}))
        LG = pd.concat(legs)
        card_lines = [f"Target cards 2021-26: {len(cards)} cards, {2 * len(cards)} legs. "
                      f"Leg win {np.nanmean(LG.win):.3f} vs predicted {np.nanmean(LG.p):.3f}; "
                      f"legs moved our way {np.nanmean(LG.clv > 0):.1%} (+{np.nanmean(LG.clv):.2f} pts on average).",
                      f"Overs: win {np.nanmean(LG[LG.side == 1].win):.3f} (n={int((LG.side == 1).sum())}); "
                      f"Unders: win {np.nanmean(LG[LG.side == -1].win):.3f} (n={int((LG.side == -1).sum())})."]

    lines = ["# Where the NCAAB edge comes from: bet-level diagnostics (locked v3 engine, out of sample)\n",
             f"Every main-line single the engine would have taken at the opener (calibrated P >= {P_MIN:.0%}), "
             f"{len(B):,} bets over {B.season.nunique()} seasons. ROI @-110 for all seasons; real best-book "
             "price for 2021-26. CLV = points the line moved toward the bet from open to close.\n"]
    for title, T in sections:
        lines += [f"## {title}\n", df_to_md(T, "{:.3f}"), ""]
    lines += ["## Calibration of all eligible games (predicted vs actual)\n", df_to_md(cal, "{:.3f}"), ""]
    if card_lines:
        lines += ["## The 2.5+ target cards (2021-26)\n"] + card_lines + [""]
    (ROOT / "reports" / "bet_diagnostics.md").write_text("\n".join(lines) + "\n")
    B.drop(columns=["books_json"], errors="ignore").to_parquet(ROOT / "data" / "processed" / "ncaab_bets_diag.parquet", index=False)
    print("\n".join(lines[:6]))
    log_experiment("diagnose_bets", {"p_min": P_MIN}, {"bets": int(len(B))})


if __name__ == "__main__":
    main()
