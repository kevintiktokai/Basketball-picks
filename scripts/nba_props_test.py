"""NBA player points props at real book prices (OddsPapi): is there money in them?

A. Soft books against Pinnacle. A 1xBet / Betway / DraftKings price for a player's points line
   that beats Pinnacle's no-vig price for the same player and line by 2%+, taken at fixed times
   before tip-off, graded on the player's actual points, and valued against Pinnacle's last
   pre-game price (closing-line value, the low-noise check).
B. Our points model against Pinnacle. Does the model (scripts/nba_points_model.py, fitted only on
   earlier seasons, every forecast from earlier games) know anything Pinnacle's line does not?

Player ids: OddsPapi keys props by its own numeric player id. Names for the ids in its live feed
are in data/raw/oddspapi/132/player_names.json; every other id is matched to ESPN box scores by
team (the games the id appears in) and by line (books set the line near the player's expected
points), and the matching is checked on the named ids first.

This is exploration on a few hundred games: any rule it suggests must be tested forward.
usage: python scripts/nba_props_test.py        (after: python -m data.nba_props backfill ... / parse)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

import nba_points_model as nbm
from backtest.analysis import df_to_md
from config_loader import ROOT, log_experiment
from data import nba_props as NP

SEASON_LABEL = nbm.SEASON_LABEL

SOFT = ["1xbet", "betway", "draftkings", "fanduel"]
CHECKS = {"8h before": 8.0, "3h before": 3.0, "1h before": 1.0, "15 min before": 0.25}
EV_MIN = 0.02
MARGINS = [0.5, 1.0, 2.0, 3.0, 5.0]   # candidate gaps (best match's cost below the next best's)
ACCURACY = 0.95              # a season's matched ids are used from the smallest gap checked to be this accurate
NAMES = NP.op.RAW / str(NP.NBA) / "player_names.json"
OUT = ROOT / "reports" / "nba_props_test"
ZFILE = str(ROOT / "data" / "processed" / "nba_props_z{}.npy")      # each season's forecast-error shape


# ---------------------------------------------------------------- ESPN side: box scores and forecasts
def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", "", s.replace("-", " "))
    return " ".join(w for w in s.split() if w not in {"jr", "sr", "ii", "iii", "iv"})


def nickname(team: str) -> str:
    return str(team).split()[-1].lower()


def box_and_forecasts() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every box row of 2025-26 and 2026-27 (DNP rows too, to void props), and a pre-game forecast
    (mu, sd, P(over) shape) for every player-game played, from a model fitted on earlier seasons."""
    nbm.SEASONS = [2022, 2023, 2024, 2025, 2026, 2027]
    nbm.COLS = list(dict.fromkeys(nbm.COLS + ["team_display_name"]))
    b = nbm.load()
    g = nbm.features(b)
    # nba_points_model fits only rows after a player's first game of a season (its prop universe
    # starts at game 6); count games from 1 so season openers, which carry props, are fitted too
    g = g.assign(n_season=g.n_season + 1)
    F = []
    for s in (2026, 2027):
        mu, sd, z = nbm.fit_predict(g[g.season < s], g[g.season == s])
        F.append(g[g.season == s][["game_id", "athlete_id", "date", "points", "pts_ewm"]].assign(mu=mu, sd=sd, season=s,
                                                                                                    zkey=s))
        np.save(ZFILE.format(s), z)
    F = pd.concat(F, ignore_index=True)
    box = b[b.season.isin([2026, 2027])][["game_id", "season", "season_type", "date", "athlete_id",
                                         "athlete_display_name", "team_display_name", "points", "played"]].copy()
    teams = box.groupby("game_id").team_display_name.agg(lambda x: frozenset(nickname(t) for t in x.unique()))
    box["teams"] = box.game_id.map(teams)
    return box, F


