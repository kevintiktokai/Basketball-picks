"""Improvement study 5 — learn from the closing line (pre-registered: config/improvements.yaml `study_5`).

M1: the mean model is trained on close - open (the market's own correction of the opener) instead
of total - open; a constant and the variance model are then fitted on total - open - predicted move.
M2: the locked engine plus the predicted move as one extra feature. Everything else is locked
(features, season weights, calibrator, eligibility). Walk-forward exactly as backtest/wf2.py.
Selection on 2011-21; a qualifying candidate is checked ONCE on the sealed 2021-26 seasons.
Writes reports/study5_close_target.md.
"""
from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml

import study2_stage_matchup as S2
from backtest.analysis import df_to_md
from backtest.wf2 import _season_weights
from config_loader import ROOT, log_experiment
from models.dist_models import DistModel, LatentCalibrator
from stage3_common import evaluate

CFG = yaml.safe_load((ROOT / "config" / "improvements.yaml").read_text())["study_5"]
REPORT = ROOT / "reports" / "study5_close_target.md"
ARMS = ("M1_close_target", "M2_move_feature")


def walk_forward_close(d: pd.DataFrame, spec: dict, mode: str, min_train: int = 2, calib_seed: int = 2):
    """walk_forward_market with a close-informed mean model (mode M1 or M2)."""
    seasons = sorted(d.season.unique())
    data = d.copy()
    data["eligible"] = data.rt_min_games.fillna(0) >= spec["min_games"]
    data["move"] = (data.line_close - data.line_open).where(data.ok_close & data.ok_open)
    mf, vf = list(spec["mean_feats"]), list(spec["var_feats"])
    kw = dict(kind=spec["kind"], shape=spec["shape"], alpha=spec["alpha"])
    preds = []
    for i, s in enumerate(seasons):
        if i < min_train:
            continue
        tr = data[data.season.isin(seasons[:i]) & data.eligible].copy()
        te = data[data.season == s].copy()
        w = _season_weights(tr.season, s, seasons, spec["train_decay"])
        trm = tr.move.notna().values
        mover = DistModel(mf, [], **kw).fit(tr[trm].assign(resid=tr.move[trm]), weights=w[trm])
        if mode == "M1_close_target":
            mu_tr = mover.predict_mean(tr)
            rest = DistModel([], vf, **kw).fit(tr.assign(resid=tr.resid - mu_tr), weights=w)
            te["mu"] = mover.predict_mean(te) + rest.mean_m
            te["sd"] = rest.predict_sd(te)
        else:
            tr["mu_move"] = mover.predict_mean(tr)
            te["mu_move"] = mover.predict_mean(te)
            m = DistModel(mf + ["mu_move"], vf, **kw).fit(tr, weights=w)
            te["mu"], te["sd"] = m.predict_mean(te), m.predict_sd(te)
        mk = DistModel([], [], shape=spec["shape"]).fit(tr)
        te["mu_mkt"], te["sd_mkt"] = mk.predict_mean(te), mk.predict_sd(te)
        preds.append(te)
    P = pd.concat(preds, ignore_index=True)
    cals, cals_mkt = {}, {}
    ps = list(dict.fromkeys(P.season))
    for j, s in enumerate(ps):
        if j < calib_seed:
            continue
        hist = P[P.season.isin(ps[:j]) & P.eligible]
        cals[s] = LatentCalibrator().fit(hist, weights=_season_weights(hist.season, s, ps, spec["calib_decay"]))
        cals_mkt[s] = LatentCalibrator().fit(hist.assign(mu=hist.mu_mkt, sd=hist.sd_mkt))
    P["calibrated"] = P.season.isin(list(cals))
    return P, cals, cals_mkt


def cached(d, spec, mode, fp):
    from features.store import STORE
    path = STORE / f"wf_study5_{mode}_{fp}_{len(d)}.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    out = walk_forward_close(d, spec, mode)
    path.write_bytes(pickle.dumps(out))
    return out


