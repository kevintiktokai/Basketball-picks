"""Date-by-date opponent-adjusted team ratings (Massey/KenPom-style ridge fits).

For every game date D, ratings are fitted on games with date < D only:
  * points model     : pts_team = mu + off_t + def_opp + h * venue
  * efficiency model : 100*pts/poss = mu_e + oe_t + de_opp + h_e * venue   (box games)
  * tempo model      : poss = tau + tp_home + tp_away                       (box games)
Weights decay with game age (half-life in days); the previous season's games
enter with a reduced weight, which acts as a shrinking pre-season prior that
current-season games quickly override. A ridge penalty shrinks every team
toward league average (strongest when a team has few games).

Each emitted rating row carries `asof` = last game date used, < D.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


def _season_index(seasons: pd.Series) -> pd.Series:
    order = {s: i for i, s in enumerate(sorted(seasons.unique()))}
    return seasons.map(order)


class DailyRatings:
    def __init__(self, half_life_days: float = 45.0, prev_season_weight: float = 0.35,
                 ridge: float = 3.0, lookback_days: int = 400):
        self.hl = half_life_days
        self.prev_w = prev_season_weight
        self.lam = ridge
        self.lookback = lookback_days

    def run(self, games: pd.DataFrame) -> pd.DataFrame:
        """games: date, season, home, away, neutral, home_pts, away_pts, poss (nan ok), game_key.
        Returns one row per game with pre-game ratings for both teams."""
        g = games.sort_values("date").reset_index(drop=True).copy()
        teams = pd.Index(sorted(set(g.home) | set(g.away)))
        nt = len(teams)
        g["hi"] = teams.get_indexer(g.home)
        g["ai"] = teams.get_indexer(g.away)
        g["si"] = _season_index(g.season)
        venue = np.where(g.neutral.values, 0.0, 1.0)

        dates = np.sort(g.date.unique())
        out = []
        date_arr = g.date.values
        for D in dates:
            today = g.index[date_arr == D]
            past = (date_arr < D) & (date_arr >= D - np.timedelta64(self.lookback, "D"))
            P = g[past]
            cur_season = g.si.values[today[0]]
            if len(P) < 30:
                for i in today:
                    out.append(self._empty_row(g, i))
                continue
            age = (D - P.date.values) / np.timedelta64(1, "D")
            # current season: recency-decayed; previous season(s): constant reduced
            # weight = a pre-season prior that current games override quickly
            w = np.where(P.si.values == cur_season, 0.5 ** (age / self.hl), self.prev_w)
            # points system: two rows per game
            pts_fit = self._fit_points(P, w, nt, venue[P.index])
            eff_fit = self._fit_eff(P, w, nt, venue[P.index])
            n_cur = self._games_played(P[P.si == cur_season], nt)
            asof = P.date.max()
            for i in today:
                h, a = g.hi.values[i], g.ai.values[i]
                v = venue[i]
                row = {"game_key": g.game_key.values[i], "rt_asof": asof,
                       "rt_n_home": n_cur[h], "rt_n_away": n_cur[a]}
                mu, off, dfn, hh, ha = pts_fit
                row["rt_pts_home"] = mu + off[h] + dfn[a] + hh * v
                row["rt_pts_away"] = mu + off[a] + dfn[h] + ha * v
                row["rt_off_home"], row["rt_def_home"] = off[h], dfn[h]
                row["rt_off_away"], row["rt_def_away"] = off[a], dfn[a]
                if eff_fit is not None:
                    mue, oe, de, he, tau, tp, ht = eff_fit
                    poss = tau + tp[h] + tp[a]
                    oe_h = mue + oe[h] + de[a] + he * v
                    oe_a = mue + oe[a] + de[h] - he * v
                    row.update({"rt_poss": poss, "rt_oe_home": oe_h, "rt_oe_away": oe_a,
                                "rt_tempo_home": tp[h], "rt_tempo_away": tp[a],
                                "rt_eff_total": poss * (oe_h + oe_a) / 100.0})
                out.append(row)
        return pd.DataFrame(out)

    # -------------------------------------------------------------- fits
    def _empty_row(self, g, i):
        return {"game_key": g.game_key.values[i], "rt_asof": pd.NaT}

    @staticmethod
    def _games_played(P, nt):
        c = np.zeros(nt)
        np.add.at(c, P.hi.values, 1)
        np.add.at(c, P.ai.values, 1)
        return c

    def _solve(self, rows, cols, vals, y, w, ncol, n_team_cols):
        A = sparse.csr_matrix((vals, (rows, cols)), shape=(len(y), ncol))
        Wa = A.multiply(w[:, None])
        AtA = (A.T @ Wa).toarray()
        Aty = Wa.T @ y
        reg = np.zeros(ncol)
        reg[:n_team_cols] = self.lam
        return np.linalg.solve(AtA + np.diag(reg) + 1e-9 * np.eye(ncol), Aty)

    def _fit_points(self, P, w, nt, venue):
        n = len(P)
        hi, ai = P.hi.values, P.ai.values
        # columns: off[0:nt], def[nt:2nt], mu, home_bonus_home, home_bonus_away
        r = np.arange(2 * n)
        rows = np.concatenate([r, r, r, r])
        cols = np.concatenate([
            np.concatenate([hi, ai]),                 # offence of scoring team
            nt + np.concatenate([ai, hi]),            # defence of conceding team
            np.full(2 * n, 2 * nt),                   # mu
            np.concatenate([np.full(n, 2 * nt + 1), np.full(n, 2 * nt + 2)]),
        ])
        vals = np.concatenate([np.ones(2 * n), np.ones(2 * n), np.ones(2 * n),
                               np.concatenate([venue, venue])])
        y = np.concatenate([P.home_pts.values, P.away_pts.values]).astype(float)
        ww = np.concatenate([w, w])
        b = self._solve(rows, cols, vals, y, ww, 2 * nt + 3, 2 * nt)
        return b[2 * nt], b[:nt], b[nt:2 * nt], b[2 * nt + 1], b[2 * nt + 2]

    def _fit_eff(self, P, w, nt, venue):
        m = P.poss.notna().values
        if m.sum() < 30:
            return None
        Q = P[m]
        wq = w[m]
        vq = venue[m]
        n = len(Q)
        hi, ai = Q.hi.values, Q.ai.values
        poss = Q.poss.values.astype(float)
        r = np.arange(2 * n)
        # efficiency: oe[0:nt], de[nt:2nt], mu_e, h_e
        rows = np.concatenate([r, r, r, r])
        cols = np.concatenate([np.concatenate([hi, ai]), nt + np.concatenate([ai, hi]),
                               np.full(2 * n, 2 * nt), np.full(2 * n, 2 * nt + 1)])
        vals = np.concatenate([np.ones(4 * n), np.ones(2 * n),
                               np.concatenate([vq, -vq])])
        y = 100.0 * np.concatenate([Q.home_pts.values, Q.away_pts.values]) / np.concatenate([poss, poss])
        b = self._solve(rows, cols, vals, y, np.concatenate([wq, wq]), 2 * nt + 2, 2 * nt)
        mue, oe, de, he = b[2 * nt], b[:nt], b[nt:2 * nt], b[2 * nt + 1]
        # tempo: tp[0:nt], tau, venue
        r1 = np.arange(n)
        rows = np.concatenate([r1, r1, r1, r1])
        cols = np.concatenate([hi, ai, np.full(n, nt), np.full(n, nt + 1)])
        vals = np.concatenate([np.ones(3 * n), vq])
        bt = self._solve(rows, cols, vals, poss, wq, nt + 2, nt)
        return mue, oe, de, he, bt[nt], bt[:nt], bt[nt + 1]