def p_over(rows: pd.DataFrame, line) -> np.ndarray:
    out = np.full(len(rows), np.nan)
    for s in rows.zkey.dropna().unique():
        z = np.load(ZFILE.format(int(s)))
        m = (rows.zkey == s).values
        out[m] = nbm.p_over(rows.mu.values[m], rows.sd.values[m], z, np.asarray(line)[m])
    return out


# ---------------------------------------------------------------- odds side
def fixture_games(T: pd.DataFrame, box: pd.DataFrame) -> pd.Series:
    """OddsPapi fixture -> ESPN game id, by US date (start minus 5 h) and the two team nicknames."""
    fx = T.drop_duplicates("fixture_id")[["fixture_id", "start", "home_name", "away_name"]].copy()
    fx["teams"] = [frozenset((nickname(a), nickname(b))) for a, b in zip(fx.home_name, fx.away_name)]
    fx["day"] = (fx.start - pd.Timedelta(hours=5)).dt.tz_localize(None).dt.normalize()
    games = box.drop_duplicates("game_id")[["game_id", "date", "teams"]]
    key = {(d.normalize(), t): gid for gid, d, t in zip(games.game_id, games.date, games.teams)}
    out = {}
    for fid, d, t in zip(fx.fixture_id, fx.day, fx.teams):
        for k in (0, -1, 1):
            gid = key.get((d + pd.Timedelta(days=k), t))
            if gid is not None:
                out[fid] = gid
                break
    return pd.Series(out, name="game_id")


def quotes(T: pd.DataFrame, hours: float) -> pd.DataFrame:
    """Each book's offer at `hours` before the scheduled start: the last snapshot of every
    (player, line, side) at or before that time, kept only if it was live (a pulled line's final
    snapshot is marked inactive). One row per fixture, book, player, line with over/under prices."""
    cut = T.start - pd.Timedelta(hours=hours)
    Q = T[T.t <= cut].sort_values("t").groupby(["fixture_id", "book", "player_id", "line", "side"]).tail(1)
    Q = Q[Q.active & (Q.price > 1)]
    W = Q.pivot_table(index=["fixture_id", "book", "player_id", "line"], columns="side", values="price").reset_index()
    for c in ("over", "under"):
        if c not in W:
            W[c] = np.nan
    return W


def pinnacle_fair(W: pd.DataFrame) -> pd.DataFrame:
    P = W[(W.book == "pinnacle") & W.over.notna() & W.under.notna()].copy()
    io, iu = 1 / P.over, 1 / P.under
    P["p_fair"] = io / (io + iu)                                    # proportional no-vig
    P["margin"] = io + iu - 1
    return P[["fixture_id", "player_id", "line", "p_fair", "margin", "over", "under"]].rename(
        columns={"over": "pin_over", "under": "pin_under"})


def main_lines(T: pd.DataFrame) -> pd.DataFrame:
    """Per fixture and player: the median over books of each book's last pre-game main line (the
    line priced nearest even money), used to match ids to players."""
    W = quotes(T, 0.0).dropna(subset=["over", "under"])
    W["skew"] = np.abs(np.log(W.over / W.under))
    M = W.sort_values("skew").groupby(["fixture_id", "book", "player_id"]).head(1)
    return M.groupby(["fixture_id", "player_id"]).line.median().rename("main_line").reset_index()


