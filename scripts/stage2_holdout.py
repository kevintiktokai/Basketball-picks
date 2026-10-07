"""ONE-TIME evaluation of the locked stage-2 engine on the NCAAB holdout
(2018-19, 2019-20, 2020-21). Refuses to run twice. Uses config/stage2_locked.yaml
only — nothing here is tunable.
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

REPORT = ROOT / "reports" / "stage2_holdout_report.md"
OUT = []


def h(s=""):
    OUT.append(s)
    print(s)


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT} exists — the stage-2 holdout is evaluated once only.")
    lock = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())
    s2 = yaml.safe_load((ROOT / "config" / "stage2.yaml").read_text())["ncaab"]["periods"]
    DEV, HOLD = s2["discovery"] + s2["validation"], s2["holdout"]
    m, cp = lock["model"], lock["card_policy"]

    f = pd.read_parquet(ROOT / "data" / "processed" / "ncaab_features.parquet")
    d = market_frame(f, lock["market"])
    P, cals, calm = walk_forward_market(d, m["mean_feats"], m["var_feats"], m["kind"], m["shape"],
                                        m["alpha"], seasons=DEV + HOLD, min_games=m["min_games"])
    T = leg_table(P, cals, calm)
    C = buffered_cards(T, joint_target=cp["joint_target"], max_buffer=cp["max_buffer_points"],
                       top_legs=cp["top_legs"], rho_lo=cp["rho_lo"])
    C.to_csv(ROOT / "reports" / "stage2_cards_all_seasons.csv", index=False)

    h("# Stage 2 — NCAAB holdout report (locked engine, run once)\n")
    h(f"Locked at revision `{lock['locked_at_revision']}`; market `{lock['market']}`; model "
      f"`{m['iteration']}`; card policy: buffered lines, conservative joint ≥ {cp['joint_target']}, "
      f"max buffer {cp['max_buffer_points']} pts.\n")

    h("## 1. Two-pick card results by stage\n")
    rows = []
    for name, seas in (("DEVELOPMENT (disc+val)", DEV), ("FINAL HOLDOUT 2018-21", HOLD)):
        s = card_summary(C[C.season.isin(seas)])
        rows.append({"stage": name, "slates": s["slates"], "cards": s.get("cards"),
                     "2of2": int(round(s.get("rate_2of2", 0) * s.get("cards", 0))) if s.get("cards") else 0,
                     "rate_2of2": s.get("rate_2of2"), "ci95": s.get("ci95"),
                     "leg_win": s.get("leg_win_rate"), "avg_leg_p": s.get("avg_leg_p"),
                     "model_joint": s.get("avg_joint_model"), "avg_buffer": s.get("avg_buffer"),
                     "dbl_odds": s.get("avg_double_odds"), "roi_open_px": s.get("roi_double"),
                     "roi_close_px": s.get("roi_double_close_priced")})
    h(df_to_md(pd.DataFrame(rows)))
    h()
    h("### Holdout by season\n")
    rows = []
    for season in HOLD:
        c = C[(C.season == season) & (C.released == True)]  # noqa: E712
        n = len(c)
        k = int(c.card_2of2.sum())
        lo, hi = wilson(k, n)
        rows.append({"season": season, "cards": n, "2of2": k, "1of2": int(((c.win_a + c.win_b) == 1).sum()),
                     "0of2": int(((c.win_a + c.win_b) == 0).sum()), "rate_2of2": k / n if n else np.nan,
                     "ci95": (lo, hi), "model_joint": c.joint_model.mean(),
                     "roi_open_px_4.5%": c.profit_double.mean(),
                     "roi_close_px_4.5%": c.profit_double_close.mean()})
    h(df_to_md(pd.DataFrame(rows)))
    h()

    HC = C[C.season.isin(HOLD) & (C.released == True)]  # noqa: E712
    wa, wb = HC.win_a.astype(float), HC.win_b.astype(float)
    h(f"Leg independence in holdout cards: leg A {wa.mean():.1%}, leg B {wb.mean():.1%}, "
      f"product {wa.mean() * wb.mean():.1%}, actual 2/2 {(wa * wb).mean():.1%}, outcome corr "
      f"{np.corrcoef(wa, wb)[0, 1]:+.3f}.\n")
    for name, msk in (("both Over", (HC.side_a == 1) & (HC.side_b == 1)),
                      ("both Under", (HC.side_a == -1) & (HC.side_b == -1)),
                      ("mixed", HC.side_a != HC.side_b)):
        c = HC[msk]
        h(f"* {name}: {len(c)} cards, 2/2 {c.card_2of2.mean():.1%}")
    h()
    # streaks / drawdown of the double under open pricing
    prof = HC.sort_values("date").profit_double.values
    eq = np.cumsum(prof)
    dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    miss = (HC.sort_values("date").card_2of2.values == 0)
    best = cur = 0
    for x in miss:
        cur = cur + 1 if x else 0
        best = max(best, cur)
    h(f"Longest run of non-2/2 cards: {best}. Max drawdown of the 1-unit double (open-priced, "
      f"4.5% margin): {dd:.1f} units.\n")

    h("## 2. Pricing scenarios for the holdout cards (EV is assumption-dependent)\n")
    rows = []
    for margin in lock["pricing_scenarios"]["margins"]:
        for ref in ("open", "close"):
            pa = HC.pm_a if ref == "open" else (1 - 0.0455) / HC.odds_close_a
            pb = HC.pm_b if ref == "open" else (1 - 0.0455) / HC.odds_close_b
            oa, ob = (1 - margin) / pa, (1 - margin) / pb
            profit = np.where(HC.card_2of2 == 1, oa * ob - 1, -1.0)
            rows.append({"alt price reference": ref, "margin per leg": margin,
                         "avg double odds": float((oa * ob).mean()), "ROI per card": float(profit.mean()),
                         "break-even 2/2 rate": float((1 / (oa * ob)).mean())})
    h(df_to_md(pd.DataFrame(rows)))
    h("\nNo historical alternate-line prices exist in the data, so these are scenarios: the "
      "market-only distribution around the stated line, minus the stated margin per leg.\n")

    h("## 3. Main-line (no buffer) two-sided performance, holdout\n")
    M = main_line_probs(P, cals)
    Mm = main_line_probs(P.assign(mu=P.mu_mkt, sd=P.sd_mkt), calm)
    e = M[M.season.isin(HOLD) & M.eligible & ~M.push]
    em = Mm.set_index("game_key").loc[e.game_key]
    ll_m = log_loss(e.p_over / (e.p_over + e.p_under), e.over)
    ll_k = log_loss(em.p_over / (em.p_over + em.p_under), e.over)
    h(f"Log loss model {ll_m:.5f} vs market-only {ll_k:.5f} (gain {(ll_k - ll_m) * 1e4:+.1f}×10⁻⁴) over {len(e)} games.\n")
    rows = []
    for lo, hi in ((.5, .55), (.55, .6), (.6, .65), (.65, 1.01)):
        mm = e[(e.p_best >= lo) & (e.p_best < hi) & ~e.best_push]
        k, n = int(mm.best_win.sum()), len(mm)
        rows.append({"two-sided P bucket": f"{lo:.0%}-{min(hi, 1):.0%}", "bets": n,
                     "pred": mm.p_best.mean() if n else np.nan, "win": k / n if n else np.nan,
                     "ci95": wilson(k, n), "roi_at_1.909": (k * 0.909 - (n - k)) / n if n else np.nan})
    h(df_to_md(pd.DataFrame(rows)))
    h()
    f2 = []
    for date, day in e.groupby("date"):
        if len(day) >= 2:
            t = day.nlargest(2, "p_best")
            f2.append(int(t.best_win.all() and not t.best_push.any()))
    k, n = int(np.sum(f2)), len(f2)
    lo, hi = wilson(k, n)
    h(f"Main-line top-2 card every slate (no buffer): {n} cards, 2/2 {k / n:.1%} (CI {lo:.1%}–{hi:.1%}).\n")

    h("## 4. Closing-line value of the chosen legs (holdout)\n")
    F = P.set_index("game_key")
    mv = []
    for leg in ("a", "b"):
        g = F.loc[HC[f"game_{leg}"]]
        mv.append(HC[f"side_{leg}"].values * (g.line_close.values - g.line_open.values))
    mv = np.concatenate(mv)
    h(f"Average open→close line move in the direction of our bet: {np.nanmean(mv):+.2f} points "
      f"(share of legs where the market moved our way: {np.nanmean(mv > 0):.1%}, against: {np.nanmean(mv < 0):.1%}).\n")

    REPORT.write_text("\n".join(OUT) + "\n")
    log_experiment("stage2_holdout", {"lock": lock},
                   {"holdout": card_summary(C[C.season.isin(HOLD)]),
                    "development": card_summary(C[C.season.isin(DEV)])})


if __name__ == "__main__":
    main()
