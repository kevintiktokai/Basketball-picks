"""NCAAB point-in-time features for three markets: open, close, second-half.

All team-history features are computed from games on strictly earlier dates.
Second-half features additionally use this game's pre-game lines and its own
first-half score (known at half-time, when the 2H line is bet).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config_loader import ROOT
from features.ratings import DailyRatings

PROC = ROOT / "data" / "processed"


def _team_long(g: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game with the stats we track per team."""
    cols = ["game_key", "date", "season", "total", "line_close", "line_open", "first_half",
            "ok_close", "ok_open"]
    h = g[cols + ["home", "home_pts", "away_pts"]].rename(columns={"home": "team", "home_pts": "pf", "away_pts": "pa"})
    a = g[cols + ["away", "home_pts", "away_pts"]].rename(columns={"away": "team", "away_pts": "pf", "home_pts": "pa"})
    return pd.concat([h, a], ignore_index=True).sort_values(["team", "date"]).reset_index(drop=True)


def _ew_prior(s: pd.Series, groups: pd.Series, halflife: float) -> pd.Series:
    """EW mean of strictly previous values within group (shifted by one game)."""
    return s.groupby(groups).transform(lambda x: x.shift(1).ewm(halflife=halflife, min_periods=1).mean())


def team_history_features(g: pd.DataFrame, halflife: float = 8.0) -> pd.DataFrame:
    L = _team_long(g)
    L["resid_close"] = (L.total - L.line_close).where(L.ok_close)
    L["absres_close"] = L.resid_close.abs()
    L["resid_open"] = (L.total - L.line_open).where(L.ok_open)
    L["move"] = (L.line_close - L.line_open).where(L.ok_close & L.ok_open)
    L["fh_share"] = L.first_half / L.total
    key = L.team + "|" + L.season           # histories restart each season (prior via ratings)
    for c in ["resid_close", "absres_close", "resid_open", "move", "fh_share"]:
        L[f"h_{c}"] = _ew_prior(L[c], key, halflife)
    L["h_games"] = L.groupby(key).cumcount()
    L["prev_date"] = L.groupby(L.team)["date"].shift(1)
    L["rest"] = ((L.date - L.prev_date).dt.days).clip(upper=10).fillna(10)
    feats = ["h_resid_close", "h_absres_close", "h_resid_open", "h_move", "h_fh_share", "h_games", "rest"]
    return L[["game_key", "team"] + feats]


STYLE = ["efg", "efg_allowed", "tpar", "tpar_allowed", "ftr", "ftr_allowed", "orb", "orb_allowed",
         "tovr", "tovr_forced", "pace"]


def style_history_features(g: pd.DataFrame, box: pd.DataFrame, halflife: float = 8.0) -> pd.DataFrame:
    """Per team-game style stats from ESPN box scores, EW over the team's PRIOR games."""
    b = box[box.box_ok].copy()
    fga, fga_o = b.fga.clip(lower=1), b.fga_opp.clip(lower=1)
    b["efg"] = (b.fgm + 0.5 * b.fg3m) / fga
    b["efg_allowed"] = (b.fgm_opp + 0.5 * b.fg3m_opp) / fga_o
    b["tpar"] = b.fg3a / fga
    b["tpar_allowed"] = b.fg3a_opp / fga_o
    b["ftr"] = b.fta / fga
    b["ftr_allowed"] = b.fta_opp / fga_o
    b["orb"] = b.oreb / (b.oreb + b.dreb_opp).clip(lower=1)
    b["orb_allowed"] = b.oreb_opp / (b.oreb_opp + b.dreb).clip(lower=1)
    b["tovr"] = b.tov / b.poss
    b["tovr_forced"] = b.tov_opp / b.poss
    b["pace"] = b.poss
    stats = b[["espn_game_id", "team_id"] + STYLE]
    rows = []
    for side in ("home", "away"):
        x = g[["game_key", "date", "season", side, "espn_game_id", f"espn_{side}_id"]].rename(
            columns={side: "team", f"espn_{side}_id": "team_id"})
        rows.append(x)
    L = pd.concat(rows, ignore_index=True)
    L = L.merge(stats, on=["espn_game_id", "team_id"], how="left")
    L = L.sort_values(["team", "date"]).reset_index(drop=True)
    key = L.team + "|" + L.season
    out = L[["game_key", "team"]].copy()
    for c in STYLE:
        out[f"s_{c}"] = _ew_prior(L[c], key, halflife)
    return out