def market():
    from data.ncaab_unify import unify
    from features.ncaab_features import market_frame
    from features.store import fingerprint, get_features
    u, box, _ = unify(write=False, include_live=True)
    f = get_features("ncaab", u, box, verbose=False)
    return market_frame(f, "open").reset_index(drop=True), fingerprint(u, box)


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT.name} exists — study 5's confirmation on 2021-26 runs once only.")
    from features.store import cached_walk_forward
    d, fp = market()
    seasons = sorted(d.season.unique())
    spec = S2.spec_v3()
    arms = {"locked_v3": cached_walk_forward(d, spec, seasons, fp)}
    for mode in ARMS:
        arms[mode] = cached(d, spec, mode, fp)
        print("fitted", mode, flush=True)
    Ms = {k: S2.main_line(P, cals) for k, (P, cals, _) in arms.items()}
    base = Ms["locked_v3"]
    n_by_season = base[base.p_best >= S2.P_MIN].groupby("season").size().to_dict()
    rows = []
    for name, M in Ms.items():
        for era, ss in S2.SEL_ERAS.items():
            rows.append({"engine": name, "era": era, **S2.era_metrics(M, n_by_season, ss)})
        rows.append({"engine": name, "era": "2011-21", **S2.era_metrics(M, n_by_season, S2.DEV + S2.HOLD)})
    S = pd.DataFrame(rows)
    b = S[S.engine == "locked_v3"].set_index("era")
    qual = {}
    for name in ARMS:
        c = S[S.engine == name].set_index("era")
        qual[name] = bool(all(c.loc[e, "log loss"] < b.loc[e, "log loss"] and
                              c.loc[e, "matched ROI @-110"] > b.loc[e, "matched ROI @-110"] for e in S2.SEL_ERAS))
    ok = [n for n in ARMS if qual[n]]
    selected = max(ok, key=lambda n: S[(S.engine == n) & (S.era == "2011-21")]["matched ROI @-110"].iloc[0]) if ok else None
    lines = ["# Improvement study 5 — learn from the closing line (NCAAB)\n",
             "_Pre-registered in `config/improvements.yaml` (`study_5`) before any candidate was fitted. "
             "Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._\n",
             "## Selection (2011-21)\n", df_to_md(S, "{:.4f}"), "",
             "Qualifies (lower log loss AND higher matched ROI in both eras): "
             + ", ".join(f"{n} **{q}**" for n, q in qual.items()) + f". Selected: **{selected or 'none'}**.\n"]
    verdict = None
    if selected:
        books = d.set_index("game_key").books_json
        C = pd.DataFrame([{"engine": n, **S2.era_metrics(Ms[n], n_by_season, S2.CONF, real=True)}
                          for n in ("locked_v3", selected)]).set_index("engine")
        c, l = C.loc[selected], C.loc["locked_v3"]
        verdict = bool(c["log loss"] < l["log loss"] and c["matched ROI @-110"] >= l["matched ROI @-110"]
                       and c["matched ROI real price"] >= l["matched ROI real price"])
        cards = []
        for name in ("locked_v3", selected):
            P, cals, calm = arms[name]
            R, _ = evaluate(P, cals, calm, books, S2.CONF)
            R = R[(R.season == "POOLED") & R["product"].str.match(r"(TARGET|MAIN)")]
            cards += [{"engine": name, "product": x["product"].split(" (")[0], "cards": x.cards, "hit": x.hit,
                       "leg_win": x.leg_win, "roi": x.roi, "roi_ci95": x.roi_ci95} for _, x in R.iterrows()]
        lines += ["## Confirmation on the sealed 2021-26 seasons (run once)\n", df_to_md(C.reset_index(), "{:.4f}"), "",
                  "2.5+ target cards and main-line doubles at real prices, 2021-26:\n",
                  df_to_md(pd.DataFrame(cards), "{:.3f}"), "",
                  f"**Confirmation passed: {verdict}** (lower log loss, matched ROI not lower at -110 and at the "
                  "best real price)."]
        if verdict:
            path = ROOT / "config" / "improvements_adopted.yaml"
            cur = yaml.safe_load(path.read_text()) if path.exists() else {}
            cur["study_5"] = {"adopted": selected,
                              "use": "2026-27 forward ledger: recorded next to the locked v3 engine"}
            path.write_text(yaml.safe_dump(cur, sort_keys=False))
    else:
        lines.append("No candidate qualified, so this study does not use the 2021-26 seasons.")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("study5_close_target", {"pre_registration": CFG},
                   {"selection": S.to_dict("records"), "qualifies": qual, "selected": selected, "confirmed": verdict})


if __name__ == "__main__":
    main()
