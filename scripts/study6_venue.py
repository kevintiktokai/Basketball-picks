"""Improvement study 6 — venue park factor and high altitude (pre-registered: config/improvements.yaml `study_6`).

The locked v3 engine's mean model gets the home floor's point-in-time park factor (V1), plus a
high-altitude flag (V2); everything else is the locked engine. Selection on 2011-21; a qualifying
candidate is checked ONCE on the sealed 2021-26 seasons; the script refuses to run again once its
report exists. Writes reports/study6_venue.md.
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
from data.ncaab_venue import high_altitude, venue_factor
from stage3_common import evaluate

CFG = yaml.safe_load((ROOT / "config" / "improvements.yaml").read_text())["study_6"]
REPORT = ROOT / "reports" / "study6_venue.md"
EXTRA = {"V1_venue": ["venue_factor"], "V2_venue_altitude": ["venue_factor", "high_altitude"]}


def market():
    from data.ncaab_unify import unify
    from features.ncaab_features import market_frame
    from features.store import fingerprint, get_features
    u, box, _ = unify(write=False, include_live=True)
    f = get_features("ncaab", u, box, verbose=False)
    d = market_frame(f, "open").reset_index(drop=True)
    d["venue_factor"] = venue_factor(u, d)
    d["high_altitude"] = high_altitude(d)
    return d, fingerprint(u, box)


def venue_bets(M: pd.DataFrame, d: pd.DataFrame, seasons: list) -> pd.DataFrame:
    """Secondary: P >= 55% bets whose venue factor is strong (|f| >= 1) and agrees / disagrees."""
    B = M[M.season.isin(seasons) & (M.p_best >= S2.P_MIN) & ~M.best_push].merge(
        d[["game_key", "venue_factor"]], on="game_key", how="left", suffixes=("", "_d"))
    vf = B["venue_factor_d"] if "venue_factor_d" in B else B["venue_factor"]
    rows = []
    for lab, sel in (("strong, agrees with the bet", (vf.abs() >= 1) & (np.sign(vf) == B.best_side)),
                     ("strong, against the bet", (vf.abs() >= 1) & (np.sign(vf) != B.best_side)),
                     ("weak or neutral site", vf.abs() < 1)):
        x = B[sel]
        rows.append({"venue factor": lab, "bets": len(x), "won": x.best_win.mean(),
                     "ROI @-110": (x.best_win * 100 / 110 - (1 - x.best_win)).mean()})
    return pd.DataFrame(rows)


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT.name} exists — study 6's confirmation on 2021-26 runs once only.")
    from features.store import cached_walk_forward
    d, fp = market()
    seasons = sorted(d.season.unique())
    base_spec = S2.spec_v3()
    arms = {"locked_v3": cached_walk_forward(d, base_spec, seasons, fp)}
    for name, extra in EXTRA.items():
        spec = dict(base_spec, mean_feats=list(base_spec["mean_feats"]) + extra, study="study_6:" + name)
        arms[name] = cached_walk_forward(d, spec, seasons, fp)
        print("fitted", name, flush=True)
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
    qual, pooled = {}, {}
    for name in EXTRA:
        c = S[S.engine == name].set_index("era")
        qual[name] = bool(all(c.loc[e, "log loss"] < b.loc[e, "log loss"] and
                              c.loc[e, "matched ROI @-110"] > b.loc[e, "matched ROI @-110"] for e in S2.SEL_ERAS))
        pooled[name] = float(c.loc["2011-21", "matched ROI @-110"])
    ok = [n for n in EXTRA if qual[n]]
    selected = max(ok, key=lambda n: (pooled[n], -list(EXTRA).index(n))) if ok else None
    sel = d[d.season.isin(S2.DEV + S2.HOLD)]
    cover = (f"Non-neutral games with a venue history: {(sel.venue_factor != 0).mean():.0%} of 2011-21 games; "
             f"venue factor sd {sel.venue_factor.std():.2f} points; high-altitude venues {sel.high_altitude.mean():.1%} of games.")

    lines = ["# Improvement study 6 — venue park factor and high altitude (NCAAB)\n",
             "_Pre-registered in `config/improvements.yaml` (`study_6`) before any candidate was fitted. "
             "Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._\n",
             cover + "\n",
             "## Selection (2011-21)\n", df_to_md(S, "{:.4f}"), "",
             "Locked engine's bets by venue factor (secondary, 2011-21):\n",
             df_to_md(venue_bets(base, d, S2.DEV + S2.HOLD), "{:.3f}"), "",
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
        seas = []
        for n in ("locked_v3", selected):
            for s in S2.CONF:
                seas.append({"engine": n, "season": s, **S2.era_metrics(Ms[n], n_by_season, [s], real=True)})
        cards = []
        for name in ("locked_v3", selected):
            P, cals, calm = arms[name]
            R, _ = evaluate(P, cals, calm, books, S2.CONF)
            R = R[(R.season == "POOLED") & R["product"].str.match(r"(TARGET|MAIN)")]
            cards += [{"engine": name, "product": x["product"].split(" (")[0], "cards": x.cards, "hit": x.hit,
                       "leg_win": x.leg_win, "roi": x.roi, "roi_ci95": x.roi_ci95} for _, x in R.iterrows()]
        lines += ["## Confirmation on the sealed 2021-26 seasons (run once)\n", df_to_md(C.reset_index(), "{:.4f}"), "",
                  "Season by season:\n", df_to_md(pd.DataFrame(seas), "{:.4f}"), "",
                  "Locked engine's 2021-26 bets by venue factor (secondary):\n",
                  df_to_md(venue_bets(base, d, S2.CONF), "{:.3f}"), "",
                  "2.5+ target cards and main-line doubles at real prices, 2021-26:\n",
                  df_to_md(pd.DataFrame(cards), "{:.3f}"), "",
                  f"**Confirmation passed: {verdict}** (lower log loss, matched ROI not lower at -110 and at the "
                  "best real price)."]
        if verdict:
            path = ROOT / "config" / "improvements_adopted.yaml"
            cur = yaml.safe_load(path.read_text()) if path.exists() else {}
            cur["study_6"] = {"adopted": selected, "extra_mean_feats": EXTRA[selected],
                              "use": "2026-27 forward ledger: recorded next to the locked v3 engine"}
            path.write_text(yaml.safe_dump(cur, sort_keys=False))
    else:
        lines.append("No candidate qualified, so this study does not use the 2021-26 seasons.")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("study6_venue", {"pre_registration": CFG},
                   {"selection": S.to_dict("records"), "qualifies": qual, "selected": selected, "confirmed": verdict})


if __name__ == "__main__":
    main()