# ---------------------------------------------------------------- player ids
def map_players(T: pd.DataFrame, box: pd.DataFrame, F: pd.DataFrame, fg: pd.Series):
    """OddsPapi player id -> ESPN athlete, per season. Named ids by name; the rest by an assignment
    that rewards appearing in the id's games and a forecast near the id's lines. Returns the map, a
    validation table (named ids hidden a fifth at a time and matched like the rest), and per season
    the smallest best-vs-next gap at which the validation was ACCURACY right."""
    names = {k: norm(" ".join(reversed([p.strip() for p in v.split(",", 1)]))) for k, v in
             json.loads(NAMES.read_text()).items()}
    L = main_lines(T)
    L["game_id"] = L.fixture_id.map(fg)
    L = L.dropna(subset=["game_id"]).astype({"game_id": int})
    seasons = box.drop_duplicates("game_id").set_index("game_id").season
    L["season"] = L.game_id.map(seasons)
    roster = box.groupby("game_id").athlete_id.agg(set)
    mu = dict(zip(zip(F.game_id, F.athlete_id), F.mu))
    athletes = box.drop_duplicates("athlete_id").set_index("athlete_id").athlete_display_name
    by_name = {}
    for a, n in athletes.items():
        by_name.setdefault(norm(n), []).append(a)

    def cost_matrix(sub: pd.DataFrame, pids: list, cands: list) -> np.ndarray:
        C = np.full((len(pids), len(cands)), 1e6)
        ci = {a: j for j, a in enumerate(cands)}
        grp = {pid: x for pid, x in sub.groupby("player_id")}
        for i, pid in enumerate(pids):
            x = grp[pid]
            n = len(x)
            app, dist = {}, {}
            for gid, line in zip(x.game_id, x.main_line):
                for a in roster.get(gid, ()):
                    if a not in ci:
                        continue
                    app[a] = app.get(a, 0) + 1
                    m = mu.get((gid, a))
                    if m is not None and np.isfinite(m):
                        dist.setdefault(a, []).append(abs(line - m))
            for a, k in app.items():
                if k / n >= 0.5:
                    d = np.median(dist[a]) if a in dist else 8.0
                    C[i, ci[a]] = d + 20 * (1 - k / n)
        return C

    def assign(sub: pd.DataFrame, pids: list, cands: list) -> pd.DataFrame:
        if not pids or not cands:
            return pd.DataFrame(columns=["player_id", "athlete_id", "cost", "margin"])
        C = cost_matrix(sub, pids, cands)
        r, c = linear_sum_assignment(C)
        rows = []
        for i, j in zip(r, c):
            if C[i, j] >= 1e6:
                continue
            alt = np.sort(np.delete(C[i], j))
            rows.append({"player_id": pids[i], "athlete_id": cands[j], "cost": C[i, j],
                         "margin": (alt[0] if len(alt) else 1e6) - C[i, j]})
        return pd.DataFrame(rows)

    def appears(pid_games: pd.Series, a) -> bool:
        return np.mean([a in roster.get(g, ()) for g in pid_games]) >= 0.5

    maps, checks, prev, use = [], [], {}, {}
    # this season first: its teams have met different opponents, so an id's team is clear; last
    # season's props are mostly playoff series (the same two teams every game) and borrow from it
    for s, sub in sorted(L.groupby("season"), key=lambda x: -x[0]):
        games = set(sub.game_id)
        pool = sorted({a for gid in games for a in roster.get(gid, ())})
        pid_games = sub.groupby("player_id").game_id.agg(list)
        fixed = {}
        for pid in pid_games.index:
            if pid in names:
                hits = [a for a in by_name.get(names[pid], []) if a in pool]
                if len(hits) == 1:
                    fixed[pid] = (hits[0], "name")
            elif pid in prev and appears(pid_games[pid], prev[pid]):  # same id, same player next season
                fixed[pid] = (prev[pid], "carried")
        named = [p for p, (_, how) in fixed.items() if how == "name"]
        # validation: hide a fifth of the named ids at a time, keep the rest fixed, match the hidden
        rng = np.random.default_rng(0)
        fold = dict(zip(named, rng.permutation(len(named)) % 5))
        Vs = []
        for k in range(5):
            hide = {p for p in named if fold[p] == k}
            keep = {p: a for p, (a, _) in fixed.items() if p not in hide}
            V = assign(sub, sorted(set(pid_games.index) - set(keep)), sorted(set(pool) - set(keep.values())))
            V = V[V.player_id.isin(hide)]
            V["correct"] = V.athlete_id == V.player_id.map(lambda p: fixed[p][0])
            Vs.append(V.assign(season=s))
        V = pd.concat(Vs, ignore_index=True)
        checks.append(V)
        ok = [m for m in MARGINS if (V.margin >= m).sum() >= 10 and V.correct[V.margin >= m].mean() >= ACCURACY]
        use[s] = ok[0] if ok else np.inf
        # the map: named and carried ids fixed, the rest assigned among the athletes left
        rest = sorted(set(pid_games.index) - set(fixed))
        A = assign(sub, rest, sorted(set(pool) - {a for a, _ in fixed.values()}))
        Mx = pd.concat([pd.DataFrame({"player_id": list(fixed), "athlete_id": [a for a, _ in fixed.values()],
                                      "cost": 0.0, "margin": np.inf, "how": [h for _, h in fixed.values()]}),
                        A.assign(how="matched")]).assign(season=s)
        maps.append(Mx)
        prev.update({p: a for p, a, m in zip(Mx.player_id, Mx.athlete_id, Mx.margin) if m >= use[s]})
    return pd.concat(maps, ignore_index=True), pd.concat(checks, ignore_index=True), use


