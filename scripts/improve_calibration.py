"""Engine-improvement study 1 — side-aware calibration (pre-registered in config/improvements.yaml).

The locked NCAAB v3 engine's walk-forward predictions are kept; only the calibrator is refitted,
walk-forward with the locked history and season weights, in three forms: C0 (locked), C1 (+ a side
term) and C2 (+ side terms on the alternate-line buffer). Every season 2011-26 was used before, so
this is a RE-ANALYSIS; the pre-registered rule decides which calibrator joins the 2026-27 forward
ledger next to C0. Writes reports/improve_calibration.md (and config/improvements_adopted.yaml if
a candidate passes).
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
from backtest.wf2 import _season_weights, main_line_probs
from calibration.calibrate import wilson
from config_loader import ROOT, log_experiment
from diagnose_bets import book_stats, load
from models.dist_models import LatentCalibrator
from stage3_common import evaluate

CFG = yaml.safe_load((ROOT / "config" / "improvements.yaml").read_text())
ERAS = list(CFG["eras"])                                             # dev, holdout, reanalysis
ERA = {s: e for e, ss in CFG["eras"].items() for s in ss}
CANDS = {"C0_locked": "base", "C1_side": "side", "C2_side_buffer": "side_buffer"}
P_MIN = 0.55


def refit(P: pd.DataFrame, terms: str, decay: float = 0.6, seed: int = 2) -> dict:
    """The calibrator loop of backtest.wf2.walk_forward_market with another calibrator form."""
    pseasons = list(dict.fromkeys(P.season))
    cals = {}
    for j, s in enumerate(pseasons):
        if j < seed:
            continue
        hist = P[P.season.isin(pseasons[:j]) & P.eligible]
        cals[s] = LatentCalibrator(terms).fit(hist, weights=_season_weights(hist.season, s, pseasons, decay))
    return cals


def log_loss(p, y) -> float:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def pseudo_log_loss(P: pd.DataFrame, cals: dict) -> dict:
    """Log loss over the calibrator's alternate-line pseudo-bets (both sides, all buffers), per era."""
    out = {e: [0.0, 0] for e in ERAS}
    for s in [s for s in cals if s in ERA]:
        pb = LatentCalibrator.pseudo_bets(P[(P.season == s) & P.eligible])
        p = np.clip(cals[s].prob(pb.s_model.values, pb.s_buf.values, side=pb.side.values), 1e-6, 1 - 1e-6)
        out[ERA[s]][0] += float(-np.sum(pb.win * np.log(p) + (1 - pb.win) * np.log(1 - p)))
        out[ERA[s]][1] += len(pb)
    return {e: v[0] / v[1] for e, v in out.items() if v[1]}


def singles(M: pd.DataFrame) -> pd.DataFrame:
    B = M[(M.p_best >= P_MIN) & ~M.best_push].copy()
    B["win"] = B.best_win.astype(int)
    B["pnl110"] = np.where(B.win == 1, 100 / 110, -1.0)
    live = B.books_json.notna() & B.books_json.astype(str).str.startswith("{")
    st = [book_stats(bj, int(s))[:2] for bj, s in zip(B.loc[live, "books_json"], B.loc[live, "best_side"])]
    B["best_line"], B["best_price"] = np.nan, np.nan
    if st:
        B.loc[live, ["best_line", "best_price"]] = np.array(st, dtype=float)
    win_real = np.where(B.best_side == 1, B.outcome > B.best_line, B.outcome < B.best_line)
    B["pnl_real"] = np.where(B.best_line.isna(), np.nan, np.where(B.outcome == B.best_line, 0.0,
                                                                   np.where(win_real, B.best_price - 1, -1.0)))
    B["side"] = np.where(B.best_side == 1, "Over", "Under")
    return B


def single_rows(B: pd.DataFrame, name: str) -> list:
    rows = []
    for era in ERAS + ["POOLED"]:
        b = B if era == "POOLED" else B[B.era == era]
        n, w = len(b), int(b.win.sum())
        r = {"calibrator": name, "era": era, "bets": n, "win": w / n if n else np.nan, "ci95": wilson(w, n),
             "predicted": b.p_best.mean(), "ROI @-110": b.pnl110.mean(),
             "ROI real price": b.pnl_real.mean() if b.pnl_real.notna().any() else np.nan}
        for side in ("Over", "Under"):
            x = b[b.side == side]
            r[f"{side} bets"] = len(x)
            r[f"{side} win - predicted"] = (x.win.mean() - x.p_best.mean()) if len(x) else np.nan
        rows.append(r)
    return rows


