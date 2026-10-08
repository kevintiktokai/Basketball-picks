"""ONE-TIME holdout of the locked European card strategy (config/europe_locked.yaml).

Holdout games: 2025-26, 2026-03-21 .. 2026-06-30, except the three samples analysed during
development. They were not fetched when the strategy was locked. This script refuses to run
before they are (>= 80% of the official games in the window must have odds) and refuses a
second run once reports/euro_holdout.md exists.

Reports every arm declared in the lock file (`evaluation`): the locked strategy executed 30
minutes after Pinnacle opens (primary), instantly and after 60 minutes, plus the baseline and
user-band comparison arms.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import pandas as pd
import yaml

import euro_dev_study as D
from backtest.analysis import df_to_md
from backtest.euro_cards import cards, decision_times, legs, summary
from config_loader import ROOT, log_experiment
from data.euroleague import parse as euro_parse
from euro_info_study import build as build_ratings
from euro_optimize import SAMPLES
from features.euro_market import close_board, fair_curve, timelines

OUT = ROOT / "reports" / "euro_holdout.md"
H_FROM, H_TO = pd.Timestamp("2026-03-21", tz="UTC"), pd.Timestamp("2026-07-01", tz="UTC")


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT.name} exists: the holdout is run once only.")
    lock = yaml.safe_load((ROOT / "config" / "europe_locked.yaml").read_text())
    T = timelines()
    T = T[(T.start >= H_FROM) & (T.start < H_TO) & ~T.fixture_id.isin(SAMPLES)]
    T = T.drop_duplicates(["fixture_id", "book", "line", "side", "t"])
    G, _ = euro_parse(["E2025", "U2025"])
    official = int(((pd.to_datetime(G.date) >= "2026-03-21") & (pd.to_datetime(G.date) < "2026-07-01")).sum())
    have = T.fixture_id.nunique()
    if have < 0.8 * official:
        raise SystemExit(f"holdout not fetched yet: odds for {have} of {official} games "
                         "(run `python -m data.oddspapi update` first)")
    final, F = D.results(T)
    R = build_ratings()
    model = F.set_index("fixture_id").game_key.map(R.set_index("game_key").exp_total)
    CC = fair_curve(close_board(T))
    pin = decision_times(T, "pinnacle_open")
    start = T.groupby("fixture_id").start.first()
    s = lock["strategy"]
    arms = {"locked": {k: s[k] for k in ("leg_ev_min", "leg_odds_band", "books", "model_agrees", "cards_per_date")}}
    arms.update({k: {kk: v[kk] for kk in ("leg_ev_min", "leg_odds_band", "books", "model_agrees", "cards_per_date")}
                 for k, v in lock["evaluation"]["comparison_arms"].items()})
    rows, kept = [], {}
    for delay in (30, 0, 60):
        w = pin + pd.Timedelta(minutes=delay)
        w = w[w < start.reindex(w.index) - pd.Timedelta(minutes=5)]
        L = legs(T, w, CC, final, model)
        for name, cfg in arms.items():
            C = cards(L, {**cfg, "leg_odds_band": tuple(cfg["leg_odds_band"]), "cards_per_date": str(cfg["cards_per_date"])})
            rows.append({"arm": name, "executed": f"Pinnacle open +{delay} min",
                         "primary": name == "locked" and delay == 30, **summary(C, n_boot=2000)})
            if name == "locked" and delay == 30:
                kept = C
    Rt = pd.DataFrame(rows)
    lines = ["# Europe: one-time holdout of the locked card strategy\n",
             f"Holdout games with odds: **{have}** of {official} official games (2026-03-21 .. 2026-06-30, "
             "development samples excluded). Strategy locked before these games were fetched "
             f"(revision {lock.get('selected_at_revision')}).\n",
             df_to_md(Rt, "{:.3f}"), "",
             "## Cards of the primary arm\n",
             df_to_md(kept, "{:.3f}") if len(kept) else "(no cards)", ""]
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("euro_holdout", {"lock": lock["strategy"]}, {"table": Rt.astype(str).to_dict("records")})


if __name__ == "__main__":
    main()