# ---------------------------------------------------------------- grading helpers
def grade(D: pd.DataFrame) -> pd.DataFrame:
    """won / lost / push / void (player did not play) and profit per 1 staked."""
    pts = D.points
    win = np.where(D.side == "over", pts > D.line, pts < D.line)
    D["result"] = np.where(~D.played.fillna(False).astype(bool), "void",
                           np.where(pts == D.line, "push", np.where(win, "won", "lost")))
    D["pnl"] = np.where(D.result == "won", D.price - 1, np.where(D.result == "lost", -1.0, 0.0))
    return D


def summary(D: pd.DataFrame, by: list) -> pd.DataFrame:
    def f(x):
        g = x[x.result.isin(["won", "lost", "push"])]
        n = len(g)
        c = x.clv.dropna()
        return pd.Series({"bets": n, "won %": (g.result == "won").mean() if n else np.nan,
                          "avg odds": g.price.mean() if n else np.nan,
                          "value at bet time": x.ev.mean(), "value vs close": c.mean() if len(c) else np.nan,
                          "close found": len(c) / max(len(x), 1),
                          "ROI": g.pnl.mean() if n else np.nan,
                          "ROI ± (1 se)": g.pnl.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan})
    return D.groupby(by).apply(f).reset_index()


def window(start: pd.Series) -> pd.Series:
    d = start.dt.tz_localize(None)
    return np.where(d >= "2026-10-01", "2026-27 so far",
                    np.where(d >= "2026-04-18", "2026 playoffs", "2025-26 Mar-Apr"))


