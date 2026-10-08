"""Live NCAAB two-pick card engine — the LOCKED stage-2 engine applied to a new date.

Pipeline (identical code paths to the backtests):
  1. history  = SBR archive (2007-08..2020-21) + sportsbookreview.com seasons
                (2021-22..current, cached scrape) + ESPN box scores (hoopR)
  2. slate    = the target date's games with opening totals (auto-fetched from
                sportsbookreview.com, or a user CSV)
  3. features = features/ncaab_features.py (point-in-time; slate games carry no outcome)
  4. model    = walk-forward per config/stage2_locked.yaml (current season predicted by a
                model trained on earlier seasons; calibrator from earlier OOS seasons)
  5. card     = buffered two-pick card, conservative joint >= locked target
"""
from __future__ import annotations

import difflib
import json

import numpy as np
import pandas as pd
import yaml

from backtest.wf2 import K_GRID, buffered_cards, leg_table, main_line_probs, walk_forward_market
from config_loader import ROOT
from data.ncaab_unify import load_all_box, load_schedules, unify
from features.ncaab_features import build_ncaab_features, market_frame

PROC = ROOT / "data" / "processed"


def season_of(d: pd.Timestamp) -> str:
    y = d.year if d.month >= 7 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


class NameResolver:
    """Map free-text team names to unified team keys (ESPN ids)."""

    def __init__(self, games: pd.DataFrame, box: pd.DataFrame):
        pairs = pd.concat([
            games[["home_name", "home"]].rename(columns={"home_name": "name", "home": "key"}),
            games[["away_name", "away"]].rename(columns={"away_name": "name", "away": "key"}),
        ]).dropna()
        b = box[["team_name", "team_id"]].dropna().drop_duplicates()
        pairs = pd.concat([pairs, pd.DataFrame({"name": b.team_name, "key": "e" + b.team_id.astype(int).astype(str)})])
        pairs["norm"] = pairs.name.map(self._norm)
        top = pairs.groupby(["norm", "key"]).size().reset_index(name="n").sort_values("n", ascending=False)
        self.map = dict(top.drop_duplicates("norm")[["norm", "key"]].values)
        self.names = list(self.map)

    @staticmethod
    def _norm(s: str) -> str:
        return "".join(ch for ch in str(s).lower() if ch.isalnum())

    def __call__(self, name: str) -> tuple[str, str]:
        n = self._norm(name)
        if n in self.map:
            return self.map[n], "exact"
        cand = difflib.get_close_matches(n, self.names, n=1, cutoff=0.75)
        if cand:
            return self.map[cand[0]], f"fuzzy:{cand[0]}"
        return f"unknown:{name}", "unknown"


def pending_from_sbr(date: str) -> pd.DataFrame:
    """Scheduled (not yet final) games on `date` with opening totals, from the SBR cache."""
    from data import sbr_live
    rows = []
    tot = sbr_live.RAW / "totals" / f"{date}.json"
    spr = sbr_live.RAW / "spread" / f"{date}.json"
    sp = {}
    for r in sbr_live._rows(spr) if spr.exists() else []:
        vals = [(o.get("openingLine") or {}).get("homeSpread") for o in r["oddsViews"] if o]
        vals = [v for v in vals if v is not None]
        sp[r["gameView"]["gameId"]] = -float(np.median(vals)) if vals else np.nan
    for r in sbr_live._rows(tot) if tot.exists() else []:
        gv = r["gameView"]
        if str(gv.get("gameStatusText", "")).startswith("Final"):
            continue
        books = {}
        for o in r["oddsViews"]:
            if o and (o.get("openingLine") or {}).get("total") is not None:
                books[o["sportsbook"]] = {"open": o["openingLine"]["total"],
                                          "open_over": o["openingLine"].get("overOdds"),
                                          "open_under": o["openingLine"].get("underOdds"),
                                          "current": (o.get("currentLine") or {}).get("total"),
                                          "current_over": (o.get("currentLine") or {}).get("overOdds"),
                                          "current_under": (o.get("currentLine") or {}).get("underOdds")}
        if not books:
            continue
        rows.append({"home_name": gv["homeTeam"]["fullName"], "away_name": gv["awayTeam"]["fullName"],
                     "line_open": float(np.median([b["open"] for b in books.values()])),
                     "home_spread_open": sp.get(gv["gameId"], np.nan), "books_json": json.dumps(books),
                     "start": gv.get("startDate"), "neutral": None})
    return pd.DataFrame(rows)


def engine_spec(engine: str = "v3"):
    """v2 = config/stage2_locked.yaml; v3 = v2 + recency weights + J from stage3_v3_locked.yaml."""
    lock = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())
    m, cp = lock["model"], dict(lock["card_policy"])
    decays = (None, None)
    if engine == "v3":
        v3 = yaml.safe_load((ROOT / "config" / "stage3_v3_locked.yaml").read_text())["changes_vs_v2"]
        cp["joint_target"] = v3["joint_target"]
        decays = (v3["train_decay"], v3["calib_decay"])
    return lock, m, cp, decays


