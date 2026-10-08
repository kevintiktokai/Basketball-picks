"""Stage 3 — WNBA opening-line engine: DEVELOPMENT on 2021 and 2022 only (config/stage3.yaml `wnba`).

Same pipeline as the NBA (scripts/stage3_nba_dev.py). The test seasons (2023-26) are removed
before anything is fitted or evaluated. Odds start in 2019, so 2019-20 are training history;
with two training seasons the walk-forward predicts from 2021 and calibrates from 2023, so the
development comparison uses the models' own (uncalibrated) probabilities against the
market-only model, the same log-loss-gain rule as the NBA.

Writes reports/stage3_wnba_dev.md and config/stage3_wnba_locked.yaml (the variant chosen by
the pre-stated rule).
"""
from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm

from backtest.analysis import df_to_md
from backtest.wf2 import walk_forward_market
from calibration.calibrate import log_loss, wilson
from config_loader import ROOT, log_experiment
from data.wnba_unify import unify_wnba
from features.ncaab_features import build_ncaab_features, market_frame

S3 = yaml.safe_load((ROOT / "config" / "stage3.yaml").read_text())["wnba"]
DEV, TEST = S3["development"], S3["test"]
V2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())["model"]
RATINGS = {"half_life_days": 45, "prev_season_weight": 0.15, "ridge": 3.0, "venue_tempo": True}
VARIANTS = {
    "W1_same_as_ncaab": (V2["mean_feats"], V2["var_feats"]),
    "W3_no_style": ([c for c in V2["mean_feats"] if not c.startswith("m_")],
                    [c for c in V2["var_feats"] if not c.startswith("m_")]),
}
LOCK = ROOT / "config" / "stage3_wnba_locked.yaml"


def wnba_market():
    g, box, rep = unify_wnba(write=True)
    f = build_ncaab_features(write=False, ratings_kw=RATINGS, games=g, box=box)
    return market_frame(f, "open"), rep


def walk(d, mf, vf):
    return walk_forward_market(d, mf, vf, V2["kind"], V2["shape"], V2["alpha"], seasons=sorted(d.season.unique()),
                               min_games=V2["min_games"], train_decay=0.6, calib_decay=0.6)


def raw_probs(P):
    """Model and market-only P(over the opening line), uncalibrated (normal shape)."""
    e = P[P.eligible & (P.outcome != P.line)].copy()
    e["over"] = (e.outcome > e.line).astype(int)
    e["p_model"] = norm.cdf(e.mu / e.sd)
    e["p_mkt"] = norm.cdf(e.mu_mkt / e.sd_mkt)
    return e


def main():
    if LOCK.exists():
        sys.exit(f"REFUSING: {LOCK.name} exists — the WNBA variant is already locked.")
    d, rep = wnba_market()
    print("WNBA data:", rep, flush=True)
    d = d[~d.season.isin(TEST)]                                # test seasons removed
    rows = []
    for name, (mf, vf) in VARIANTS.items():
        P, _, _ = walk(d, mf, vf)
        E = raw_probs(P)
        for s in DEV + ["DEV POOLED"]:
            e = E[E.season.isin(DEV)] if s == "DEV POOLED" else E[E.season == s]
            gain = (log_loss(e.p_mkt, e.over) - log_loss(e.p_model, e.over)) * 1e4
            pb = np.maximum(e.p_model, 1 - e.p_model)
            win = np.where(e.p_model >= 0.5, e.over == 1, e.over == 0)
            b = pb >= 0.55
            k, n = int(win[b].sum()), int(b.sum())
            rows.append({"variant": name, "season": s, "games": len(e), "ll_gain_x1e4": gain,
                         "bets_p>=55%": n, "win_p>=55%": k / n if n else np.nan, "ci95": wilson(k, n)})
    R = pd.DataFrame(rows)
    pooled = R[R.season == "DEV POOLED"].set_index("variant").ll_gain_x1e4
    best = pooled.idxmax()
    mf, vf = VARIANTS[best]
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    lock = {"comment": "LOCKED WNBA opener engine, chosen by the pre-stated rule (best pooled development log-loss "
                       "gain at the real opener, 2021-22) and committed BEFORE the 2023-26 WNBA test is evaluated.",
            "variant": best,
            "model": {"mean_feats": list(mf), "var_feats": list(vf), "kind": V2["kind"], "shape": V2["shape"],
                      "alpha": V2["alpha"], "min_games": V2["min_games"], "train_decay": 0.6, "calib_decay": 0.6},
            "ratings": RATINGS,
            "dev_evidence": {"ll_gain_x1e4": {k: round(float(v), 1) for k, v in pooled.items()}},
            "products": "config/stage3_locked.yaml (same as NCAAB and NBA)",
            "locked_at_revision": rev}
    LOCK.write_text(yaml.safe_dump(lock, sort_keys=False))
    lines = ["# Stage 3 — WNBA opening-line engine: development (2021, 2022)\n",
             f"Data: {rep['games']} WNBA games 2019-2026 with final scores ({rep['with_open']} with a usable "
             f"opener); box scores matched for {rep['box_matched']:.0%}. Test seasons (2023-26) removed before "
             "fitting. Odds start in 2019, so 2019-20 are training history only.\n",
             "Log-loss gain of each variant's probability over the market-only model at the real opener "
             "(×10⁻⁴; uncalibrated, since calibration needs two earlier predicted seasons and starts in 2023):\n",
             df_to_md(R), "",
             f"**Rule:** choose the variant with the best pooled development gain → **{best}** "
             f"({pooled[best]:+.1f}×10⁻⁴). Locked in `config/stage3_wnba_locked.yaml`.\n"]
    (ROOT / "reports" / "stage3_wnba_dev.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("stage3_wnba_dev", {"variants": list(VARIANTS), "ratings": RATINGS},
                   {"table": R.astype(str).to_dict("records"), "best": best})


if __name__ == "__main__":
    main()
