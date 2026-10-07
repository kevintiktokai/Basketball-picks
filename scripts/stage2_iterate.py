"""Stage-2 iteration harness (DEVELOPMENT seasons only).

usage: python scripts/stage2_iterate.py <iteration-name> [<iteration-name> ...]

Each iteration is a named configuration in ITERATIONS below. Results are logged
to reports/experiments/ and appended to reports/ITERATIONS.md. Holdout seasons
listed in config/stage2.yaml are removed from the data before anything runs.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml

from backtest.analysis import df_to_md
from backtest.wf2 import (buffered_cards, card_summary, leg_table, main_line_probs,
                          walk_forward_market)
from calibration.calibrate import log_loss, wilson
from config_loader import ROOT, log_experiment
from features.ncaab_features import market_frame

S2 = yaml.safe_load((ROOT / "config" / "stage2.yaml").read_text())
NC = S2["ncaab"]["periods"]
DEV = NC["discovery"] + NC["validation"]
HOLD = set(NC["holdout"])

BASE = ["x_pts", "x_eff", "early", "log_games", "abs_spread", "neutral_i", "line_rel"]
RICH = BASE + ["x_poss", "vol_sum", "mkt_bias_sum", "open_bias_sum", "move_hist_sum", "rest_min",
               "weekend", "march", "log_slate", "lg_drift"]
VAR = ["line_rel", "x_poss", "vol_sum", "abs_spread", "early", "log_games", "neutral_i", "log_slate"]

STYLE_M = ["m_efg", "m_tpar", "m_ftr", "m_orb", "m_tovr", "m_pace"]
TT = ["x_home_tt", "x_away_tt", "x_tt_absdiff"]
INTER = ["x_pts_early", "x_poss_early"]
VAR2 = VAR + ["m_tpar", "m_pace", "m_ftr"]

ITERATIONS = {
    # name: (market, mean_feats, var_feats, kind, shape, alpha)
    "it01_open_base":        ("open", BASE, [], "ridge", "normal", 50.0),
    "it02_open_rich":        ("open", RICH, [], "ridge", "normal", 50.0),
    "it03_open_rich_var":    ("open", RICH, VAR, "ridge", "normal", 50.0),
    "it04_open_rich_var_t":  ("open", RICH, VAR, "ridge", "student_t", 50.0),
    "it05_open_lgbm_var":    ("open", RICH, VAR, "lgbm", "normal", 50.0),
    "it06_open_ens_var":     ("open", RICH, VAR, "ensemble", "normal", 50.0),
    "it07_close_rich_var":   ("close", RICH + ["move"], VAR, "ridge", "normal", 50.0),
    "it09_open_rich_var_fix": ("open", RICH, VAR, "ridge", "normal", 50.0),
    "it10_open_style":        ("open", RICH + STYLE_M, VAR2, "ridge", "normal", 50.0),
    "it11_open_style_tt":     ("open", RICH + STYLE_M + TT, VAR2, "ridge", "normal", 50.0),
    "it13_open_style_tt_int": ("open", RICH + STYLE_M + TT + INTER, VAR2, "ridge", "normal", 50.0),
    "it08_2h_var":           ("second_half", ["fh_surplus", "fh_margin_abs", "x_2h_vs_naive",
                                              "x_2h_vs_pregame", "x_pts", "x_eff", "move",
                                              "abs_spread", "early", "line_rel"],
                              ["fh_margin_abs", "abs_spread", "line_rel", "vol_sum"], "ridge", "normal", 50.0),
}


def load_market(market: str, features_file: str = "ncaab_features.parquet") -> pd.DataFrame:
    f = pd.read_parquet(ROOT / "data" / "processed" / features_file)
    f = f[~f.season.isin(HOLD)]                       # holdout physically removed
    return market_frame(f, market)


def evaluate(name: str) -> dict:
    market, mf, vf, kind, shape, alpha = ITERATIONS[name]
    d = load_market(market)
    P, cals, calm = walk_forward_market(d, mf, vf, kind, shape, alpha, seasons=DEV)
    M = main_line_probs(P, cals)
    Pm = P.assign(mu=P.mu_mkt, sd=P.sd_mkt)
    Mm = main_line_probs(Pm, calm)
    e = M[M.eligible & ~M.push]
    em = Mm.set_index("game_key").loc[e.game_key]
    y = e.over.values
    res = {"iteration": name, "market": market, "n_main": int(len(e)),
           "seasons_scored": sorted(e.season.unique()),
           "ll_model": log_loss(e.p_over / (e.p_over + e.p_under), y),
           "ll_market_only": log_loss(em.p_over / (em.p_over + em.p_under), y)}
    res["ll_gain_x1e4"] = (res["ll_market_only"] - res["ll_model"]) * 1e4

    # two-sided pick buckets at the main line
    b = []
    for lo, hi in ((.5, .55), (.55, .6), (.6, .65), (.65, .7), (.7, 1.01)):
        m = e[(e.p_best >= lo) & (e.p_best < hi) & ~e.best_push]
        k, n = int(m.best_win.sum()), len(m)
        b.append({"bucket": f"{lo:.0%}-{min(hi,1):.0%}", "n": n, "pred": m.p_best.mean() if n else np.nan,
                  "win": k / n if n else np.nan, "ci": wilson(k, n)})
    res["buckets"] = b
    res["max_p_best"] = float(e.p_best.max())

    # forced main-line pair: top-2 two-sided picks per date
    f2 = []
    for date, day in e.groupby("date"):
        if len(day) < 2:
            continue
        t = day.nlargest(2, "p_best")
        f2.append({"season": t.season.iloc[0], "w": int(t.best_win.all() and not t.best_push.any()),
                   "joint": float(t.p_best.prod())})
    f2 = pd.DataFrame(f2)
    res["forced_main_pair"] = {"cards": len(f2), "rate_2of2": float(f2.w.mean()),
                               "ci": wilson(int(f2.w.sum()), len(f2)), "avg_joint_model": float(f2.joint.mean())}

    # dependence among same-day games
    z = (P.resid - P.mu) / P.sd
    zz = P.assign(z=z)[P.eligible]
    prs = []
    for date, day in zz.groupby("date"):
        v = day.z.values
        if len(v) >= 2:
            i, j = np.triu_indices(len(v), 1)
            prs.append(np.column_stack([v[i], v[j]]))
    prs = np.vstack(prs)
    res["same_day_z_corr"] = float(np.corrcoef(prs[:, 0], prs[:, 1])[0, 1])

    # buffered cards
    T = leg_table(P, cals, calm)
    out = {}
    for mode, gate, margin in (("hit_rate", False, 0.0455), ("value_4.5pct", True, 0.0455),
                               ("value_8pct", True, 0.08)):
        C = buffered_cards(T, value_gate=gate, margin=margin)
        per = {}
        for pname, seas in (("discovery", NC["discovery"]), ("validation", NC["validation"])):
            per[pname] = card_summary(C[C.season.isin(seas)])
        out[mode] = per
        if mode == "hit_rate":
            C.to_csv(ROOT / "reports" / f"dev_cards_{name}.csv", index=False)
    res["buffered"] = out
    return res


def to_markdown(r: dict) -> str:
    lines = [f"### {r['iteration']} — market `{r['market']}`\n",
             f"Main-line log loss (non-push, calibrated): model {r['ll_model']:.5f} vs market-only "
             f"{r['ll_market_only']:.5f} → gain {r['ll_gain_x1e4']:+.1f}×10⁻⁴ over {r['n_main']} games "
             f"({r['seasons_scored'][0]}..{r['seasons_scored'][-1]}). Max two-sided P at the main line: "
             f"{r['max_p_best']:.1%}. Same-day error correlation: {r['same_day_z_corr']:+.4f}.\n",
             df_to_md(pd.DataFrame(r["buckets"])), "",
             f"Forced main-line pair (top-2 per slate): {r['forced_main_pair']['cards']} cards, "
             f"2/2 = {r['forced_main_pair']['rate_2of2']:.1%} (CI {r['forced_main_pair']['ci'][0]:.1%}–"
             f"{r['forced_main_pair']['ci'][1]:.1%}).\n"]
    rows = []
    for mode, per in r["buffered"].items():
        for pname, s in per.items():
            rows.append({"mode": mode, "period": pname, "cards": s.get("cards"),
                         "pct_slates": s.get("pct_slates_with_card"), "rate_2of2": s.get("rate_2of2"),
                         "ci95": s.get("ci95"), "avg_buffer_pts": s.get("avg_buffer"),
                         "leg_win": s.get("leg_win_rate"), "avg_leg_p": s.get("avg_leg_p"),
                         "dbl_odds": s.get("avg_double_odds"), "roi_double": s.get("roi_double"),
                         "model_ev": s.get("avg_model_ev")})
    lines.append("Buffered (alternate-line) cards:\n")
    lines.append(df_to_md(pd.DataFrame(rows)))
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    log = ROOT / "reports" / "ITERATIONS.md"
    if not log.exists():
        log.write_text("# Stage-2 iteration journal (development seasons only)\n\n"
                       "Every configuration tried is recorded here, including failures.\n\n")
    for name in sys.argv[1:]:
        r = evaluate(name)
        md = to_markdown(r)
        print(md)
        with open(log, "a") as fh:
            fh.write(md + "\n")
        log_experiment(f"stage2_{name}", {"iteration": name, "config": [str(x) for x in ITERATIONS[name]]}, r)
