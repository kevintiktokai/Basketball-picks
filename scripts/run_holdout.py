"""ONE-TIME final holdout + live-simulated evaluation of the LOCKED model.

Refuses to run if a holdout report already exists: the holdout may be looked
at exactly once. Uses config/locked_model.yaml only; no parameter here may be
tuned. Walk-forward continues through the holdout (each holdout season's model
is fitted on all earlier seasons, exactly as it would have been live).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warnings

import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore")

from backtest.analysis import (bet_summary, bucket_table, df_to_md, failure_analysis, fmt_pct,
                               monte_carlo_singles)
from backtest.cards import SelectionParams, card_metrics
from backtest.dependence import dependence_summary, required_individual_probability, same_day_pairs
from backtest.engine import forced_best_pair, run_engine
from backtest.walkforward import load_features, walk_forward
from calibration.calibrate import brier, ece, log_loss, reliability_table, wilson
from config_loader import ROOT, load_config, log_experiment

CFG = load_config()
REPORT = ROOT / "reports" / "holdout_report.md"
OUT = []


def h(s=""):
    OUT.append(s)
    print(s)


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT} exists. The holdout is evaluated once only.")
    lock = yaml.safe_load((ROOT / "config" / "locked_model.yaml").read_text())
    m = lock["model"]
    sel = lock["selection"]
    per = CFG["periods"]
    HOLD, LIVE, DEV = per["holdout"], per["live_sim"], per["discovery"] + per["validation"]

    df = load_features()
    P = walk_forward(df, m["feature_set"], m["learner"], m["dist"], m["calib"], "live_sim")
    P.to_parquet(ROOT / "data" / "processed" / "predictions_locked.parquet", index=False)

    h("# OVER ENGINE — Final holdout and live-simulated report\n")
    h(f"Locked model: `{m}` (locked at revision `{lock['locked_at_revision']}`). "
      f"Selection: `{sel}`. Holdout {HOLD}; live-sim {LIVE}. Run once.\n")

    sp = SelectionParams(joint_target=sel["joint_target"], individual_floor=sel["individual_floor"],
                         single_cons_min=sel["single_cons_min"], min_edge_points=sel["min_edge_points"])
    slates, picks = run_engine(P, sp, DEV + HOLD + LIVE)
    summary = {}
    h("## 1. Card engine — slate outcomes by stage\n")
    rows = []
    for name, seas in (("DISCOVERY", per["discovery"]), ("VALIDATION", per["validation"]),
                       ("FINAL HOLDOUT", HOLD), ("LIVE-SIMULATED", LIVE)):
        cm = card_metrics(slates[slates.season.isin(seas)])
        summary[name] = cm
        rows.append({"stage": name, "slates": cm["slates"], "two_pick_cards": cm["two_pick_cards"],
                     "pct_card": cm["pct_two_pick"], "pct_one_pick": cm["pct_one_pick"],
                     "pct_no_bet": cm["pct_no_bet"],
                     "rate_2of2": cm.get("rate_2of2", np.nan), "ci95": cm.get("ci95", (np.nan, np.nan))})
    h(df_to_md(pd.DataFrame(rows)))
    hs = slates[slates.season.isin(HOLD)]
    h(f"\nHoldout closest pair, conservative joint probability: median "
      f"{hs.closest_pair_joint_cons.median():.1%}, max {hs.closest_pair_joint_cons.max():.1%} (target 60%).\n")

    singles = picks[picks.role == "ONE QUALIFYING PICK"] if len(picks) else pd.DataFrame()
    h("## 2. Single-pick standard (reported separately, never mixed with cards)\n")
    if len(singles):
        sres = singles.assign(over=(singles.result == "W").astype(int), push=singles.result == "P")
        for name, seas in (("holdout", HOLD), ("live-sim", LIVE)):
            b = bet_summary(sres[sres.season.isin(seas)])
            h(f"* {name}: {b}")
    else:
        h("* No single pick met the standard in any stage.\n")

    ev = P[P.calibrated & P.eligible_data]
    h("## 3. Individual-probability calibration, holdout\n")
    for name, seas in (("FINAL HOLDOUT", HOLD), ("LIVE-SIMULATED", LIVE)):
        s = ev[ev.season.isin(seas) & ~ev.push]
        h(f"**{name}** n={len(s)}: Brier {brier(s.p_cal, s.over):.4f}, log loss {log_loss(s.p_cal, s.over):.4f} "
          f"(coin flip 0.6931), ECE {ece(s.p_cal, s.over):.4f}, max P {s.p_cal.max():.1%}\n")
        h(df_to_md(reliability_table(s.p_cal.values, s.over.values)))
        h()

    h("## 4. Holdout bet buckets (each calibrated game as a 1u Over at 1.909)\n")
    eh = ev[ev.season.isin(HOLD)].assign(edge=lambda d: d.proj_total - d.line)
    h(df_to_md(bucket_table(eh, "p_cal", [0, .50, .55, .60, .65, .70, .75, 1.01],
                            ["<50%", "50–54", "55–59", "60–64", "65–69", "70–74", "75%+"])))
    h()
    h(df_to_md(bucket_table(eh, "edge", [-99, 0, 1, 2, 3, 4, 5, 99],
                            ["<0", "0–1", "1–2", "2–3", "3–4", "4–5", "5+"])))
    h()
    top = eh[eh.p_cal >= .55]
    b = bet_summary(top)
    h(f"Holdout Overs with calibrated P ≥ 55% (pre-declared diagnostic threshold): {b}\n")
    mcs = monte_carlo_singles(np.where(top.push, 0, np.where(top.over == 1, .909, -1.0)))
    if mcs:
        h(f"Monte Carlo (200 such bets): {mcs}\n")

    h("## 5. Dependence in the holdout\n")
    dep = dependence_summary(same_day_pairs(P[P.season.isin(HOLD) & P.eligible_data]), n_boot=300)
    h(f"Same-day pairs {dep['n_pairs']}: Over-outcome corr {dep['over_corr']:.4f} "
      f"(CI {dep['over_corr_ci'][0]:.4f}..{dep['over_corr_ci'][1]:.4f}); error corr {dep['z_corr']:.4f} "
      f"(CI {dep['z_corr_ci'][0]:.4f}..{dep['z_corr_ci'][1]:.4f}); joint−product {dep['joint_minus_product']:+.4f}.\n")
    h(f"Required individual P for 60% joint at holdout rho: "
      f"{required_individual_probability(.6, dep['z_corr']):.1%}.\n")

    h("## 6. Diagnostics (NOT the engine): forced nightly top-2 Overs\n")
    diag = []
    for t in (0.0, 0.50, 0.52, 0.54, 0.56):
        fb = forced_best_pair(P, lock["dependence_dev"]["z_corr"], t)
        for name, seas in (("FINAL HOLDOUT", HOLD), ("LIVE-SIMULATED", LIVE)):
            f = fb[fb.season.isin(seas)] if len(fb) else fb
            n = len(f)
            k = int(f.card_2of2.sum()) if n else 0
            diag.append({"min_p": t, "stage": name, "cards": n, "rate_2of2": k / n if n else np.nan,
                         "ci95": wilson(k, n), "avg_joint_cal": f.joint_cal.mean() if n else np.nan,
                         "roi_double": f.double_profit.mean() if n else np.nan})
    h(df_to_md(pd.DataFrame(diag)))
    h()

    h("## 7. Failure analysis — holdout losing Overs with P ≥ 55%\n")
    box = pd.read_parquet(ROOT / "data" / "processed" / "team_box.parquet")
    fa = failure_analysis(top[(top.over == 0) & ~top.push], box)
    if len(fa):
        h(df_to_md(fa.category.value_counts().rename_axis("category").reset_index()))
        fa.to_csv(ROOT / "reports" / "holdout_failure_analysis.csv", index=False)
    h()

    REPORT.write_text("\n".join(OUT) + "\n")
    slates.to_csv(ROOT / "reports" / "card_engine_slates.csv", index=False)
    log_experiment("holdout", {"lock": lock}, {"stages": summary, "dependence_holdout": dep,
                                               "forced_diag": diag})


if __name__ == "__main__":
    main()
