"""Improvement study 2 — stage and matchup features (pre-registered: config/improvements.yaml `study_2`).

The locked v3 engine's mean model gets stage indicators (S1), then tempo and efficiency mismatch
(S2), then recent fatigue (S3); everything else is the locked engine. Selection uses 2011-21 only.
The selected candidate (if any) is then checked ONCE on the sealed 2021-26 seasons; the script
refuses to run again once its report exists.
Writes reports/study2_stage_matchup.md.
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
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from data.ncaab_stages import STAGES, attach, load_schedules
from diagnose_bets import book_stats
from stage3_common import evaluate

CFG = yaml.safe_load((ROOT / "config" / "improvements.yaml").read_text())["study_2"]
REPORT = ROOT / "reports" / "study2_stage_matchup.md"
DEV = ["2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17", "2017-18"]
HOLD = ["2018-19", "2019-20", "2020-21"]
CONF = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
SEL_ERAS = {"dev 2011-18": DEV, "holdout 2018-21": HOLD}
P_MIN = 0.55
STAGE_FEATS = [f"st_{s}" for s in STAGES if s != "conf_regular"]
EXTRA = {"S1_stage": STAGE_FEATS,
         "S2_stage_matchup": STAGE_FEATS + ["tempo_gap", "eff_gap"],
         "S3_stage_matchup_fatigue": STAGE_FEATS + ["tempo_gap", "eff_gap", "fatigue3"]}


def recent_games(d: pd.DataFrame, s: pd.DataFrame, days: int = 3) -> np.ndarray:
    """Games each team played in the `days` days before the game (ESPN schedule), home + away."""
    long = pd.concat([s[["date", "home"]].rename(columns={"home": "team"}),
                      s[["date", "away"]].rename(columns={"away": "team"})])
    by_team = {t: np.sort(g.date.values) for t, g in long.groupby("team")}
    out = np.zeros(len(d))
    for side in ("home", "away"):
        for t, idx in d.groupby(side).groups.items():
            dates = by_team.get(t)
            if dates is None:
                continue
            D = d.loc[idx, "date"].values
            out[d.index.get_indexer(idx)] += (np.searchsorted(dates, D, "left")
                                              - np.searchsorted(dates, D - np.timedelta64(days, "D"), "left"))
    return out


def market():
    from data.ncaab_unify import unify
    from features.ncaab_features import market_frame
    from features.store import fingerprint, get_features
    u, box, _ = unify(write=False, include_live=True)
    f = get_features("ncaab", u, box, verbose=False)
    d = market_frame(f, "open")
    s = load_schedules()
    d = attach(d, s)
    for st in STAGES:
        if st != "conf_regular":
            d[f"st_{st}"] = (d.stage == st).astype(float)
    d["tempo_gap"] = (d.rt_tempo_home - d.rt_tempo_away).abs()
    d["eff_gap"] = ((d.rt_off_home - d.rt_def_away) - (d.rt_off_away - d.rt_def_home)).abs()
    d["fatigue3"] = recent_games(d.reset_index(drop=True), s)
    return d.reset_index(drop=True), fingerprint(u, box)


def spec_v3() -> dict:
    v2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())["model"]
    v3 = yaml.safe_load((ROOT / "config" / "stage3_v3_locked.yaml").read_text())["changes_vs_v2"]
    return dict(v2, train_decay=v3["train_decay"], calib_decay=v3["calib_decay"])


def main_line(P, cals) -> pd.DataFrame:
    M = main_line_probs(P, cals)
    return M[M.eligible].copy()


def log_loss_two_sided(M: pd.DataFrame) -> float:
    e = M[M.outcome != M.line]
    p = np.clip(e.p_over / (e.p_over + e.p_under), 1e-6, 1 - 1e-6)
    y = (e.outcome > e.line).astype(float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def matched(M: pd.DataFrame, n_by_season: dict) -> pd.DataFrame:
    """Each season's N most confident games (selection never looks at the result)."""
    return pd.concat([g.nlargest(n_by_season.get(s, 0), "p_best") for s, g in M.groupby("season")])


def roi(B: pd.DataFrame, real: bool = False) -> float:
    if not real:
        pnl = np.where(B.best_push, 0.0, np.where(B.best_win == 1, 100 / 110, -1.0))
        return float(pnl.mean()) if len(B) else np.nan
    st = [book_stats(bj, int(s))[:2] for bj, s in zip(B.books_json, B.best_side)]
    line = np.array([x[0] for x in st], float)
    price = np.array([x[1] for x in st], float)
    ok = ~np.isnan(line)
    win = np.where(B.best_side == 1, B.outcome > line, B.outcome < line)
    pnl = np.where(B.outcome == line, 0.0, np.where(win, price - 1, -1.0))
    return float(pnl[ok].mean()) if ok.any() else np.nan


