"""Europe: optimise the two-leg card strategy on the development games.

The grid, objective and selection rule were declared in config/europe.yaml (section
`optimisation`) and committed before this script was run. Development games only:
2026-01-20 .. 2026-03-20 plus the three sample games already analysed; the holdout
(2026-03-21 .. 2026-06-30) is excluded here even after it is fetched.

Writes reports/euro_optimize.md and config/europe_locked.yaml (the selected strategy). Refuses to
run once the lock file exists, unless --relock is passed (a new, disclosed development round).
"""
from __future__ import annotations

import itertools
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

import euro_dev_study as D
from backtest.analysis import df_to_md
from backtest.euro_cards import cards, decision_times, legs, summary
from config_loader import ROOT, log_experiment
from euro_info_study import build as build_ratings
from features.euro_market import close_board, fair_curve, timelines

CFG = yaml.safe_load((ROOT / "config" / "europe.yaml").read_text())["optimisation"]
DEV_FROM, DEV_TO = pd.Timestamp("2026-01-20", tz="UTC"), pd.Timestamp("2026-03-21", tz="UTC")
SAMPLES = {"id1100014170121994", "id1100013862096300", "id1100013870907956"}   # analysed in Q1-Q4


def dev_timelines() -> pd.DataFrame:
    T = timelines()
    dev = ((T.start >= DEV_FROM) & (T.start < DEV_TO)) | T.fixture_id.isin(SAMPLES)
    return T[dev].drop_duplicates(["fixture_id", "book", "line", "side", "t"])


def grid():
    g = CFG["grid"]
    for ev, band, books, model, per in itertools.product(g["leg_ev_min"], g["leg_odds_band"], g["books"],
                                                         g["model_agrees"], g["cards_per_date"]):
        yield {"leg_ev_min": ev, "leg_odds_band": tuple(band), "books": books, "model_agrees": model,
               "cards_per_date": str(per)}


def best(R: pd.DataFrame, col: str, min_cards: int) -> pd.Series:
    ok = R[R[f"{col}_cards"] >= min_cards]
    return ok.sort_values([f"{col}_clv", f"{col}_cards"], ascending=[False, False]).iloc[0]


