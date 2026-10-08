"""Improvement study 4 — roster continuity (pre-registered: config/improvements.yaml `study_4`).

Point-in-time roster continuity and incoming-transfer shares from ESPN player box scores are added
to the locked v3 engine (mean and variance models). Selection on 2011-21; a qualifying candidate is
checked ONCE on the sealed 2021-26 seasons. Writes reports/study4_continuity.md.
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

import study2_stage_matchup as S2
from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment
from data.ncaab_continuity import attach, continuity
from data.ncaab_players import load as load_players
from stage3_common import evaluate

CFG = yaml.safe_load((ROOT / "config" / "improvements.yaml").read_text())["study_4"]
REPORT = ROOT / "reports" / "study4_continuity.md"
EXTRA_MEAN = {"R1_continuity": ["cont_avg", "xfer_avg", "x_pts_lowcont"]}
EXTRA_VAR = {"R1_continuity": ["lowcont"]}


def market():
    from data.ncaab_unify import unify
    from features.ncaab_features import market_frame
    from features.store import fingerprint, get_features
    u, box, _ = unify(write=False, include_live=True)
    f = get_features("ncaab", u, box, verbose=False)
    d = market_frame(f, "open")
    d = attach(d, continuity(load_players()))
    d["cont_avg"] = d[["home_cont", "away_cont"]].mean(axis=1, skipna=False)
    d["xfer_avg"] = d[["home_xfer", "away_xfer"]].mean(axis=1, skipna=False)
    d["lowcont"] = 1 - d.cont_avg
    d["x_pts_lowcont"] = d.x_pts * d.lowcont
    return d.reset_index(drop=True), fingerprint(u, box)


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT.name} exists — study 4's confirmation on 2021-26 runs once only.")
    from features.store import cached_walk_forward
    d, fp = market()
    seasons = sorted(d.season.unique())
    base_spec = S2.spec_v3()
    arms = {"locked_v3": cached_walk_forward(d, base_spec, seasons, fp)}
    for name in EXTRA_MEAN:
        spec = dict(base_spec, mean_feats=list(base_spec["mean_feats"]) + EXTRA_MEAN[name],
                    var_feats=list(base_spec["var_feats"]) + EXTRA_VAR[name], study="study_4:" + name)
        arms[name] = cached_walk_forward(d, spec, seasons, fp)
    Ms = {k: S2.main_line(P, cals) for k, (P, cals, _) in arms.items()}
    base = Ms["locked_v3"]
    n_by_season = base[base.p_best >= S2.P_MIN].groupby("season").size().to_dict()

    rows, early = [], []
    for name, M in Ms.items():
        for era, ss in S2.SEL_ERAS.items():
            rows.append({"engine": name, "era": era, **S2.era_metrics(M, n_by_season, ss)})
        rows.append({"engine": name, "era": "2011-21", **S2.era_metrics(M, n_by_season, S2.DEV + S2.HOLD)})
        e = M[M.season.isin(S2.DEV + S2.HOLD) & (M.rt_min_games < 6)]
        b = e[e.p_best >= S2.P_MIN]
        early.append({"engine": name, "early games": int((e.outcome != e.line).sum()),
                      "log loss": S2.log_loss_two_sided(e), "bets P>=55%": len(b), "ROI @-110": S2.roi(b)})
    S = pd.DataFrame(rows)
    b = S[S.engine == "locked_v3"].set_index("era")
    qual = {}
    for name in EXTRA_MEAN:
        c = S[S.engine == name].set_index("era")
        qual[name] = bool(all(c.loc[e, "log loss"] < b.loc[e, "log loss"] and
                              c.loc[e, "matched ROI @-110"] > b.loc[e, "matched ROI @-110"] for e in S2.SEL_ERAS))
    ok = [n for n in EXTRA_MEAN if qual[n]]
    selected = ok[0] if ok else None
    cov = d[d.season.isin(S2.DEV + S2.HOLD)].groupby("season").cont_avg.apply(lambda s: s.notna().mean())

    lines = ["# Improvement study 4 — roster continuity (NCAAB)\n",
             "_Pre-registered in `config/improvements.yaml` (`study_4`) before the candidate was fitted. "
             "Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._\n",
             "Share of games with a continuity value, by season: "
             + ", ".join(f"{s} {v:.0%}" for s, v in cov.items()) + ".\n",
             "## Selection (2011-21)\n", df_to_md(S, "{:.4f}"), "",
             "Early-season games only (a team with < 6 games; secondary, not part of the rule):\n",
             df_to_md(pd.DataFrame(early), "{:.4f}"), "",
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
            cur["study_4"] = {"adopted": selected, "extra_mean_feats": EXTRA_MEAN[selected],
                              "extra_var_feats": EXTRA_VAR[selected],
                              "use": "2026-27 forward ledger: recorded next to the locked v3 engine"}
            path.write_text(yaml.safe_dump(cur, sort_keys=False))
    else:
        lines.append("No candidate qualified, so this study does not use the 2021-26 seasons.")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("study4_continuity", {"pre_registration": CFG},
                   {"selection": S.to_dict("records"), "early": early, "qualifies": qual, "selected": selected,
                    "confirmed": verdict})


if __name__ == "__main__":
    main()