def era_metrics(M: pd.DataFrame, n_by_season: dict, seasons: list, real: bool = False) -> dict:
    m = M[M.season.isin(seasons)]
    B = matched(m, n_by_season)
    out = {"games": int((m.outcome != m.line).sum()), "log loss": log_loss_two_sided(m),
           "matched bets": len(B), "matched win": float(B[~B.best_push].best_win.mean()), "matched ROI @-110": roi(B)}
    if real:
        out["matched ROI real price"] = roi(B, real=True)
    T = m[m.p_best >= P_MIN]
    out.update({"bets P>=55%": len(T), "ROI @-110 at P>=55%": roi(T)})
    return out


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT.name} exists — study 2's confirmation on 2021-26 runs once only.")
    from features.store import cached_walk_forward
    d, fp = market()
    seasons = sorted(d.season.unique())
    base_spec = spec_v3()
    arms = {"locked_v3": cached_walk_forward(d, base_spec, seasons, fp)}
    for name, extra in EXTRA.items():
        spec = dict(base_spec, mean_feats=list(base_spec["mean_feats"]) + extra, study="study_2:" + name)
        arms[name] = cached_walk_forward(d, spec, seasons, fp)
        print("fitted", name, flush=True)
    Ms = {k: main_line(P, cals) for k, (P, cals, _) in arms.items()}
    base = Ms["locked_v3"]
    n_by_season = (base[base.p_best >= P_MIN].groupby("season").size()).to_dict()

    # ---------------- selection (2011-21 only)
    rows = []
    for name, M in Ms.items():
        for era, ss in SEL_ERAS.items():
            rows.append({"engine": name, "era": era, **era_metrics(M, n_by_season, ss)})
        rows.append({"engine": name, "era": "2011-21", **era_metrics(M, n_by_season, DEV + HOLD)})
    S = pd.DataFrame(rows)
    b = S[S.engine == "locked_v3"].set_index("era")
    qual = {}
    for name in EXTRA:
        c = S[S.engine == name].set_index("era")
        qual[name] = bool(all(c.loc[e, "log loss"] < b.loc[e, "log loss"] and
                              c.loc[e, "matched ROI @-110"] > b.loc[e, "matched ROI @-110"] for e in SEL_ERAS))
    ok = [n for n in EXTRA if qual[n]]
    selected = max(ok, key=lambda n: S[(S.engine == n) & (S.era == "2011-21")]["matched ROI @-110"].iloc[0]) if ok else None

    lines = ["# Improvement study 2 — stage and matchup features (NCAAB)\n",
             "_Pre-registered in `config/improvements.yaml` (`study_2`) before any candidate was fitted. "
             "Selection on 2011-21 only; the selected candidate is checked once on the sealed 2021-26 seasons._\n",
             "Matched volume: in each season, each engine's N most confident games, N = the locked engine's "
             f"number of P >= {P_MIN:.0%} bets that season (the choice of games never looks at results).\n",
             "## Selection (2011-21)\n", df_to_md(S, "{:.4f}"), "",
             "Qualifies (lower log loss AND higher matched ROI in both eras): "
             + ", ".join(f"{n} **{q}**" for n, q in qual.items()) + f". Selected: **{selected or 'none'}**.\n"]

    # ---------------- one-time confirmation (2021-26)
    verdict = None
    if selected:
        books = d.set_index("game_key").books_json
        crow = []
        for name in ("locked_v3", selected):
            crow.append({"engine": name, **era_metrics(Ms[name], n_by_season, CONF, real=True)})
        C = pd.DataFrame(crow).set_index("engine")
        c, l = C.loc[selected], C.loc["locked_v3"]
        verdict = bool(c["log loss"] < l["log loss"] and c["matched ROI @-110"] >= l["matched ROI @-110"]
                       and c["matched ROI real price"] >= l["matched ROI real price"])
        cards = []
        for name in ("locked_v3", selected):
            P, cals, calm = arms[name]
            R, _ = evaluate(P, cals, calm, books, CONF)
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
            cur["study_2"] = {"adopted": selected, "extra_mean_feats": EXTRA[selected],
                              "use": "2026-27 forward ledger: recorded next to the locked v3 engine"}
            path.write_text(yaml.safe_dump(cur, sort_keys=False))
    else:
        lines.append("No candidate qualified, so the 2021-26 seasons stay sealed.")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("study2_stage_matchup", {"pre_registration": CFG, "extra": EXTRA},
                   {"selection": S.to_dict("records"), "qualifies": qual, "selected": selected, "confirmed": verdict})


if __name__ == "__main__":
    main()