def _prev_season(season: str) -> str:
    y = int(season[:4]) - 1
    return f"{y}-{str(y + 1)[2:]}"


def cached_features(allg: pd.DataFrame, box: pd.DataFrame, season: str) -> pd.DataFrame:
    """Features via the shared store (features/store.py): completed seasons are reused,
    only the current season (with today's slate) is recomputed."""
    from features.store import get_features
    return get_features("ncaab", allg, box, verbose=False)


def run_card(date: str, slate: pd.DataFrame | None = None, engine: str = "v3") -> dict:
    """slate (optional): columns home, away, line_open[, home_spread_open, neutral]."""
    lock, m, cp, decays = engine_spec(engine)
    D = pd.Timestamp(date)
    season = season_of(D)

    u, box, _ = unify(write=False, include_live=(PROC / "ncaab_live_raw.parquet").exists())
    u = u[u.date < D]                                    # strictly past games as history
    resolver = NameResolver(u, box)
    if slate is None:
        slate = pending_from_sbr(date)
    else:
        slate = slate.rename(columns={"home": "home_name", "away": "away_name", "line": "line_open"})
        if {"over_odds", "under_odds"} <= set(slate.columns):
            def amer(dec):
                dec = float(dec)
                return round((dec - 1) * 100) if dec >= 2 else round(-100 / (dec - 1))
            slate["books_json"] = [json.dumps({"user": {"open": float(r.line_open), "open_over": amer(r.over_odds),
                                                        "open_under": amer(r.under_odds)}})
                                   for r in slate.itertuples()]
    if slate.empty:
        return {"date": date, "error": "no games with opening totals found for this date"}
    slate = slate.copy()
    keys = [resolver(n) for n in slate.home_name], [resolver(n) for n in slate.away_name]
    slate["home"] = [k for k, _ in keys[0]]
    slate["away"] = [k for k, _ in keys[1]]
    slate["match_home"] = [h for _, h in keys[0]]
    slate["match_away"] = [h for _, h in keys[1]]
    sched = load_schedules()
    slate["neutral"] = slate.get("neutral").fillna(False).astype(bool) if "neutral" in slate else False
    slate["date"] = D
    slate["season"] = season
    slate["game_key"] = "P" + D.strftime("%Y%m%d") + "_" + slate.away + "@" + slate.home
    for c in ["home_pts", "away_pts", "total", "first_half", "second_half", "line_close", "line_2h",
              "home_spread_close", "home_spread_2h", "ml_home", "ml_away", "home_1h", "away_1h",
              "home_2h_reg", "away_2h_reg", "espn_game_id", "espn_home_id", "espn_away_id"]:
        if c not in slate:
            slate[c] = np.nan
    slate["quality_flags"] = ""
    slate["clean"] = True
    slate["ok_open"] = slate.line_open.between(95, 200)
    slate["ok_close"] = False
    slate["ok_2h"] = False
    slate["source"] = "pending"
    slate = slate[~slate.home.str.startswith("unknown") & ~slate.away.str.startswith("unknown")]
    allg = pd.concat([u, slate[[c for c in u.columns if c in slate.columns]]], ignore_index=True)

    f = cached_features(allg, box[box.date < D], season)
    d = market_frame(f, lock["market"])
    seasons = sorted(s for s in d.season.unique() if s <= season)
    P, cals, calm = walk_forward_market(d, m["mean_feats"], m["var_feats"], m["kind"], m["shape"],
                                        m["alpha"], seasons=seasons, min_games=m["min_games"],
                                        train_decay=decays[0], calib_decay=decays[1])
    today = P[P.date == D].copy()
    if today.empty or season not in cals:
        return {"date": date, "error": "slate games not eligible (too few games played this season)"}
    # stage-3 odds-targeted products (config/stage3_locked.yaml)
    from backtest.odds_cards import build_legs, odds_cards
    lock3 = yaml.safe_load((ROOT / "config" / "stage3_locked.yaml").read_text())["products"]
    tc = lock3["target_card"]
    books = today.set_index("game_key").books_json if "books_json" in today else None
    legs = build_legs(today, cals, calm, books=books, alt_ref="median")
    target = odds_cards(legs, floor=tc["min_combined_odds"], objective=tc["objective"],
                        leg_band=tuple(tc["leg_odds_band"]), margin=tc["alt_price_margin"])
    main_double = odds_cards(legs, floor=lock3["main_line_double"]["min_combined_odds"],
                             objective="ev", main_only=True)
    T = leg_table(today, cals, calm)
    C = buffered_cards(T, joint_target=cp["joint_target"], max_buffer=cp["max_buffer_points"],
                       top_legs=cp["top_legs"], rho_lo=cp["rho_lo"])
    M = main_line_probs(today, cals)
    lock = dict(lock, card_policy=cp, engine=engine)
    return {"date": date, "lock": lock, "slate": slate, "frame": T["frame"], "T": T, "card": C,
            "target_card": target, "main_double": main_double, "legs": legs,
            "main": M, "n_screened": int(len(today)), "n_eligible": int(today.eligible.sum())}
