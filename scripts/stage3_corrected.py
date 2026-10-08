"""CORRECTED re-runs after a data-quality fix discovered post-test.

Bug: "best book" line shopping took the best opening number across books with no sanity
check, so a single book's stale/erroneous opener (e.g. 145.5 when every other book
opened 166.5) could be selected — a number that was never realistically bettable.
Fix (outcome-blind, pre-stated here): ignore any book whose opener is more than 3 points
from the cross-book median opener (backtest.odds_cards.MAX_BOOK_DEV).

Model predictions are unaffected (they use the median opener); only leg pricing and
card selection change. Results here are labelled CORRECTED and are NOT pristine: the
original one-time results had already been seen. Original reports are kept unchanged.
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
import yaml

from backtest.analysis import df_to_md
from backtest.odds_cards import best_main
from backtest.wf2 import buffered_cards, leg_table, main_line_probs
from calibration.calibrate import wilson
from config_loader import ROOT, log_experiment
from features.ncaab_features import market_frame
from features.store import cached_walk_forward, fingerprint, get_features
from stage3_common import evaluate

OUT = []


def h(s=""):
    OUT.append(s)
    print(s, flush=True)


def singles_best_book(M, books, seasons):
    e = M[M.season.isin(seasons) & M.eligible & ~M.push]
    bj = books.reindex(e.game_key).values
    rows = []
    for lo, hi in ((0.5, 0.55), (0.55, 0.6), (0.6, 1.01)):
        m = np.where((e.p_best >= lo).values & (e.p_best < hi).values)[0]
        prof, wins, n = [], 0, 0
        for i in m:
            r = e.iloc[i]
            line, price, _ = best_main(bj[i], int(r.best_side))
            if np.isnan(line):
                line, price = r.line, 1.909
            win = r.outcome > line if r.best_side == 1 else r.outcome < line
            push = r.outcome == line
            prof.append(0.0 if push else (price - 1 if win else -1.0))
            wins += int(win)
            n += int(not push)
        rows.append({"two-sided P": f"{lo:.0%}-{min(hi, 1):.0%}", "bets": len(m),
                     "win_best_book": wins / n if n else np.nan, "ci95": wilson(wins, n),
                     "roi_best_book_real_price": float(np.mean(prof)) if prof else np.nan})
    return pd.DataFrame(rows)


def line_shopping_cards(P, cals, calm, books, seasons, J):
    T = leg_table(P, cals, calm)
    C = buffered_cards(T, joint_target=J, max_buffer=15.0, top_legs=14)
    C = C[C.season.isin(seasons) & (C.released == True)]  # noqa: E712
    Fi = P.set_index("game_key")
    ok = []
    for l in ("a", "b"):
        g = Fi.loc[C[f"game_{l}"]]
        side = C[f"side_{l}"].values
        best = np.array([best_main(b, int(s))[0] for b, s in zip(books.reindex(g.index).values, side)])
        gain = np.where(np.isnan(best), 0.0, np.where(side == 1, g.line_open.values - best, best - g.line_open.values))
        thr = C[f"thr_{l}"].values - side * np.maximum(gain, 0)
        out = g.outcome.values
        ok.append(np.where(side == 1, out > thr, out < thr))
    w = ok[0] & ok[1]
    k, n = int(w.sum()), len(w)
    return k, n


def main():
    from data.ncaab_unify import unify
    from data.nba_unify import unify_nba
    from stage3_nba_dev import nba_market
    v2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())["model"]
    v3c = yaml.safe_load((ROOT / "config" / "stage3_v3_locked.yaml").read_text())["changes_vs_v2"]
    h("# CORRECTED results — book-outlier guard (post-test data-quality fix)\n")
    h("_See the module docstring: books whose opener is > 3 pts from the cross-book median are "
      "ignored when shopping for the best number. Original one-time reports are unchanged; these "
      "corrected figures are not pristine because the originals had been seen._\n")

    # ---------------- NCAAB
    u, box, _ = unify(write=False, include_live=True)
    f = get_features("ncaab", u, box)
    d = market_frame(f, "open")
    seasons = sorted(d.season.unique())
    fp = fingerprint(u, box)
    books = d.set_index("game_key").books_json
    EV = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    spec3 = dict(v2, train_decay=v3c["train_decay"], calib_decay=v3c["calib_decay"])
    P3, c3, m3 = cached_walk_forward(d, spec3, seasons, fp)
    R, _ = evaluate(P3, c3, m3, books, EV)
    h("## NCAAB 2021-26 (re-analysis) — stage-3 products, corrected\n")
    h(df_to_md(R[R.season == "POOLED"]))
    h()
    h("## NCAAB 2021-26 — stage-2b secondary figures, corrected\n")
    P2, c2, m2 = cached_walk_forward(d, dict(v2), seasons, fp)
    for name, (P, cals, calm, J) in (("v2", (P2, c2, m2, 0.625)), ("v3", (P3, c3, m3, 0.65))):
        k, n = line_shopping_cards(P, cals, calm, books, EV, J)
        lo, hi = wilson(k, n)
        h(f"* {name} buffered cards, line-shopping variant: {k}/{n} = {k / n:.1%} (CI {lo:.1%}–{hi:.1%})")
        h(df_to_md(singles_best_book(main_line_probs(P, cals), books, EV)))
        h()

    # ---------------- NBA
    dn = nba_market()
    lockn = yaml.safe_load((ROOT / "config" / "stage3_nba_locked.yaml").read_text())
    Pn, cn, mn = cached_walk_forward(dn, lockn["model"], sorted(dn.season.unique()),
                                     f"nba-{len(dn)}-{dn.total.sum():.0f}")
    TEST = yaml.safe_load((ROOT / "config" / "stage3.yaml").read_text())["nba"]["test"]
    booksn = dn.set_index("game_key").books_json
    Rn, _ = evaluate(Pn, cn, mn, booksn, TEST)
    h("## NBA 2023-26 test — stage-3 products, corrected\n")
    h(df_to_md(Rn))
    h()
    h("### NBA singles at the best book (corrected)\n")
    h(df_to_md(singles_best_book(main_line_probs(Pn, cn), booksn, TEST)))
    (ROOT / "reports" / "stage3_corrected.md").write_text("\n".join(OUT) + "\n")
    log_experiment("stage3_corrected", {"max_book_dev": 3.0},
                   {"ncaab_pooled": R[R.season == "POOLED"].to_dict("records"),
                    "nba_pooled": Rn[Rn.season == "POOLED"].to_dict("records")})


if __name__ == "__main__":
    main()