def build_ncaab_features(write: bool = True, ratings_kw: dict | None = None,
                         games: pd.DataFrame | None = None, box: pd.DataFrame | None = None) -> pd.DataFrame:
    g = pd.read_parquet(PROC / "ncaab_games.parquet") if games is None else games.copy()
    box = pd.read_parquet(PROC / "ncaab_box.parquet") if box is None else box.copy()
    g = g[g.clean].copy()
    poss = box[box.box_ok].drop_duplicates("espn_game_id").set_index("espn_game_id").poss
    g["poss"] = g.espn_game_id.map(poss)

    r = DailyRatings(**(ratings_kw or {"half_life_days": 45, "prev_season_weight": 0.15,
                                        "ridge": 3.0})).run(g)
    g = g.merge(r, on="game_key", how="left")
    if (pd.to_datetime(g.rt_asof) >= g.date).any():
        raise AssertionError("LEAKAGE: ratings as-of >= game date")

    th = team_history_features(g)
    hh = th.rename(columns=lambda c: c if c in ("game_key", "team") else f"home_{c}")
    aa = th.rename(columns=lambda c: c if c in ("game_key", "team") else f"away_{c}")
    g = g.merge(hh, left_on=["game_key", "home"], right_on=["game_key", "team"], how="left").drop(columns="team")
    g = g.merge(aa, left_on=["game_key", "away"], right_on=["game_key", "team"], how="left").drop(columns="team")

    sh = style_history_features(g, box)
    for side in ("home", "away"):
        x = sh.rename(columns=lambda c: c if c in ("game_key", "team") else f"{side}_{c}")
        g = g.merge(x, left_on=["game_key", side], right_on=["game_key", "team"], how="left").drop(columns="team")

    # league-level trailing environment (strictly earlier dates)
    daily = g.groupby("date").agg(n=("game_key", "size"),
                                  rc=("total", "sum"), lc=("line_close", "sum")).sort_index()
    ok = g[g.ok_close].groupby("date").agg(rsum=("total", "sum"), lsum=("line_close", "sum"),
                                           cnt=("total", "size"))
    ok = ok.reindex(daily.index).fillna(0)
    roll = ok.rolling(21, min_periods=1).sum().shift(1)
    lg_drift = (roll.rsum - roll.lsum) / roll.cnt
    lg_line = roll.lsum / roll.cnt
    g["lg_drift"] = g.date.map(lg_drift)
    g["lg_line"] = g.date.map(lg_line)
    g["slate_size"] = g.date.map(daily.n)            # schedule size: known in advance
    g["dow"] = g.date.dt.dayofweek
    g["month"] = g.date.dt.month
    g["rt_pts_total"] = g.rt_pts_home + g.rt_pts_away
    g["rt_min_games"] = np.minimum(g.rt_n_home, g.rt_n_away)
    if write:
        g.to_parquet(PROC / "ncaab_features.parquet", index=False)
    return g


# ------------------------------------------------------------------ markets
def market_frame(f: pd.DataFrame, market: str) -> pd.DataFrame:
    """Standardised frame for one market: line, outcome, and market-specific features.
    Columns: game_key, season, date, line, outcome, feats..., plus ids."""
    d = f.copy()
    if market == "open":
        d = d[d.ok_open]
        d["line"] = d.line_open
        d["outcome"] = d.total
        d["spread"] = d.home_spread_open
    elif market == "close":
        d = d[d.ok_close]
        d["line"] = d.line_close
        d["outcome"] = d.total
        d["spread"] = d.home_spread_close
        d["move"] = (d.line_close - d.line_open).where(d.ok_open)
    elif market == "second_half":
        d = d[d.ok_2h]
        d["line"] = d.line_2h
        d["outcome"] = d.second_half
        d["spread"] = d.home_spread_close
        exp_1h = d.line_close * d[["home_h_fh_share", "away_h_fh_share"]].mean(axis=1).fillna(0.48)
        d["fh_surplus"] = d.first_half - exp_1h
        d["fh_margin_abs"] = (d.home_1h - d.away_1h).abs()
        d["naive_2h"] = d.line_close - d.first_half
        d["x_2h_vs_naive"] = d.line_2h - d.naive_2h
        d["x_2h_vs_pregame"] = d.line_2h - (d.line_close - exp_1h)
        d["move"] = (d.line_close - d.line_open).where(d.ok_open)
    else:
        raise ValueError(market)
    d["market"] = market
    full_line = d.line if market != "second_half" else d.line_close
    d["x_pts"] = d.rt_pts_total - full_line
    d["x_eff"] = d.rt_eff_total - full_line
    # tempo relative to the league's trailing tempo (strictly earlier dates only)
    daily_poss = d.groupby("date").rt_poss.mean().sort_index()
    trail = daily_poss.rolling(30, min_periods=1).mean().shift(1)
    d["x_poss"] = d.rt_poss - d.date.map(trail)
    d["abs_spread"] = d.spread.abs()
    d["line_rel"] = full_line - d.lg_line
    d["vol_sum"] = d.home_h_absres_close + d.away_h_absres_close
    d["mkt_bias_sum"] = d.home_h_resid_close + d.away_h_resid_close
    d["open_bias_sum"] = d.home_h_resid_open + d.away_h_resid_open
    d["move_hist_sum"] = d.home_h_move + d.away_h_move
    d["rest_min"] = np.minimum(d.home_rest, d.away_rest)
    d["early"] = (d.rt_min_games < 6).astype(int)
    d["log_games"] = np.log1p(d.rt_min_games.fillna(0))
    d["neutral_i"] = d.neutral.astype(int)
    d["weekend"] = d.dow.isin([5, 6]).astype(int)
    d["march"] = (d.month == 3).astype(int)
    d["log_slate"] = np.log1p(d.slate_size)
    # style matchups: offence tendency + opponent's allowance
    for st, al in (("efg", "efg_allowed"), ("tpar", "tpar_allowed"), ("ftr", "ftr_allowed"),
                   ("orb", "orb_allowed"), ("tovr", "tovr_forced")):
        d[f"m_{st}"] = (d[f"home_s_{st}"] + d[f"away_s_{al}"] + d[f"away_s_{st}"] + d[f"home_s_{al}"])
    d["m_pace"] = d.home_s_pace + d.away_s_pace
    # team-total split vs spread-implied team totals
    imp_home = (full_line + d.spread) / 2
    imp_away = (full_line - d.spread) / 2
    d["x_home_tt"] = d.rt_pts_home - imp_home
    d["x_away_tt"] = d.rt_pts_away - imp_away
    d["x_tt_absdiff"] = (d.x_home_tt - d.x_away_tt).abs()
    d["x_pts_early"] = d.x_pts * d.early
    d["x_poss_early"] = d.x_poss * d.early
    d["resid"] = d.outcome - d.line
    d["over"] = (d.outcome > d.line).astype(int)
    d["push"] = d.outcome == d.line
    return d.reset_index(drop=True)
