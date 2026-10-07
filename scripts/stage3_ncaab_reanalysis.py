"""Stage 3 — NCAAB 2021-26 RE-ANALYSIS of the locked odds-card products at real prices.

These seasons were the stage-2b test set; this is a re-analysis of used data (not a
new independent test). The products and policy are locked in config/stage3_locked.yaml.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import pandas as pd
import yaml

from backtest.analysis import df_to_md
from backtest.wf2 import walk_forward_market
from config_loader import ROOT, log_experiment
from features.ncaab_features import market_frame
from stage3_common import evaluate, locked

EVAL = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]


def main():
    f = pd.read_parquet(ROOT / "data" / "processed" / "ncaab_features_unified_all.parquet")
    d = market_frame(f, "open")
    v2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())["model"]
    v3 = yaml.safe_load((ROOT / "config" / "stage3_v3_locked.yaml").read_text())["changes_vs_v2"]
    P, cals, calm = walk_forward_market(d, v2["mean_feats"], v2["var_feats"], v2["kind"], v2["shape"],
                                        v2["alpha"], seasons=sorted(d.season.unique()),
                                        min_games=v2["min_games"], train_decay=v3["train_decay"],
                                        calib_decay=v3["calib_decay"])
    books = d.set_index("game_key").books_json if "books_json" in d else None
    R, cards = evaluate(P, cals, calm, books, EVAL)
    lines = ["# Stage 3 — NCAAB 2021-26 re-analysis: odds-targeted cards at real prices\n",
             "_These seasons were already used as the stage-2b test; this is a RE-ANALYSIS of used "
             "data with products locked in `config/stage3_locked.yaml` (locked at revision "
             f"`{locked()['locked_at_revision']}`), not a new independent test._\n",
             df_to_md(R), ""]
    (ROOT / "reports" / "stage3_ncaab_reanalysis.md").write_text("\n".join(lines) + "\n")
    for name, C in cards.items():
        tag = name.strip().split(" ")[0].lower().replace(":", "")
        C.to_csv(ROOT / "reports" / f"stage3_ncaab_cards_{tag}.csv", index=False)
    print("\n".join(lines))
    log_experiment("stage3_ncaab_reanalysis", {"lock": locked()},
                   {"pooled": R[R.season == "POOLED"].to_dict("records")})


if __name__ == "__main__":
    main()
