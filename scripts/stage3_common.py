"""Shared evaluation of the LOCKED stage-3 products (config/stage3_locked.yaml)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import yaml

from backtest.odds_cards import build_legs, odds_cards, summarize
from config_loader import ROOT


def locked():
    return yaml.safe_load((ROOT / "config" / "stage3_locked.yaml").read_text())


def product_runs(lock: dict):
    t = lock["products"]["target_card"]
    m = lock["products"]["main_line_double"]
    base = dict(floor=t["min_combined_odds"], objective=t["objective"], leg_band=tuple(t["leg_odds_band"]),
                margin=t["alt_price_margin"])
    return [
        ("TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob)", "median", dict(base)),
        ("  sensitivity: alternate margin 8%", "median", dict(base, margin=0.08)),
        ("  stress: alternates priced off the CLOSE", "median", dict(base, settle_price_ref="close")),
        ("  variant: alternates shopped at best book", "best_book", dict(base)),
        ("MAIN-LINE DOUBLE (real prices only)", "median",
         dict(floor=m["min_combined_odds"], objective=m["objective"], main_only=True)),
    ]


def evaluate(P, cals, calm, books, eval_seasons, label_prefix=""):
    lock = locked()
    legs = {}
    rows, cards = [], {}
    n_slates_all = P[P.calibrated & P.eligible & P.season.isin(eval_seasons)].date.nunique()
    for name, ladder, kw in product_runs(lock):
        if ladder not in legs:
            legs[ladder] = build_legs(P, cals, calm, books=books, alt_ref=ladder)
        C = odds_cards(legs[ladder], **kw)
        C = C[C.season.isin(eval_seasons)]
        cards[name] = C
        for season in list(eval_seasons) + ["POOLED"]:
            c = C if season == "POOLED" else C[C.season == season]
            ns = n_slates_all if season == "POOLED" else \
                P[P.calibrated & P.eligible & (P.season == season)].date.nunique()
            s = summarize(c, ns)
            rows.append({"product": label_prefix + name, "season": season, "cards": s.get("cards"),
                         "pct_slates": s.get("pct_slates"), "hit": s.get("hit_rate"),
                         "hit_ci95": s.get("hit_ci95"), "avg_odds": s.get("avg_combined_odds"),
                         "breakeven": s.get("breakeven_hit"), "model_hit": s.get("model_hit"),
                         "leg_win": s.get("leg_win"), "leg_p": s.get("leg_model_p"),
                         "roi": s.get("roi"), "roi_ci95": s.get("roi_ci95"), "units": s.get("units"),
                         "max_dd": s.get("max_drawdown"), "losing_run": s.get("longest_losing_run")})
    return pd.DataFrame(rows), cards