def main():
    lock_path = ROOT / "config" / "europe_locked.yaml"
    if lock_path.exists() and "--relock" not in sys.argv:
        raise SystemExit("config/europe_locked.yaml exists: the strategy is locked. Re-running would replace it; "
                         "pass --relock only for a new, disclosed development round.")
    T = dev_timelines()
    final, F = D.results(T)
    G = build_ratings()
    model = F.set_index("fixture_id").game_key.map(G.set_index("game_key").exp_total)
    CC = fair_curve(close_board(T))
    dates = sorted(T.start.dt.tz_convert("Europe/Madrid").dt.date.unique())
    split = dates[len(dates) // 2]
    fold = lambda C: (C.date < split) if not C.empty else []           # noqa: E731

    rows, store = [], {}
    for dt in CFG["grid"]["decision_time"]:
        L = legs(T, decision_times(T, dt), CC, final, model)
        for cfg in grid():
            C = cards(L, cfg)
            key = (dt,) + tuple(cfg.values())
            store[key] = C
            r = {"decision_time": dt, **cfg}
            for name, part in (("all", C), ("A", C[fold(C)] if len(C) else C), ("B", C[~fold(C)] if len(C) else C)):
                r[f"{name}_cards"] = len(part)
                r[f"{name}_clv"] = part.clv.mean() if len(part) else np.nan
                r[f"{name}_roi"] = part.pnl.mean() if len(part) else np.nan
                r[f"{name}_won"] = part.win.mean() if len(part) else np.nan
            rows.append(r)
    R = pd.DataFrame(rows)
    params = ["decision_time", "leg_ev_min", "leg_odds_band", "books", "model_agrees", "cards_per_date"]

    # honest estimate: select on one half of the dates, score on the other
    nested = []
    for sel, ev in (("A", "B"), ("B", "A")):
        b = best(R, sel, 4)
        nested.append({"selected on": f"{'first' if sel == 'A' else 'second'} half",
                       **{p: b[p] for p in params}, f"selection-half CLV": b[f"{sel}_clv"],
                       "scored on": f"{'second' if ev == 'B' else 'first'} half", "cards": b[f"{ev}_cards"],
                       "CLV": b[f"{ev}_clv"], "both won": b[f"{ev}_won"], "ROI": b[f"{ev}_roi"]})
    N = pd.DataFrame(nested)

    final_pick = best(R, "all", 8)
    key = tuple(final_pick[p] for p in params)
    C = store[key].sort_values("date").reset_index(drop=True)
    S = summary(C, n_boot=2000)
    top = R[R.all_cards >= 8].sort_values("all_clv", ascending=False).head(15)
    freq = {p: top[p].astype(str).value_counts().to_dict() for p in params}
    # baseline for comparison: the Q4 card rule (Pinnacle open, any positive EV, 1.40-1.90, all books)
    base = R[(R.decision_time == "pinnacle_open") & (R.leg_ev_min == 0.0)
             & R.leg_odds_band.apply(lambda x: tuple(x) == (1.4, 1.9))
             & (R.books == "all_soft") & (~R.model_agrees.astype(bool)) & (R.cards_per_date == "1")].iloc[0]

    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    strategy = {p: (list(final_pick[p]) if p == "leg_odds_band" else
                    (bool(final_pick[p]) if p == "model_agrees" else
                     (float(final_pick[p]) if p == "leg_ev_min" else str(final_pick[p])))) for p in params}
    strategy["min_combined_odds"] = 2.5
    locked = {"comment": "LOCKED European card strategy, selected on development games by the rule declared in "
                         "config/europe.yaml (optimisation). Committed BEFORE the holdout (2026-03-21..06-30) is "
                         "fetched and before any 2026-27 result is compared with a line.",
              "strategy": strategy,
              "dev_evidence": {k: (list(map(float, v)) if isinstance(v, tuple) else
                                   (float(v) if isinstance(v, (float, np.floating)) else int(v) if isinstance(v, (int, np.integer)) else v))
                               for k, v in S.items()},
              "nested_cv": N[["selected on", "cards", "CLV", "both won", "ROI"]].to_dict("records"),
              "configs_tried": len(R), "selected_at_revision": rev}
    (ROOT / "config" / "europe_locked.yaml").write_text(yaml.safe_dump(locked, sort_keys=False, allow_unicode=True))

    pnl = C.pnl.cumsum()
    lines = ["# Europe: optimising the two-leg card strategy (development games)\n",
             f"Development games: **{T.fixture_id.nunique()}** ({D.DEV_FROM.date()} .. 2026-03-20 plus 3 samples), "
             f"{len(dates)} match dates; strategies tried: **{len(R)}** "
             f"({len(CFG['grid']['decision_time'])} decision times x {len(R) // len(CFG['grid']['decision_time'])} "
             "leg/card rules). Objective: mean joint CLV per card against Pinnacle's close.\n",
             "## Honest estimate (nested time split)\n",
             "Choose the best strategy on one half of the dates, then score it on the other half. "
             "This is what to expect from the selection procedure on unseen games.\n",
             df_to_md(N, "{:.3f}"), "",
             "## Selected strategy (best on all development games, >= 8 cards)\n",
             "```", yaml.safe_dump(strategy, sort_keys=False).strip(), "```", "",
             df_to_md(pd.DataFrame([S]), "{:.3f}"), "",
             f"Baseline (Q4 rule: when Pinnacle opens, any positive EV, legs 1.40-1.90, all books, one card per "
             f"date): {int(base.all_cards)} cards, CLV {base.all_clv:+.3f}, both won {base.all_won:.3f}, "
             f"ROI {base.all_roi:+.3f}.\n",
             "How often each setting appears among the 15 best strategies (robustness):\n",
             "\n".join(f"* {p}: {v}" for p, v in freq.items()), "",
             "## Every card of the selected strategy (the backtest)\n",
             df_to_md(C.assign(cum_units=pnl)[["date", "leg_a", "leg_b", "odds", "ev", "clv", "win", "pnl", "cum_units"]],
                      "{:.3f}"), "",
             "## Caveats\n",
             "* About 100 usable games: the best of hundreds of strategies is flattered by selection; "
             "trust the nested estimate and the holdout, not the in-sample ROI.",
             "* Results depend on the soft-book prices in the OddsPapi feed being available when shown; "
             "a live check of prices is part of the forward test.",
             "* Locked in `config/europe_locked.yaml`; next checks: holdout (21 Mar - Jun 2026, once fetched), "
             "then the 2026-27 test."]
    (ROOT / "reports" / "euro_optimize.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:14]))
    print(df_to_md(pd.DataFrame([S]), "{:.3f}"))
    log_experiment("euro_optimize", {"grid": CFG["grid"], "split_date": str(split)},
                   {"nested": N.to_dict("records"), "selected": strategy, "summary": {k: str(v) for k, v in S.items()},
                    "n_configs": len(R)})


if __name__ == "__main__":
    main()