def main():
    P, cals_locked, calm = load()
    books = P.drop_duplicates("game_key").set_index("game_key").books_json
    re_seasons = CFG["eras"]["reanalysis"]

    # the refitted C0 must reproduce the locked calibrators exactly
    c0 = refit(P, "base")
    drift = max(float(np.max(np.abs(c0[s].beta - cals_locked[s].beta))) for s in c0)
    assert drift < 1e-6, f"C0 refit does not reproduce the locked calibrators (max |d beta| = {drift})"

    prim, pseudo, single_tab, card_tab, betas, side_mix = [], [], [], [], {}, []
    for name, terms in CANDS.items():
        cals = cals_locked if terms == "base" else refit(P, terms)
        betas[name] = {s: np.round(cals[s].beta, 4).tolist() for s in ("2011-12", "2018-19", "2025-26") if s in cals}
        M = main_line_probs(P, cals)
        M = M[M.eligible & M.season.isin(ERA)].copy()
        M["era"] = M.season.map(ERA)
        e = M[M.outcome != M.line]
        p2 = e.p_over / (e.p_over + e.p_under)
        y = (e.outcome > e.line).astype(int)
        r = {"calibrator": name}
        for era in ERAS:
            m = (e.era == era).values
            r[era] = log_loss(p2[m], y[m])
        r["pooled"] = log_loss(p2, y)
        r["mean P(over)"] = float(p2.mean())
        r["over rate"] = float(y.mean())
        prim.append(r)
        pseudo.append({"calibrator": name, **pseudo_log_loss(P, cals)})
        B = singles(M)
        single_tab += single_rows(B, name)
        side_mix.append({"calibrator": name, **{f"{era} Under share": (B[B.era == era].side == "Under").mean()
                                                 for era in ERAS}})
        R, _ = evaluate(P, cals, calm, books, re_seasons)
        R = R[(R.season == "POOLED") & R["product"].str.match(r"(TARGET|MAIN)")]
        card_tab += [{"calibrator": name, "product": x["product"].split(" (")[0], "cards": x.cards, "hit": x.hit,
                      "model_hit": x.model_hit, "leg_win": x.leg_win, "leg_p": x.leg_p, "roi": x.roi,
                      "roi_ci95": x.roi_ci95} for _, x in R.iterrows()]

    Pr = pd.DataFrame(prim).set_index("calibrator")
    S = pd.DataFrame(single_tab)
    roi = S[S.era == "POOLED"].set_index("calibrator")["ROI @-110"]
    qualifies = {c: bool(all(Pr.loc[c, e] < Pr.loc["C0_locked", e] for e in ERAS) and roi[c] >= roi["C0_locked"])
                 for c in ("C1_side", "C2_side_buffer")}
    if all(qualifies.values()):
        adopted = "C2_side_buffer" if all(Pr.loc["C2_side_buffer", e] < Pr.loc["C1_side", e] for e in ERAS) else "C1_side"
    else:
        adopted = next((c for c, ok in qualifies.items() if ok), None)

    gain = (Pr.loc[:, ERAS + ["pooled"]].rsub(Pr.loc["C0_locked", ERAS + ["pooled"]], axis=1) * 1e4).round(1)
    lines = ["# Improvement study 1 — side-aware calibration (NCAAB, locked v3 engine)\n",
             "_Pre-registered in `config/improvements.yaml` before any candidate was fitted. Every season "
             "2011-26 was used before, so this is a re-analysis; the 2026-27 forward ledger is the real test._\n",
             "Only the calibrator changes (walk-forward, same history and season weights as the locked one; "
             f"the refitted C0 reproduces the locked calibrators exactly, max |Δβ| = {drift:.1e}).\n",
             "## Primary: log loss of P(over) at the opener, every calibrated game\n",
             df_to_md(Pr.reset_index(), "{:.5f}"), "",
             "Improvement over C0 (×10⁻⁴; positive = better):\n", df_to_md(gain.reset_index()), "",
             "## Alternate-line pricing: log loss over all pseudo-bets (both sides, buffers -6..+18)\n",
             df_to_md(pd.DataFrame(pseudo), "{:.5f}"), "",
             f"## Singles at the opener, calibrated P >= {P_MIN:.0%}\n",
             df_to_md(S, "{:.3f}"), "",
             "Share of these bets that are Unders:\n", df_to_md(pd.DataFrame(side_mix), "{:.3f}"), "",
             "## 2.5+ target cards and main-line doubles, 2021-26 at real prices (locked products; re-analysis)\n",
             df_to_md(pd.DataFrame(card_tab), "{:.3f}"), "",
             "## Decision (pre-registered rule)\n",
             f"* C1_side qualifies: **{qualifies['C1_side']}**; C2_side_buffer qualifies: "
             f"**{qualifies['C2_side_buffer']}** (log loss lower than C0 in each era and pooled ROI @-110 not lower).",
             f"* Adopted for the 2026-27 forward ledger next to C0: **{adopted or 'none'}**.", "",
             "Calibrator coefficients (b0, b_model, b_buf, b_buf², b_model×buf, side terms…) for three seasons:\n",
             "```", yaml.safe_dump(betas, sort_keys=False, default_flow_style=None).strip(), "```"]
    (ROOT / "reports" / "improve_calibration.md").write_text("\n".join(lines) + "\n")
    if adopted:
        (ROOT / "config" / "improvements_adopted.yaml").write_text(yaml.safe_dump({
            "study": CFG["study"], "adopted": adopted, "calib_terms": CANDS[adopted],
            "use": "forward ledger 2026-27: record the adopted calibrator's picks next to the locked C0 picks",
            "evidence_log_loss_gain_x1e4": {k: float(v) for k, v in gain.loc[adopted].items()}}, sort_keys=False))
    print("\n".join(lines))
    log_experiment("improve_calibration", {"pre_registration": CFG},
                   {"primary": Pr.reset_index().to_dict("records"), "qualifies": qualifies, "adopted": adopted})


if __name__ == "__main__":
    main()
