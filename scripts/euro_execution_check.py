"""Europe: can a person actually catch the prices the card strategy needs? (development games)

1. How long do soft-book prices with value (EV > 1% against Pinnacle's fair price at its
   opening) stay unchanged afterwards?
2. The locked strategy, the baseline and the user's odds band executed 0-120 minutes after
   Pinnacle opens.
3. The same rules at fixed clock times (24 h ... 1 h before tip, 10:00 on game day).

Writes reports/euro_execution.md. Development games only.
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
from euro_info_study import build as build_ratings
from euro_optimize import dev_timelines
from features.euro_market import close_board, fair_curve


def rules():
    lock = yaml.safe_load((ROOT / "config" / "europe_locked.yaml").read_text())
    pick = lambda d: {k: (tuple(d[k]) if k == "leg_odds_band" else (str(d[k]) if k == "cards_per_date" else d[k]))  # noqa: E731
                      for k in ("leg_ev_min", "leg_odds_band", "books", "model_agrees", "cards_per_date")}
    out = {"locked": pick(lock["strategy"])}
    out.update({k: pick(v) for k, v in lock["evaluation"]["comparison_arms"].items()})
    return out


def main():
    T = dev_timelines()
    final, F = D.results(T)
    G = build_ratings()
    model = F.set_index("fixture_id").game_key.map(G.set_index("game_key").exp_total)
    CC = fair_curve(close_board(T))
    start = T.groupby("fixture_id").start.first()
    pin = decision_times(T, "pinnacle_open")

    L0 = legs(T, pin, CC, final, model)
    V = L0[L0.ev_now > 0.01]
    nxt = T.merge(pin.rename("when"), left_on="fixture_id", right_index=True)
    nxt = nxt[nxt.t > nxt.when].groupby(["fixture_id", "book", "line", "side"]).t.min().rename("next_change")
    V = V.merge(nxt.reset_index(), on=["fixture_id", "book", "line", "side"], how="left")
    mins = ((V.next_change - V.fixture_id.map(pin)).dt.total_seconds() / 60).fillna(1e9)
    P = pd.DataFrame([{"value legs at Pinnacle's opening": len(V), "median minutes until the price changed":
                       float(mins.median()), **{f"still there after {m} min": float((mins >= m).mean())
                                                for m in (15, 30, 60, 120)}}])

    R = rules()
    rows = []
    for delay in (0, 15, 30, 60, 120):
        w = pin + pd.Timedelta(minutes=delay)
        w = w[w < start.reindex(w.index) - pd.Timedelta(minutes=5)]
        L = legs(T, w, CC, final, model)
        for name, cfg in R.items():
            s = summary(cards(L, cfg))
            rows.append({"executed": f"Pinnacle open +{delay} min", "rule": name, "cards": s.get("cards", 0),
                         "mean odds": s.get("mean odds"), "mean CLV": s.get("mean CLV"), "both won": s.get("both won")})
    Dl = pd.DataFrame(rows)
    rows = []
    for dt in ("pinnacle_open", "24h", "12h", "game_day_10am", "6h", "3h", "1h"):
        L = legs(T, decision_times(T, dt), CC, final, model)
        for name, cfg in R.items():
            s = summary(cards(L, cfg))
            rows.append({"decision time": dt, "rule": name, "cards": s.get("cards", 0), "mean CLV": s.get("mean CLV")})
    Ck = pd.DataFrame(rows)
    hrs = (start.reindex(pin.index) - pin).dt.total_seconds() / 3600
    lines = ["# Europe: can the card prices actually be caught? (development games)\n",
             f"Pinnacle opens a game's totals a median **{hrs.median():.0f} hours** before tip-off, typically around "
             f"**{pin.dt.tz_convert('Europe/Madrid').dt.hour.median():.0f}:00 Madrid time** the day before.\n",
             "## 1. How long the value prices last\n", df_to_md(P, "{:.3f}"), "",
             "## 2. Acting 0-120 minutes after Pinnacle opens\n", df_to_md(Dl, "{:.3f}"), "",
             "## 3. Acting at fixed clock times\n", df_to_md(Ck, "{:.3f}"), "",
             "Reading: the value is largest in the first minutes after Pinnacle opens and about halves for a "
             "person acting 30-60 minutes later; at mid-morning on game day it is mostly gone, and some returns "
             "in the last hours before tip-off."]
    (ROOT / "reports" / "euro_execution.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("euro_execution_check", {"rules": {k: str(v) for k, v in R.items()}},
                   {"persistence": P.to_dict("records"), "delays": Dl.astype(str).to_dict("records")})


if __name__ == "__main__":
    main()
