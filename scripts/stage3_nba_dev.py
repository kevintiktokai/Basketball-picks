"""Stage 3 — NBA opening-line engine: DEVELOPMENT on 2021-22 and 2022-23 only.

Builds NBA games/features with the same pipeline as NCAAB, compares a small set of
model variants by log loss at the REAL opener on the development seasons, and writes
reports/stage3_nba_dev.md. Test seasons (2023-24..2025-26) are removed before
anything is fitted or evaluated.
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
from stage3_common import evaluate

S3 = yaml.safe_load((ROOT / "config" / "stage3.yaml").read_text())["nba"]
DEV, TEST = S3["development"], S3["test"]
V2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())["model"]
RO = ["x_pts", "x_eff", "x_poss", "line_rel", "move_hist_sum", "open_bias_sum"]


def nba_market(write_features: bool = True) -> pd.DataFrame:
    g, box, rep = unify_nba(write=True)
    print("NBA data:", rep, flush=True)
    f = build_ncaab_features(write=False, games=g, box=box)
    if write_features:
        f.to_parquet(ROOT / "data" / "processed" / "nba_features.parquet", index=False)
    d = market_frame(f, "open")
    for c in RO:
        d[f"{c}_ro"] = d[c] * d.is_real_open
    return d


VARIANTS = {
    "N1_same_as_ncaab": (V2["mean_feats"], V2["var_feats"]),
    "N2_plus_real_open_interactions": (V2["mean_feats"] + ["is_real_open"] + [f"{c}_ro" for c in RO], V2["var_feats"]),
    "N3_no_style": ([c for c in V2["mean_feats"] if not c.startswith("m_")],
                    [c for c in V2["var_feats"] if not c.startswith("m_")]),
}


def main():
    d = nba_market()
    d = d[~d.season.isin(TEST)]                                # test seasons removed
    seasons = sorted(d.season.unique())
    rows, keep = [], {}
    for name, (mf, vf) in VARIANTS.items():
        P, cals, calm = walk_forward_market(d, mf, vf, V2["kind"], V2["shape"], V2["alpha"], seasons=seasons,
                                            min_games=V2["min_games"], train_decay=0.6, calib_decay=0.6)
        M = main_line_probs(P, cals)
        Mm = main_line_probs(P.assign(mu=P.mu_mkt, sd=P.sd_mkt), calm)
        for s in DEV + ["DEV POOLED"]:
            e = M[(M.season.isin(DEV) if s == "DEV POOLED" else (M.season == s)) & M.eligible & ~M.push]
            em = Mm.set_index("game_key").loc[e.game_key]
            gain = (log_loss(em.p_over / (em.p_over + em.p_under), e.over)
                    - log_loss(e.p_over / (e.p_over + e.p_under), e.over)) * 1e4
            b = e[e.p_best >= 0.55]
            k, n = int(b.best_win.sum()), len(b)
            rows.append({"variant": name, "season": s, "games": len(e), "ll_gain_x1e4": gain,
                         "max_p": float(e.p_best.max()), "bets_p>=55%": n,
                         "win_p>=55%": k / n if n else np.nan, "ci95": wilson(k, n)})
        keep[name] = (P, cals, calm)
    R = pd.DataFrame(rows)
    pooled = R[R.season == "DEV POOLED"].set_index("variant").ll_gain_x1e4
    best = pooled.idxmax()
    lines = ["# Stage 3 — NBA opening-line engine: development (2021-22, 2022-23)\n",
             "Archive seasons (2007-21) supply history with a single line used as both open and "
             "close; 2021-22 onward use real openers (median of up to 6 books).\n",
             df_to_md(R), "",
             f"**Rule:** choose the variant with the best pooled development log-loss gain at the real "
             f"opener → **{best}** ({pooled[best]:+.1f}×10⁻⁴).\n"]
    P, cals, calm = keep[best]
    books = d.set_index("game_key").books_json
    E, _ = evaluate(P, cals, calm, books, DEV, label_prefix="[dev] ")
    lines += ["## Locked stage-3 products on the development seasons (informational)\n", df_to_md(E), ""]
    (ROOT / "reports" / "stage3_nba_dev.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("stage3_nba_dev", {"variants": list(VARIANTS)}, {"table": R.to_dict("records"), "best": best})


if __name__ == "__main__":
    main()