# ---------------------------------------------------------------- the tests
def main():
    T = NP.parse()
    T = T[T.start.notna()]
    print(f"{len(T):,} prices, {T.fixture_id.nunique()} games, {T.player_id.nunique()} player ids")
    box, F = box_and_forecasts()
    fg = fixture_games(T, box)
    print(f"games matched to ESPN: {len(fg)} of {T.fixture_id.nunique()}")
    M, V, use = map_players(T, box, F, fg)
    val = pd.DataFrame([{"season": SEASON_LABEL[s], "gap at least": m, "ids": int((x.margin >= m).sum()),
                         "correct": x.correct[x.margin >= m].mean()}
                        for s, x in V.groupby("season") for m in [0.0] + MARGINS])
    print(val.to_string(), use)
    M = M[M.margin >= M.season.map(use)]
    how = M.groupby(["season", "how"]).size().unstack(fill_value=0).reset_index()
    how["season"] = how.season.map(SEASON_LABEL)
    pmap = {(s, p): a for s, p, a in zip(M.season, M.player_id, M.athlete_id)}

    seasons = box.drop_duplicates("game_id").set_index("game_id").season
    res = box.set_index(["game_id", "athlete_id"])[["points", "played"]]
    fcast = F.set_index(["game_id", "athlete_id"])[["mu", "sd", "zkey"]]

    def attach(D: pd.DataFrame) -> pd.DataFrame:
        D = D.copy()
        D["game_id"] = D.fixture_id.map(fg)
        D = D.dropna(subset=["game_id"]).astype({"game_id": int})
        D["season"] = D.game_id.map(seasons)
        D["athlete_id"] = [pmap.get((s, p)) for s, p in zip(D.season, D.player_id)]
        D = D.dropna(subset=["athlete_id"])
        idx = pd.MultiIndex.from_arrays([D.game_id, D.athlete_id])
        D[["points", "played"]] = res.reindex(idx).values
        D[["mu", "sd", "zkey"]] = fcast.reindex(idx).values
        return D

    starts = T.drop_duplicates("fixture_id").set_index("fixture_id").start
    close = pinnacle_fair(quotes(T, 1 / 60))[["fixture_id", "player_id", "line", "p_fair"]].rename(
        columns={"p_fair": "p_close"})

    # ---- Pinnacle's honesty at the close (the yardstick for everything else)
    PC = attach(close)
    PC = PC[PC.played.fillna(False).astype(bool) & (PC.points != PC.line)]
    PC["over"] = (PC.points > PC.line).astype(float)
    PC["bin"] = pd.cut(PC.p_close, [0, .4, .45, .5, .55, .6, 1])
    pin_cal = PC.groupby("bin").agg(lines=("over", "size"), predicted=("p_close", "mean"),
                                    happened=("over", "mean")).reset_index()
    pin_cal["bin"] = pin_cal["bin"].astype(str)

    # ---- A: soft books against Pinnacle's fair price, same player and line
    bets = []
    for label, h in CHECKS.items():
        W = quotes(T, h)
        P = pinnacle_fair(W)
        S = W[W.book.isin(SOFT)].merge(P[["fixture_id", "player_id", "line", "p_fair"]],
                                       on=["fixture_id", "player_id", "line"])
        for side, pf in (("over", S.p_fair), ("under", 1 - S.p_fair)):
            x = S.assign(side=side, price=S[side], p=pf, ev=S[side] * pf - 1).dropna(subset=["price"])
            bets.append(x[x.ev >= EV_MIN].assign(check=label))
    A = pd.concat(bets, ignore_index=True)
    A = A.sort_values("ev").groupby(["check", "fixture_id", "book", "player_id"]).tail(1)    # one bet per player
    A = A.merge(close, on=["fixture_id", "player_id", "line"], how="left")
    A["clv"] = A.price * np.where(A.side == "over", A.p_close, 1 - A.p_close) - 1
    # value against the close needs no player match: it is measured on every bet
    clv_all = A.groupby(["check", "book"]).agg(**{"all bets": ("ev", "size"),
                                                  "value vs close, all bets": ("clv", "mean")}).reset_index()
    A = grade(attach(A))
    A["window"] = window(A.fixture_id.map(starts))
    A_book = summary(A, ["check", "book"]).merge(clv_all, on=["check", "book"], how="right")
    A_win = summary(A[A.check == "1h before"], ["window", "book"])
    A["ev band"] = pd.cut(A.ev, [0.02, 0.04, 0.07, 0.12, 9], labels=["2-4%", "4-7%", "7-12%", "12%+"])
    A_band = summary(A[A.check == "1h before"], ["ev band"])
    # how many prices were on offer at all (the denominator)
    offered = {label: int(len(quotes(T, h).query("book in @SOFT"))) for label, h in CHECKS.items()}

    # ---- how each book prices against Pinnacle, 1 hour before (every quote, both sides)
    W1 = quotes(T, 1.0)
    S1 = W1[W1.book.isin(SOFT)].merge(pinnacle_fair(W1)[["fixture_id", "player_id", "line", "p_fair"]],
                                      on=["fixture_id", "player_id", "line"])
    v = pd.concat([S1.assign(v=S1.over * S1.p_fair - 1), S1.assign(v=S1.under * (1 - S1.p_fair) - 1)]).dropna(subset=["v"])
    book_tab = v.groupby("book").agg(**{"prices on Pinnacle's line": ("v", "size"), "average value": ("v", "mean"),
                                        "share above fair": ("v", lambda x: (x > 0).mean()),
                                        "share 2%+ above": ("v", lambda x: (x >= EV_MIN).mean())}).reset_index()

    # ---- the side Pinnacle's own price favours, bet at Pinnacle's price 1 hour before (a pattern
    # seen in the closing-price table above; looked for after the fact, so only a check)
    PF = attach(pinnacle_fair(W1))
    PF = PF[PF.played.fillna(False).astype(bool) & (PF.points != PF.line) & ((PF.p_fair - 0.5).abs() > 0.005)]
    fav = PF.p_fair > 0.5
    PF = PF.assign(side=np.where(fav, "over", "under"), price=np.where(fav, PF.pin_over, PF.pin_under), ev=np.nan,
                   clv=np.nan)
    PF = grade(PF)
    PF["window"] = window(PF.fixture_id.map(starts))
    fav_tab = summary(PF, ["window"])[["window", "bets", "won %", "avg odds", "ROI", "ROI ± (1 se)"]]

    # ---- B: our model against Pinnacle, at Pinnacle's own price, 1 hour before
    W = quotes(T, 1.0)
    P = attach(pinnacle_fair(W))
    P = P[P.mu.notna() & P.played.fillna(False).astype(bool)].copy()
    P["p_model"] = p_over(P, P.line.values)
    P = P[np.isfinite(P.p_model)]
    P["over"] = np.where(P.points == P.line, np.nan, (P.points > P.line).astype(float))
    Pm = P.dropna(subset=["over"])
    eps = 1e-3
    lg = lambda p: np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))   # noqa: E731
    brier = {"Pinnacle no-vig": float(np.mean((Pm.p_fair - Pm.over) ** 2)),
             "our model": float(np.mean((Pm.p_model - Pm.over) ** 2)),
             "half and half": float(np.mean((0.5 * Pm.p_fair + 0.5 * Pm.p_model - Pm.over) ** 2)),
             "always 50%": float(np.mean((0.5 - Pm.over) ** 2))}
    import statsmodels.api as sm
    X = sm.add_constant(np.column_stack([lg(Pm.p_fair), lg(Pm.p_model) - lg(Pm.p_fair)]))
    fit = sm.Logit(Pm.over.values, X).fit(disp=0)
    reg = {"Pinnacle weight": float(fit.params[1]), "model-minus-Pinnacle weight": float(fit.params[2]),
           "its standard error": float(fit.bse[2]), "lines": int(len(Pm))}
    B_rows = []
    for thr in (0.0, 0.03, 0.06, 0.10):
        for side in ("over", "under"):
            pm = P.p_model if side == "over" else 1 - P.p_model
            price = P.pin_over if side == "over" else P.pin_under
            x = P[(pm * price - 1) >= thr].assign(side=side, price=price, ev=pm * price - 1)
            B_rows.append(x.assign(thr=thr))
    B = pd.concat(B_rows, ignore_index=True)
    B = B.sort_values("ev").groupby(["thr", "fixture_id", "player_id", "line"]).tail(1)
    B = B.drop(columns=["p_close"], errors="ignore").merge(close, on=["fixture_id", "player_id", "line"], how="left")
    B["clv"] = B.price * np.where(B.side == "over", B.p_close, 1 - B.p_close) - 1
    B = grade(B)
    B["window"] = window(B.fixture_id.map(starts))
    B_thr = summary(B, ["thr"])
    B_win = summary(B[B.thr == 0.03], ["window"])

    # ---- C: soft-book value (A, 1 hour before) where the model agrees vs disagrees
    C = A[(A.check == "1h before") & A.mu.notna()].copy()
    C["p_model_side"] = p_over(C, C.line.values)
    C["p_model_side"] = np.where(C.side == "over", C.p_model_side, 1 - C.p_model_side)
    C["model"] = np.where(C.p_model_side > C.p, "agrees", "disagrees")
    C_tab = summary(C, ["model"])

    # ---- report
    cover = T.groupby("book").agg(games=("fixture_id", "nunique"), players=("player_id", "nunique"),
                                  prices=("price", "size")).reset_index()
    win_games = pd.Series(window(starts)).value_counts().rename_axis("window").reset_index(name="games")
    out = {"coverage": cover.to_dict("records"), "validation": val.to_dict("records"),
           "gap_used": {SEASON_LABEL[k]: v for k, v in use.items()}, "ids_used": how.to_dict("records"),
           "pinnacle_calibration": pin_cal.to_dict("records"), "A_by_book": A_book.to_dict("records"),
           "A_by_window": A_win.to_dict("records"), "A_by_value": A_band.to_dict("records"),
           "offered": offered, "B_brier": brier, "B_regression": reg, "B_by_threshold": B_thr.to_dict("records"),
           "B_by_window": B_win.to_dict("records"), "C": C_tab.to_dict("records"),
           "books_vs_pinnacle": book_tab.to_dict("records"), "pinnacle_favoured": fav_tab.to_dict("records")}
    OUT.with_suffix(".json").write_text(json.dumps(out, indent=1, default=str))
    A.to_csv(OUT.with_name("nba_props_test_bets_A.csv"), index=False)
    fmt = "{:.3f}"
    a1 = A[(A.check == "1h before") & (A.book == "1xbet")]
    a1g = a1[a1.result.isin(["won", "lost", "push"])]
    clv1 = clv_all[(clv_all.check == "1h before") & (clv_all.book == "1xbet")]
    n_x = T[T.book == "1xbet"].fixture_id.nunique()
    b3 = B_thr[B_thr.thr == 0.03].iloc[0]
    informative = abs(reg["model-minus-Pinnacle weight"]) > 2 * reg["its standard error"]
    verdict = [
        "## Summary\n",
        f"* **1xBet against Pinnacle (the line-shopping test).** 1 hour before tip-off, "
        f"{int(clv1['all bets'].sum()) if len(clv1) else 0} 1xBet prices in {n_x} games beat Pinnacle's fair price by 2%+ "
        f"(about {(clv1['all bets'].sum() if len(clv1) else 0) / max(n_x, 1):.1f} a game). Against Pinnacle's last price "
        f"they averaged {clv1['value vs close, all bets'].mean():+.1%}, the sign of a real edge, but on far too few bets "
        f"to be sure; results so far: {int((a1g.result == 'won').sum())} won, {int((a1g.result == 'lost').sum())} lost "
        f"(ROI {a1g.pnl.mean():+.0%}, give or take {a1g.pnl.std(ddof=1) / np.sqrt(max(len(a1g), 1)):.0%}).",
        f"* **Our points model against Pinnacle.** On {reg['lines']:,} lines the model "
        + ("adds information beyond Pinnacle's price" if informative else "adds nothing beyond Pinnacle's price")
        + f" (weight {reg['model-minus-Pinnacle weight']:+.2f} ± {reg['its standard error']:.2f}); betting its "
        f"side at 3%+ model value returned {b3['ROI']:+.1%} ± {b3['ROI ± (1 se)']:.1%} on {int(b3['bets'])} bets, "
        f"and those prices were {b3['value vs close']:+.1%} against Pinnacle's close. "
        "Its probabilities sit too far from the market: what it calls value is mostly its own error.",
        "* Betway: the feed carries its points prices only until about 4-15 hours before tip-off, mostly "
        "before Pinnacle posts, so it could not be tested (the few prices on Pinnacle's line were about 6% "
        "below fair). DraftKings shows small value late but loses it on early prices, which Pinnacle moves "
        "away from; it is in the test only as a check (not a book we bet).", ""]
    lines = [
        "# NBA player points props at real prices\n",
        f"Data: OddsPapi pre-game price histories for {T.fixture_id.nunique()} NBA games "
        f"({', '.join(f'{r.window}: {r.games}' for r in win_games.itertuples())}), graded on ESPN box scores. "
        "A void (player did not play) is not counted.\n",
        *verdict,
        "Prices by book:\n", df_to_md(cover, "{:,.0f}"), "",
        "## Matching OddsPapi player ids to players\n",
        "Ids with a name in OddsPapi's live feed are matched by name; an id matched this season keeps its "
        "player last season if he is in that season's games. The rest are matched by team and line. To check that, "
        "named ids were hidden a fifth at a time and matched like the rest. 'Gap' is how much better the "
        "best match fits than the next best; a season's matches are used from the smallest gap at which "
        f"the check was {ACCURACY:.0%}+ right ({', '.join(f'{SEASON_LABEL[s]}: {v:g}' for s, v in use.items())}).\n",
        df_to_md(val, fmt), "", "Ids used, by how they were matched:\n", df_to_md(how, "{:,.0f}"), "",
        "## Is Pinnacle's closing price honest?\n",
        "Pinnacle's no-vig chance of the over at its last pre-game price, against what happened:\n",
        df_to_md(pin_cal, fmt), "",
        "## Test A: soft-book prices that beat Pinnacle's fair price by 2%+\n",
        "Same player, same line; one bet per player, book and time; 1 unit each. 'Value vs close' is the "
        "price against Pinnacle's last pre-game fair price for the same line (blank when Pinnacle no longer "
        "had that line). Results count only the bets whose player id is matched; 'all bets' and its value "
        "against the close need no match.\n",
        df_to_md(A_book, fmt), "",
        "How each book prices against Pinnacle 1 hour before tip-off (every price on the same line as "
        "Pinnacle's, both sides; 'value' = price × Pinnacle's fair chance − 1):\n", df_to_md(book_tab, fmt), "",
        "1 hour before tip-off, by period:\n", df_to_md(A_win, fmt), "",
        "1 hour before tip-off, by how much value the price showed:\n", df_to_md(A_band, fmt), "",
        "Checked and rejected: in the closing-price table Pinnacle's favoured side seems to come in more "
        "often than its price says. Bet at Pinnacle's own price 1 hour before tip-off it does not hold "
        "up period to period (and it was spotted after looking at results):\n", df_to_md(fav_tab, fmt), "",
        "## Test B: our points model against Pinnacle\n",
        f"Accuracy on {len(Pm):,} Pinnacle lines 1 hour before tip-off (Brier score, lower is better):\n",
        df_to_md(pd.DataFrame([brier]), "{:.4f}"), "",
        f"Does the model add anything to Pinnacle's price? In a logistic regression of the result on "
        f"Pinnacle's no-vig log-odds and the model's difference from it, the difference gets weight "
        f"{reg['model-minus-Pinnacle weight']:+.2f} (standard error {reg['its standard error']:.2f}); "
        "zero means no information beyond Pinnacle.\n",
        "Betting the model's side at Pinnacle's own price when the model sees value of at least the threshold:\n",
        df_to_md(B_thr, fmt), "", "At a 3% threshold, by period:\n", df_to_md(B_win, fmt), "",
        "## Test A and the model together\n",
        "Soft-book value bets 1 hour before, split by whether the model agrees with the side:\n",
        df_to_md(C_tab, fmt), ""]
    (OUT.with_suffix(".md")).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    log_experiment("nba_props_test", {"checks": CHECKS, "ev_min": EV_MIN, "soft": SOFT},
                   {k: out[k] for k in ("B_brier", "B_regression", "offered")})


if __name__ == "__main__":
    main()
