"""DEVELOPMENT research run (discovery + validation seasons ONLY).

Produces:
  reports/development_report.md
  config/locked_model.yaml        (model spec frozen for the one-time holdout run)
  reports/experiments/*.json      (reproducibility records)

The holdout seasons are never predicted by this script.
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

from backtest.analysis import (bet_summary, bucket_table, df_to_md, failure_analysis,
                               fmt_pct, monte_carlo_cards, monte_carlo_singles,
                               paired_logloss_gain)
from backtest.cards import SelectionParams, card_metrics
from backtest.dependence import dependence_summary, required_individual_probability, same_day_pairs
from backtest.engine import forced_best_pair, run_engine
from backtest.walkforward import load_features, walk_forward
from calibration.calibrate import brier, ece, log_loss, reliability_table, wilson
from config_loader import ROOT, load_config, log_experiment
from models.total_models import FEATURE_SETS, needs_box

CFG = load_config()
DISC, VAL = CFG["periods"]["discovery"], CFG["periods"]["validation"]
OUT = []


def h(s):
    OUT.append(s)
    print(s)


def main():
    df = load_features()
    for s in CFG["periods"]["holdout"] + CFG["periods"]["live_sim"]:
        assert s not in DISC + VAL
    df_dev = df[df.season.isin(DISC + VAL)]
    h("# OVER ENGINE — Development report (discovery + validation only)\n")
    h(f"Dataset `{CFG['dataset_version']}`. Holdout seasons {CFG['periods']['holdout']} and "
      f"live-sim seasons {CFG['periods']['live_sim']} were NOT predicted by this run.\n")

    # ------------------------------------------------------------ dataset
    h("## 1. Dataset\n")
    tab = df_dev.groupby("season").agg(games=("game_id", "size"), over_rate=("over", "mean"),
                                       push_rate=("push", "mean"), mean_line=("line", "mean"),
                                       resid_sd=("resid", "std"),
                                       line_mae=("resid", lambda r: r.abs().mean())).reset_index()
    h(df_to_md(tab, "{:.3f}"))
    h("\nThe closing total is an extremely strong predictor: mean absolute error ≈14 points, "
      "residual SD ≈17–19, Over rate within a few points of 50% every season.\n")

    # ------------------------------------------------------ model comparison
    h("## 2. Model comparison and ablation (walk-forward, season refit)\n")
    grid = []
    for fs in FEATURE_SETS:
        kinds = ["mean"] if fs == "F0_market_only" else ["ridge", "lgbm", "ensemble"]
        for k in kinds:
            grid.append((fs, k))
    preds = {}
    for fs, k in grid:
        preds[(fs, k, "normal", "platt")] = walk_forward(df, fs, k, "normal", "platt", "development")
    # distribution and calibration variants for the score-only ridge model
    for dist, cal in [("empirical", "platt"), ("normal", "isotonic"), ("normal", "none")]:
        preds[("S_scores_full", "ridge", dist, cal)] = walk_forward(
            df, "S_scores_full", "ridge", dist, cal, "development")
    for dist, cal in [("normal", "isotonic"), ("normal", "none")]:
        preds[("F8_trends", "ridge", dist, cal)] = walk_forward(
            df, "F8_trends", "ridge", dist, cal, "development")

    common = None
    for p in preds.values():
        ids = set(p[p.calibrated & p.eligible_data & ~p.push].game_id)
        common = ids if common is None else common & ids
    base = preds[("F0_market_only", "mean", "normal", "platt")].set_index("game_id").loc[sorted(common)]
    rows = []
    for key, p in preds.items():
        e = p.set_index("game_id").loc[sorted(common)]
        y = e.over.values
        gain, ci = paired_logloss_gain(e.p_cal.values, base.p_cal.values, y, e.date.values, 500)
        rows.append({"features": key[0], "learner": key[1], "dist": key[2], "calib": key[3],
                     "n": len(e), "logloss": log_loss(e.p_cal, y),
                     "gain_vs_mkt_x1e4": gain * 1e4, "gain_ci_x1e4": (ci[0] * 1e4, ci[1] * 1e4),
                     "brier": brier(e.p_cal, y), "ece": ece(e.p_cal, y),
                     "rmse_resid": float(np.sqrt(np.mean((e.resid - e.mu_resid) ** 2))),
                     "max_p_cal": float(e.p_cal.max()),
                     "n_p>=0.55": int((e.p_cal >= .55).sum()),
                     "win_p>=0.55": float(e.over[e.p_cal >= .55].mean()) if (e.p_cal >= .55).any() else np.nan})
    comp = pd.DataFrame(rows).sort_values("logloss").reset_index(drop=True)
    seasons_common = sorted(set(base.season))
    h(f"Common evaluation sample: {len(common)} games (calibrated, ≥5 games played, non-push) "
      f"in seasons {seasons_common[0]}..{seasons_common[-1]} — the seasons where every model "
      f"(including box-score models) has a calibrated walk-forward prediction.\n")
    h("`gain_vs_mkt` = mean per-bet log-loss improvement over the market-only model (×10⁻⁴), "
      "95% CI from a date-clustered bootstrap. A coin flip has log loss 0.6931.\n")
    h(df_to_md(comp, "{:.4f}"))

    # ------------------------------------------------------- lock rule
    # Pre-stated rule: among models with a positive gain CI lower bound, choose the one
    # with the best log loss; if a score-only model is within one bootstrap SE of it,
    # prefer the score-only model (usable in every season incl. live-sim). If no model
    # has a positive lower bound, still lock the best score-only model but record that
    # the evidence for any edge is not significant.
    comp["se"] = (comp.gain_ci_x1e4.apply(lambda c: c[1] - c[0])) / (2 * 1.96)
    comp["ci_lo"] = comp.gain_ci_x1e4.apply(lambda c: c[0])
    sig = comp[comp.ci_lo > 0]
    score_only = comp[~comp.features.apply(needs_box) & (comp.features != "F0_market_only")]
    if len(sig):
        best = sig.iloc[0]
        so = score_only[(score_only.gain_vs_mkt_x1e4 >= best.gain_vs_mkt_x1e4 - best.se)
                        & (score_only.ci_lo > 0)]
        chosen = so.iloc[0] if len(so) else best
        significant = bool(chosen.ci_lo > 0)
    else:
        chosen = score_only.iloc[0]
        significant = False
    h(f"\n**Locked model (pre-stated rule):** features `{chosen.features}`, learner "
      f"`{chosen.learner}`, distribution `{chosen.dist}`, calibration `{chosen.calib}`. "
      f"Gain vs market {chosen.gain_vs_mkt_x1e4:.1f}×10⁻⁴ "
      f"(95% CI {chosen.gain_ci_x1e4[0]:.1f}..{chosen.gain_ci_x1e4[1]:.1f}); "
      f"{'statistically distinguishable from the market' if significant else 'NOT distinguishable from the market'}.\n")
    h("_Disclosure: the first development run applied the score-only preference without the "
      "positive-lower-bound requirement stated in the rule and locked an uncalibrated variant "
      "(gain CI −2.5..23.1). That implementation bug was fixed to match the stated rule before "
      "any holdout evaluation; no thresholds were changed._\n")

    # ablation ladder (ridge) in words
    h("### Ablation ladder (ridge, normal, Platt)\n")
    lad = comp[(comp.learner == "ridge") & (comp.dist == "normal") & (comp.calib == "platt")
               & comp.features.str.startswith("F")]
    lad = pd.concat([comp[comp.features == "F0_market_only"], lad]).drop_duplicates("features")
    lad = lad.set_index("features").loc[[f for f in FEATURE_SETS if f.startswith("F")]].reset_index()
    h(df_to_md(lad[["features", "logloss", "gain_vs_mkt_x1e4", "gain_ci_x1e4", "rmse_resid",
                    "max_p_cal"]], "{:.4f}"))
    h("")

    lock = {"feature_set": chosen.features, "learner": chosen.learner, "dist": chosen.dist,
            "calib": chosen.calib}
    P = preds[(lock["feature_set"], lock["learner"], lock["dist"], lock["calib"])]
    P = P[P.season.isin(DISC + VAL)]
    ev = P[P.calibrated & P.eligible_data]

    # --------------------------------------------------------- calibration
    h("## 3. Calibration of the locked model (all calibrated development games)\n")
    s = ev[~ev.push]
    h(f"Brier {brier(s.p_cal, s.over):.4f}, log loss {log_loss(s.p_cal, s.over):.4f}, "
      f"ECE {ece(s.p_cal, s.over):.4f}, n={len(s)}.\n")
    h(df_to_md(reliability_table(s.p_cal.values, s.over.values), "{:.3f}"))
    h("")

    # ---------------------------------------------------------- buckets
    h("## 4. Bet buckets (every calibrated game treated as a 1u Over bet at 1.909)\n")
    h("### Probability buckets\n")
    h(df_to_md(bucket_table(ev, "p_cal", [0, .50, .55, .60, .65, .70, .75, 1.01],
                            ["<50%", "50–54", "55–59", "60–64", "65–69", "70–74", "75%+"])))
    ev = ev.assign(edge=ev.proj_total - ev.line)
    h("\n### Projection edge buckets (model total − line, points)\n")
    h(df_to_md(bucket_table(ev, "edge", [-99, 0, 1, 2, 3, 4, 5, 99],
                            ["<0", "0–1", "1–2", "2–3", "3–4", "4–5", "5+"])))
    h("\n### Line ranges (NBA scale)\n")
    h(df_to_md(bucket_table(ev, "line", [0, 200, 210, 220, 230, 240, 400],
                            ["<200", "200–209.5", "210–219.5", "220–229.5", "230–239.5", "240+"])))
    h("\n### Season phase (games already played by the less-experienced team)\n")
    ph = ev.assign(phase=np.select(
        [ev.is_postseason, ev.min_games_season < 10, ev.min_games_season < 30, ev.min_games_season < 60],
        [4, 1, 2, 3], 5))
    h(df_to_md(bucket_table(ph, "phase", [1, 2, 3, 4, 5, 6],
                            ["5–9 games", "10–29", "30–59", "playoffs/play-in", "60+ (late)"])))
    h("\n### Stability by season — Overs with calibrated P ≥ 55%\n")
    st = []
    for sea, g in ev.groupby("season"):
        b = bet_summary(g[g.p_cal >= .55])
        st.append({"season": sea, "period": "discovery" if sea in DISC else "validation",
                   "bets": b["bets"], "win": b.get("win_rate"), "roi": b.get("roi")})
    h(df_to_md(pd.DataFrame(st)))
    h("")

    # ----------------------------------------------------------- dependence
    h("## 5. Dependence between same-slate games\n")
    pairs = same_day_pairs(P[P.eligible_data])
    dep = dependence_summary(pairs, n_boot=300)
    h(f"Same-day pairs: {dep['n_pairs']} over {dep['n_dates']} dates.\n")
    h(f"* Correlation of Over outcomes: {dep['over_corr']:.4f} (95% CI {dep['over_corr_ci'][0]:.4f}..{dep['over_corr_ci'][1]:.4f})")
    h(f"* Correlation of standardized model errors: {dep['z_corr']:.4f} (95% CI {dep['z_corr_ci'][0]:.4f}..{dep['z_corr_ci'][1]:.4f})")
    h(f"* P(both Over) − P(Over)²: {dep['joint_minus_product']:+.4f} (95% CI {dep['jmp_ci'][0]:+.4f}..{dep['jmp_ci'][1]:+.4f})\n")
    rho = dep["z_corr"]
    req = {r: required_individual_probability(.60, r) for r in (0.0, rho, 0.05, 0.10)}
    h("Individual probability each pick needs for P(both) = 60% (Gaussian copula):\n")
    for r, p in req.items():
        h(f"* rho = {r:.3f}: **{p:.1%}** per pick")
    h(f"\nThe highest calibrated P(Over) the locked model produced on any development game "
      f"was {ev.p_cal.max():.1%}; {int((ev.p_cal >= req[rho]).sum())} games reached "
      f"the {req[rho]:.1%} needed.\n")

    # ----------------------------------------------------------- card engine
    h("## 6. Two-pick card engine — direct backtest (development)\n")
    sp = SelectionParams(joint_target=CFG["selection"]["joint_target"])
    slates, picks = run_engine(P, sp, DISC + VAL)
    for name, seas in (("DISCOVERY", DISC), ("VALIDATION", VAL)):
        m = card_metrics(slates[slates.season.isin(seas)])
        h(f"**{name}** — slates {m['slates']}: TWO-PICK CARD {fmt_pct(m['pct_two_pick'])}, "
          f"ONE QUALIFYING PICK {fmt_pct(m['pct_one_pick'])}, NO BET {fmt_pct(m['pct_no_bet'])}; "
          f"two-pick cards: {m['two_pick_cards']}"
          + (f", 2/2 {m['cards_2of2']} ({fmt_pct(m['rate_2of2'])}, CI {fmt_pct(m['ci95'][0])}–{fmt_pct(m['ci95'][1])})"
             if m["two_pick_cards"] else "") + "\n")
    h(f"Closest pair, conservative joint probability: median {slates.closest_pair_joint_cons.median():.1%}, "
      f"max {slates.closest_pair_joint_cons.max():.1%} (target 60%).\n")
    singles = picks[picks.role == "ONE QUALIFYING PICK"] if len(picks) else pd.DataFrame()
    h("### Single-pick standard (separately defined: conservative P ≥ 52.38% break-even)\n")
    if len(singles):
        sp_res = singles.assign(over=(singles.result == "W").astype(int), push=singles.result == "P")
        for name, seas in (("discovery", DISC), ("validation", VAL)):
            b = bet_summary(sp_res[sp_res.season.isin(seas)])
            h(f"* {name}: {b['bets']} picks, win {fmt_pct(b.get('win_rate'))}, ROI {fmt_pct(b.get('roi'))}")
    else:
        h("* No single pick met the standard in development.")
    h("")

    # ------------------------------------------------------ diagnostics
    h("## 7. Diagnostics (NOT the engine): what if cards were forced?\n")
    h("Each slate, the two highest-probability Overs among games with calibrated P ≥ threshold. "
      "This measures the ceiling of 2/2 rates available from this model.\n")
    diag = []
    for t in (0.0, 0.50, 0.52, 0.54, 0.56, 0.58, 0.60):
        fb = forced_best_pair(P, rho, t)
        for name, seas in (("discovery", DISC), ("validation", VAL)):
            f = fb[fb.season.isin(seas)] if len(fb) else fb
            n = len(f)
            k = int(f.card_2of2.sum()) if n else 0
            lo, hi = wilson(k, n)
            diag.append({"min_p": t, "period": name, "cards": n, "rate_2of2": k / n if n else np.nan,
                         "ci95": (lo, hi), "avg_joint_cal": f.joint_cal.mean() if n else np.nan,
                         "roi_double": f.double_profit.mean() if n else np.nan})
    h(df_to_md(pd.DataFrame(diag)))
    fb0 = forced_best_pair(P, rho, 0.0)
    mc = monte_carlo_cards(fb0.card_2of2.values, fb0.double_profit.values, months=6)
    h(f"\nMonte Carlo of the forced nightly double (6 months): expected ROI {fmt_pct(mc['expected_roi'])} "
      f"(5–95%: {fmt_pct(mc['roi_p5_p95'][0])}..{fmt_pct(mc['roi_p5_p95'][1])}), "
      f"P(losing month) {mc['p_losing_month']:.1%}, median max drawdown {mc['median_max_drawdown']:.1f}u.\n")
    top = ev[ev.p_cal >= .55]
    mcs = monte_carlo_singles(np.where(top.push, 0, np.where(top.over == 1, .909, -1.0)))
    if mcs:
        h(f"Monte Carlo of 200 single Overs with P ≥ 55%: expected ROI {fmt_pct(mcs['expected_roi'])} "
          f"(5–95% {fmt_pct(mcs['roi_p5_p95'][0])}..{fmt_pct(mcs['roi_p5_p95'][1])}), "
          f"P(10-loss streak) {mcs['p_10_loss_streak']:.1%}.\n")

    # ------------------------------------------------- lessons (Section 45)
    h("## 8. Lessons from the old manual system (Section 45), tested\n")
    def gain_of(a, b):
        ka = (a, "mean" if a == "F0_market_only" else "ridge", "normal", "platt")
        kb = (b, "mean" if b == "F0_market_only" else "ridge", "normal", "platt")
        r = comp.set_index(["features", "learner", "dist", "calib"])
        return r.loc[ka].gain_vs_mkt_x1e4 - r.loc[kb].gain_vs_mkt_x1e4
    h(f"* Recent raw scoring (naive PPG, F1) vs market only: {gain_of('F1_naive_ppg','F0_market_only'):+.1f}×10⁻⁴ log-loss gain.")
    h(f"* Adding team Over/Under trends (F8 vs F7): {gain_of('F8_trends','F7_context'):+.1f}×10⁻⁴.")
    h(f"* Opponent-adjusted ratings over naive PPG (F2 vs F1): {gain_of('F2_ratings','F1_naive_ppg'):+.1f}×10⁻⁴.")
    e34 = ev[(ev.edge >= 3) & (ev.edge < 4)]
    b34 = bet_summary(e34)
    h(f"* 'A 3–4 point projection edge is enough': {b34['bets']} such Overs won "
      f"{fmt_pct(b34.get('win_rate'))} (CI {fmt_pct(b34['win_ci95'][0])}–{fmt_pct(b34['win_ci95'][1])}), ROI {fmt_pct(b34.get('roi'))}.")
    bl = ev.assign(big_fav=ev.abs_spread >= 10)
    for flag, g in bl.groupby("big_fav"):
        b = bet_summary(g)
        h(f"* Blowout risk — |spread| {'≥' if flag else '<'} 10: Over win {fmt_pct(b['win_rate'])} over {b['bets']} games.")
    h(f"* H2H: no reliable head-to-head feature was built separately; team O/U trend is the closest proxy and is tested above.\n")

    # ----------------------------------------------------- red team
    h("## 9. Red-team\n")
    rt = []
    feats = FEATURE_SETS[lock["feature_set"]]
    base_ll = log_loss(s.p_cal, s.over)
    for drop in feats:
        alt = [f for f in feats if f != drop]
        FEATURE_SETS["_tmp"] = alt
        q = walk_forward(df, "_tmp", lock["learner"], lock["dist"], lock["calib"], "development")
        q = q.set_index("game_id").loc[s.game_id]
        rt.append({"test": f"remove {drop}", "logloss": log_loss(q.p_cal, s.over.values),
                   "delta_x1e4": (log_loss(q.p_cal, s.over.values) - base_ll) * 1e4})
    # randomized feature: replace main signal with within-season permutation
    rng = np.random.default_rng(7)
    dfr = df.copy()
    dfr["x_rating"] = dfr.groupby("season").x_rating.transform(lambda x: rng.permutation(x.values))
    FEATURE_SETS["_tmp"] = feats
    q = walk_forward(dfr, "_tmp", lock["learner"], lock["dist"], lock["calib"], "development")
    q = q.set_index("game_id").loc[s.game_id]
    rt.append({"test": "permute x_rating within season", "logloss": log_loss(q.p_cal, s.over.values),
               "delta_x1e4": (log_loss(q.p_cal, s.over.values) - base_ll) * 1e4})
    for mg in (3, 10, 20):
        q = walk_forward(df, lock["feature_set"], lock["learner"], lock["dist"], lock["calib"],
                         "development", min_games=mg)
        e = q[q.calibrated & q.eligible_data & ~q.push]
        rt.append({"test": f"min games {mg}", "logloss": log_loss(e.p_cal, e.over),
                   "delta_x1e4": np.nan})
    FEATURE_SETS.pop("_tmp", None)
    h(df_to_md(pd.DataFrame(rt), "{:.4f}"))
    h("\nPositive delta = worse without the feature.\n")

    # ------------------------------------------------- failure analysis
    h("## 10. Failure analysis (losing Overs with calibrated P ≥ 55%)\n")
    box = pd.read_parquet(ROOT / "data" / "processed" / "team_box.parquet")
    losers = ev[(ev.p_cal >= .55) & (ev.over == 0) & ~ev.push]
    fa = failure_analysis(losers, box)
    if len(fa):
        h(df_to_md(fa.category.value_counts().rename_axis("category").reset_index()))
        h(f"\nMean total error {fa.error.mean():+.1f} pts; mean pace error "
          f"{fa.pace_error_poss.mean():+.1f} poss; mean efficiency error "
          f"{fa.efficiency_error_pts_per100.mean():+.1f} pts/100 (box seasons only).\n")
        fa.to_csv(ROOT / "reports" / "dev_failure_analysis.csv", index=False)

    # --------------------------------------------------------- write lock
    lock_doc = {
        "locked_at_revision": None,
        "rule": "best calibrated log loss among models with positive gain CI; prefer score-only within 1 SE",
        "model": lock,
        "selection": {"joint_target": sp.joint_target, "individual_floor": sp.individual_floor,
                      "single_cons_min": sp.single_cons_min, "min_edge_points": sp.min_edge_points,
                      "conservative_quantile": CFG["selection"]["conservative_quantile"]},
        "edge_significant_in_development": significant,
        "dependence_dev": {"z_corr": float(rho), "z_corr_ci": [float(x) for x in dep["z_corr_ci"]]},
    }
    from config_loader import git_revision
    lock_doc["locked_at_revision"] = git_revision()
    (ROOT / "config" / "locked_model.yaml").write_text(yaml.safe_dump(lock_doc, sort_keys=False))
    (ROOT / "reports" / "development_report.md").write_text("\n".join(OUT) + "\n")
    log_experiment("development", {"lock": lock, "selection": lock_doc["selection"]},
                   {"model_comparison": comp.drop(columns=["gain_ci_x1e4"]).to_dict("records"),
                    "dependence": dep, "required_p": {str(k): v for k, v in req.items()},
                    "forced_diag": diag})


if __name__ == "__main__":
    main()
