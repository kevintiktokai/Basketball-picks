"""Did the possessions bug in DailyRatings (venue term dropped from predicted tempo; see
features/ratings.py) hold back the NBA opener model?

NBA games are all coded non-neutral, so the tempo intercept was split with the venue term
and `rt_poss` / `rt_eff_total` came out about half size, distorting the `x_eff` feature.
This re-runs the locked NBA variant (N3_no_style) on the DEVELOPMENT seasons only
(2021-22, 2022-23), with and without the fix. Test seasons (2023-26) are dropped before
any modelling, as in stage3_nba_dev.py; they were already used once and are not reopened.
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
from backtest.wf2 import main_line_probs, walk_forward_market
from calibration.calibrate import log_loss, wilson
from config_loader import ROOT, log_experiment
from data.nba_unify import unify_nba
from features.ncaab_features import build_ncaab_features, market_frame
from features.store import get_features

S3 = yaml.safe_load((ROOT / "config" / "stage3.yaml").read_text())["nba"]
DEV, TEST = S3["development"], S3["test"]
LOCK = yaml.safe_load((ROOT / "config" / "stage3_nba_locked.yaml").read_text())["model"]
RATINGS = {"half_life_days": 45, "prev_season_weight": 0.15, "ridge": 3.0}   # build_ncaab_features default


def dev_table(d: pd.DataFrame, label: str) -> list[dict]:
    d = d[~d.season.isin(TEST)]
    P, cals, calm = walk_forward_market(d, LOCK["mean_feats"], LOCK["var_feats"], LOCK["kind"], LOCK["shape"],
                                        LOCK["alpha"], seasons=sorted(d.season.unique()), min_games=LOCK["min_games"],
                                        train_decay=LOCK["train_decay"], calib_decay=LOCK["calib_decay"])
    M = main_line_probs(P, cals)
    Mm = main_line_probs(P.assign(mu=P.mu_mkt, sd=P.sd_mkt), calm)
    rows = []
    for s in DEV + ["DEV POOLED"]:
        e = M[(M.season.isin(DEV) if s == "DEV POOLED" else (M.season == s)) & M.eligible & ~M.push]
        em = Mm.set_index("game_key").loc[e.game_key]
        gain = (log_loss(em.p_over / (em.p_over + em.p_under), e.over)
                - log_loss(e.p_over / (e.p_over + e.p_under), e.over)) * 1e4
        b = e[e.p_best >= 0.55]
        k, n = int(b.best_win.sum()), len(b)
        rows.append({"ratings": label, "season": s, "games": len(e), "ll_gain_x1e4": gain,
                     "bets_p>=55%": n, "win_p>=55%": k / n if n else np.nan, "ci95": wilson(k, n)})
    return rows


def main():
    g, box, _ = unify_nba(write=False)
    f_old = get_features("nba", g, box)                                    # locked behaviour
    f_new = build_ncaab_features(write=False, ratings_kw={**RATINGS, "venue_tempo": True}, games=g, box=box)
    chk = f_old.merge(f_new[["game_key", "rt_poss"]], on="game_key", suffixes=("_old", "_new"))
    poss = box.drop_duplicates("espn_game_id").poss.mean() if "poss" in box else np.nan
    rows = dev_table(market_frame(f_old, "open"), "as locked (bug)") + \
        dev_table(market_frame(f_new, "open"), "venue_tempo fixed")
    R = pd.DataFrame(rows)
    lines = ["# NBA: effect of the possessions fix on the development seasons\n",
             f"Mean predicted possessions: as locked **{chk.rt_poss_old.mean():.1f}**, fixed "
             f"**{chk.rt_poss_new.mean():.1f}** (actual box-score average {poss:.1f}).\n",
             "Locked NBA variant (N3_no_style), walk-forward, development seasons only; the 2023-26 "
             "test seasons are removed before modelling. `ll_gain` is the log-loss gain over the "
             "market-only model at the opener (×10⁻⁴; higher is better).\n",
             df_to_md(R, "{:.3f}"), ""]
    out = ROOT / "reports" / "nba_tempo_fix_check.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("stage3_nba_tempo_check", {"ratings": RATINGS, "variant": "N3_no_style", "dev": DEV},
                   {"table": R.to_dict("records")})


if __name__ == "__main__":
    main()
