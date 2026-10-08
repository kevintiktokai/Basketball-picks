"""NCAAB stage map: how the market and the locked v3 engine behave at each stage of the season.

Stages come from ESPN schedules (data/ncaab_stages.py): non-conference at home, non-conference at
neutral sites (multi-team events), conference regular season, conference tournaments, the NCAA
tournament and the other postseason events. Early-season games (a team with < 6 games) are also
shown separately because they cut across stages.

Only the 2011-12 .. 2020-21 seasons are read (dev 2011-18 and holdout 2018-21 of the locked engine).
The 2021-22 .. 2025-26 seasons are SEALED here: they are kept for a one-time confirmation of any
stage strategy chosen from this map (config/improvements.yaml, study 2).
Writes reports/ncaab_stage_map.md.
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

from backtest.analysis import df_to_md
from backtest.wf2 import main_line_probs
from calibration.calibrate import wilson
from config_loader import ROOT, log_experiment
from data.ncaab_stages import STAGES, attach
from diagnose_bets import load

ERAS = {**{s: "dev 2011-18" for s in ["2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17", "2017-18"]},
        **{s: "holdout 2018-21" for s in ["2018-19", "2019-20", "2020-21"]}}
P_MIN = 0.55
LABEL = {"nonconf_home": "non-conference, campus site", "nonconf_neutral": "non-conference, neutral site (events)",
         "conf_regular": "conference regular season", "conf_tournament": "conference tournaments",
         "ncaa_tournament": "NCAA tournament", "other_postseason": "NIT / CBI / CIT"}


def ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


def frame():
    P, cals, calm = load()
    P = P[P.season.isin(ERAS)]                                     # 2021-26 sealed
    M = main_line_probs(P, cals)
    Mm = main_line_probs(P.assign(mu=P.mu_mkt, sd=P.sd_mkt), calm).set_index("game_key")
    M = M[M.eligible].copy()
    M["p2"] = M.p_over / (M.p_over + M.p_under)
    M["p2_mkt"] = (Mm.p_over / (Mm.p_over + Mm.p_under)).reindex(M.game_key).values
    M = attach(M)
    M["era"] = M.season.map(ERAS)
    M["phase"] = np.where(M.rt_min_games < 6, "early (a team < 6 games)", "established")
    return M


def stage_rows(M: pd.DataFrame, by: str, order) -> pd.DataFrame:
    rows = []
    for era in list(dict.fromkeys(ERAS.values())) + ["2011-21"]:
        E = M if era == "2011-21" else M[M.era == era]
        for k in order:
            g = E[E[by] == k]
            if not len(g):
                continue
            np_ = g[g.outcome != g.line]
            y = (np_.outcome > np_.line).astype(int)
            b = g[(g.p_best >= P_MIN) & ~g.best_push]
            w, n = int(b.best_win.sum()), len(b)
            clv = (b.best_side * (b.line_close - b.line_open))
            rows.append({
                "era": era, by: LABEL.get(k, k), "games": len(g),
                "market error (open)": (g.outcome - g.line_open).abs().mean(),
                "market error (close)": (g.outcome - g.line_close).abs().mean(),
                "line move": (g.line_close - g.line_open).abs().mean(),
                "total - opener": (g.outcome - g.line_open).mean(),
                "Over rate": y.mean(), "OT rate": g.ot.mean(),
                "model gain x1e4": (ll(np_.p2_mkt, y) - ll(np_.p2, y)) * 1e4,
                "bets": n, "bet win": w / n if n else np.nan, "win 95% CI": wilson(w, n),
                "predicted": b.p_best.mean() if n else np.nan,
                "ROI @-110": (w * 100 / 110 - (n - w)) / n if n else np.nan,
                "CLV pts": clv.mean() if n else np.nan, "Under share": (b.best_side == -1).mean() if n else np.nan})
    return pd.DataFrame(rows)


def main():
    M = frame()
    T = stage_rows(M, "stage", STAGES)
    E = stage_rows(M, "phase", ["early (a team < 6 games)", "established"])
    pooled = T[T.era == "2011-21"]
    lines = ["# NCAAB stage map (2011-12 .. 2020-21; 2021-26 sealed for confirmation)\n",
             "Every eligible game the locked v3 engine priced out of sample, split by stage of the season "
             "(ESPN schedule labels). *Market error* = average miss of the opening (closing) total in points; "
             "*line move* = average size of the open-to-close move; *model gain* = how much better the engine's "
             "probabilities are than the market-only model (log loss ×10⁻⁴, positive = better); bets = "
             f"singles at calibrated P >= {P_MIN:.0%} on the opener, ROI at -110; CLV = points the line moved "
             "toward the bet.\n",
             "## Pooled 2011-21\n", df_to_md(pooled.drop(columns="era"), "{:.3f}"), "",
             "## By era (a stage pattern should hold in both)\n", df_to_md(T[T.era != "2011-21"], "{:.3f}"), "",
             "## Early season vs established teams\n", df_to_md(E, "{:.3f}"), ""]
    (ROOT / "reports" / "ncaab_stage_map.md").write_text("\n".join(lines) + "\n")
    M.drop(columns=["books_json"], errors="ignore").to_parquet(ROOT / "data" / "processed" / "ncaab_stage_frame_2011_21.parquet",
                                                               index=False)
    print("\n".join(lines))
    log_experiment("ncaab_stage_map", {"seasons": sorted(ERAS), "p_min": P_MIN},
                   {"pooled": pooled.astype(str).to_dict("records")})


if __name__ == "__main__":
    main()
