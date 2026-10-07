"""Point-in-time (PIT) feature engineering.

Every feature for a game played on date D is computed from team state that has
been updated ONLY with games played on dates strictly before D. Games on the
same date never see each other. This is enforced structurally: the builder
walks dates in order, emits features for all of D's games from the current
state, and only then folds D's results into the state.

Each emitted row carries `feature_asof` = the latest game date that
contributed to its features; the leakage tests assert feature_asof < date.

Two feature families:
  * score-only (all seasons): opponent-adjusted scoring ratings, market-implied
    team tendencies, rest, schedule, league trend.
  * box-score (2010-11..2023-24): pace and four-factor efficiencies, for and
    against, combined into a possessions x efficiency expected total.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config_loader import load_config

BOX_STATS = ["pace", "ortg", "drtg", "efg", "efg_allowed", "tpar", "tpar_allowed",
             "ftr", "ftr_allowed", "orb", "orb_allowed", "tov", "tov_forced"]


@dataclass
class EW:
    """Exponentially-weighted mean with an explicit prior weight (shrinkage)."""
    value: float
    weight: float

    def update(self, x: float, decay: float) -> None:
        w = self.weight * decay
        self.value = (self.value * w + x) / (w + 1.0)
        self.weight = w + 1.0


@dataclass
class TeamState:
    off: float = 0.0            # points scored above league expectation
    dfn: float = 0.0            # points allowed above league expectation
    n_season: int = 0
    last_date: pd.Timestamp | None = None
    last_season: str | None = None
    line_tend: EW = field(default_factory=lambda: EW(0.0, 0.0))   # market's view: team line - league line
    ou_resid: EW = field(default_factory=lambda: EW(0.0, 0.0))    # recent (total - line): "over trend"
    pts_for: EW = field(default_factory=lambda: EW(0.0, 0.0))     # raw recent scoring (naive feature)
    pts_against: EW = field(default_factory=lambda: EW(0.0, 0.0))
    box: dict = field(default_factory=dict)                       # stat -> EW
    box_n_season: int = 0


class FeatureBuilder:
    def __init__(self, k_rating: float = 0.08, halflife: float | None = None,
                 prior_games: float | None = None, season_regress: float = 0.4):
        cfg = load_config()["features"]
        self.halflife = halflife or cfg["ewm_halflife_games"]
        self.prior_games = prior_games or cfg["prior_shrink_games"]
        self.decay = 0.5 ** (1.0 / self.halflife)
        self.k = k_rating
        self.season_regress = season_regress
        self.teams: dict[str, TeamState] = {}
        # league environment (trailing, past only)
        self.lg_total = EW(200.0, 1.0)
        self.lg_line = EW(200.0, 1.0)
        self.lg_box = {s: EW(np.nan, 0.0) for s in BOX_STATS}
        self.lg_decay = 0.5 ** (1.0 / 150.0)        # ~150 games league memory
        self.home_adv = EW(0.0, 50.0)               # home minus away scoring vs expectation
        self.last_update_date: pd.Timestamp | None = None

    # ------------------------------------------------------------------ state
    def _team(self, code: str, season: str) -> TeamState:
        t = self.teams.setdefault(code, TeamState())
        if t.last_season != season:
            # new season: regress toward league, keep reduced weight as prior
            r = self.season_regress
            t.off *= (1 - r)
            t.dfn *= (1 - r)
            for ew in (t.line_tend, t.ou_resid):
                ew.value *= (1 - r)
                ew.weight = min(ew.weight, self.prior_games)
            for ew in (t.pts_for, t.pts_against):
                ew.weight = min(ew.weight, self.prior_games)
            for s, ew in t.box.items():
                lg = self.lg_box[s].value
                if not math.isnan(lg):
                    ew.value = (1 - r) * ew.value + r * lg
                ew.weight = min(ew.weight, self.prior_games)
            t.n_season = 0
            t.box_n_season = 0
            t.last_season = season
        return t

    # ------------------------------------------------------------- emission
    def _expected(self, home: TeamState, away: TeamState) -> tuple[float, float]:
        half = self.lg_total.value / 2.0
        h = half + self.home_adv.value / 2 + home.off + away.dfn
        a = half - self.home_adv.value / 2 + away.off + home.dfn
        return h, a

    def _box_expected_total(self, home: TeamState, away: TeamState) -> float:
        need = ["pace", "ortg", "drtg"]
        if not all(s in home.box and s in away.box for s in need):
            return np.nan
        lg_pace = self.lg_box["pace"].value
        lg_rtg = self.lg_box["ortg"].value
        if math.isnan(lg_pace) or math.isnan(lg_rtg):
            return np.nan
        poss = home.box["pace"].value * away.box["pace"].value / lg_pace
        ppp_h = home.box["ortg"].value * away.box["drtg"].value / lg_rtg
        ppp_a = away.box["ortg"].value * home.box["drtg"].value / lg_rtg
        return poss * (ppp_h + ppp_a) / 100.0

    def emit(self, g: pd.Series) -> dict:
        hs = self._team(g.home, g.season)
        aw = self._team(g.away, g.season)
        exp_h, exp_a = self._expected(hs, aw)
        row = {
            "game_id": g.game_id,
            "feature_asof": self.last_update_date,
            "lg_total_trailing": self.lg_total.value,
            "lg_line_trailing": self.lg_line.value,
            "lg_total_minus_line": self.lg_total.value - self.lg_line.value,
            "rating_exp_home": exp_h,
            "rating_exp_away": exp_a,
            "rating_exp_total": exp_h + exp_a,
            "naive_ppg_total": (hs.pts_for.value + aw.pts_for.value + hs.pts_against.value
                                + aw.pts_against.value) / 2.0
            if hs.pts_for.weight > 0 and aw.pts_for.weight > 0 else np.nan,
            "home_line_tend": hs.line_tend.value,
            "away_line_tend": aw.line_tend.value,
            "home_ou_trend": hs.ou_resid.value,
            "away_ou_trend": aw.ou_resid.value,
            "home_games_season": hs.n_season,
            "away_games_season": aw.n_season,
            "min_games_season": min(hs.n_season, aw.n_season),
            "home_rest": (g.date - hs.last_date).days if hs.last_date is not None else 7,
            "away_rest": (g.date - aw.last_date).days if aw.last_date is not None else 7,
            "box_exp_total": self._box_expected_total(hs, aw),
            "box_min_games_season": min(hs.box_n_season, aw.box_n_season),
        }
        row["home_rest"] = min(row["home_rest"], 7)
        row["away_rest"] = min(row["away_rest"], 7)
        row["home_b2b"] = int(row["home_rest"] == 1)
        row["away_b2b"] = int(row["away_rest"] == 1)
        for s in BOX_STATS:
            row[f"home_{s}"] = hs.box[s].value if s in hs.box else np.nan
            row[f"away_{s}"] = aw.box[s].value if s in aw.box else np.nan
        lg_pace = self.lg_box["pace"].value
        row["box_exp_pace"] = (row["home_pace"] * row["away_pace"] / lg_pace
                               if not math.isnan(lg_pace) and not math.isnan(row["home_pace"])
                               and not math.isnan(row["away_pace"]) else np.nan)
        return row

    # --------------------------------------------------------------- update
    def update(self, g: pd.Series, box_home: pd.Series | None, box_away: pd.Series | None) -> None:
        hs = self._team(g.home, g.season)
        aw = self._team(g.away, g.season)
        exp_h, exp_a = self._expected(hs, aw)
        err_h = g.home_pts - exp_h
        err_a = g.away_pts - exp_a
        k = self.k
        hs.off += k * err_h
        aw.dfn += k * err_h
        aw.off += k * err_a
        hs.dfn += k * err_a
        self.home_adv.update((g.home_pts - g.away_pts) - (exp_h - exp_a) + self.home_adv.value,
                             0.5 ** (1 / 500))
        lg_line_now = self.lg_line.value
        for t, pf, pa in ((hs, g.home_pts, g.away_pts), (aw, g.away_pts, g.home_pts)):
            t.line_tend.update(g.line - lg_line_now, self.decay)
            t.ou_resid.update(g.total - g.line, self.decay)
            t.pts_for.update(pf, self.decay)
            t.pts_against.update(pa, self.decay)
            t.n_season += 1
            t.last_date = g.date
        self.lg_total.update(g.total, self.lg_decay)
        self.lg_line.update(g.line, self.lg_decay)

        if box_home is not None and box_away is not None:
            for t, b in ((hs, box_home), (aw, box_away)):
                stats = box_stats(b)
                for s, x in stats.items():
                    if s not in t.box:
                        lg = self.lg_box[s].value
                        t.box[s] = EW(x if math.isnan(lg) else lg, self.prior_games / 2)
                    t.box[s].update(x, self.decay)
                    lg_ew = self.lg_box[s]
                    if math.isnan(lg_ew.value):
                        lg_ew.value, lg_ew.weight = x, 1.0
                    else:
                        lg_ew.update(x, self.lg_decay)
                t.box_n_season += 1


def box_stats(b: pd.Series) -> dict:
    poss = b.poss
    mins = max(b.minutes, 48.0)
    fga, fga_o = max(b.FGA, 1), max(b.FGA_opp, 1)
    return {
        "pace": poss * 48.0 / mins,
        "ortg": 100.0 * b.PTS / poss,
        "drtg": 100.0 * b.PTS_opp / poss,
        "efg": (b.FGM + 0.5 * b.FG3M) / fga,
        "efg_allowed": (b.FGM_opp + 0.5 * b.FG3M_opp) / fga_o,
        "tpar": b.FG3A / fga,
        "tpar_allowed": b.FG3A_opp / fga_o,
        "ftr": b.FTA / fga,
        "ftr_allowed": b.FTA_opp / fga_o,
        "orb": b.OREB / max(b.OREB + b.DREB_opp, 1),
        "orb_allowed": b.OREB_opp / max(b.OREB_opp + b.DREB, 1),
        "tov": b.TOV / poss,
        "tov_forced": b.TOV_opp / poss,
    }


def build_features(games: pd.DataFrame, box: pd.DataFrame | None, **kw) -> pd.DataFrame:
    """Walk dates in order; emit all of a date's features before any update."""
    fb = FeatureBuilder(**kw)
    games = games[games.clean].sort_values(["date", "game_id"]).reset_index(drop=True)
    box_idx = {}
    if box is not None:
        for r in box.itertuples(index=False):
            box_idx[(r.box_game_id, r.team)] = r
    rows = []
    for date, day in games.groupby("date", sort=True):
        for g in day.itertuples(index=False):
            rows.append(fb.emit(g))
        for g in day.itertuples(index=False):
            bh = ba = None
            if box is not None and not pd.isna(g.box_game_id):
                bh = box_idx.get((g.box_game_id, g.home))
                ba = box_idx.get((g.box_game_id, g.away))
            fb.update(g, _as_series(bh), _as_series(ba))
        fb.last_update_date = date
    feats = pd.DataFrame(rows)
    out = games.merge(feats, on="game_id", how="left")
    _assert_no_leakage(out)
    return out


def _as_series(r):
    if r is None:
        return None
    return pd.Series(r._asdict())


def _assert_no_leakage(df: pd.DataFrame) -> None:
    """Fail loudly if any feature was computed with information from game day or later."""
    asof = pd.to_datetime(df["feature_asof"])
    bad = asof.notna() & (asof >= df["date"])
    if bad.any():
        raise AssertionError(
            f"LEAKAGE: {int(bad.sum())} games have features as-of >= game date, "
            f"e.g. {df.loc[bad, 'game_id'].head(3).tolist()}"
        )
