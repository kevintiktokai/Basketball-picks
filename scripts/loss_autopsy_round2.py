"""Loss autopsy, round 2: a second batch of pre-game ideas for the NCAAB straight bets, plus checks
of the round-1 lead (high-altitude venues). Same data and rule as scripts/loss_autopsy.py: the miss
against the locked v3 engine's forecast (total - opener - mu) on every eligible game, and the bets'
own margin; a lead needs |t| >= 2 in discovery (2011-12..2017-18) and the same sign with |t| >= 1.5
in validation (2018-19..2020-21). 2021-26 is not read.

Ideas and the direction expected, written down before this script was first run:
  venue factor        a home floor's earlier games (last 3 seasons + this one) ran over or under the
                      closing total: shrunk mean of (total - close), k = 40 games; expected +
  venue split         the same minus the home team's own road games over the same window; expected +
  key player out      a player averaging 25+ minutes over his team's previous 5 games does not play
                      (injury, illness, suspension; nearly always known before tip-off, though here
                      read from the box score); expected - (a ratings engine cannot see who is out,
                      so it argues with an opener that already knows)
  key player back     a player averaging 25+ minutes this season who missed his team's previous game
                      plays again; expected + (ratings built while he was out are too low)
  long layoff         both teams had 7+ days off (exam break, holidays; season openers excluded); expected -
  played yesterday    either team played the day before (tournaments); expected -
  football stadium    venue capacity 30,000+ (domes: Final Four and some regionals, Syracuse); expected -
  senior night        the home team's last home game of the regular season; no direction expected
Separate check (execution, not a forecast): does the closing total overshoot after big moves? If the
close over-reacts, (total - close) runs against the move and a hedge at the close (a "middle") gains;
lead if the slope of (total - close) on (close - open) has t <= -2 in discovery and <= -1.5 in validation.
Altitude checks (directions written before they were run): a physical cause should hit visitors from
low altitude harder than visitors who live at altitude; teams based at altitude should run under the
forecast on the road (their ratings carry home altitude); fatigue would show mostly after half-time.
Writes reports/loss_autopsy_round2.md.
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

import loss_autopsy as LA
from backtest.analysis import df_to_md
from backtest.wf2 import main_line_probs
from config_loader import ROOT, log_experiment
from diagnose_bets import load

LAST = "2020-21"
K_VENUE, VENUE_SEASONS = 40, 3
KEY_MIN, PREV_GAMES = 25.0, 5


def season_of(d: pd.Series) -> pd.Series:
    y = d.dt.year - (d.dt.month < 8)
    return y.astype(str) + "-" + ((y + 1) % 100).astype(str).str.zfill(2)


def venue_features(G: pd.DataFrame) -> pd.DataFrame:
    """Point-in-time venue factor of each game's home floor, from games before its date only."""
    U = pd.read_parquet(ROOT / "data" / "processed" / "ncaab_games_unified.parquet",
                        columns=["season", "date", "home", "away", "neutral", "total", "line_close", "ok_close", "clean"])
    U = U[(U.season <= LAST) & ~U.neutral & U.ok_close & U.clean & U.line_close.notna() & U.total.notna()].copy()
    U["e"] = U.total - U.line_close
    seasons = sorted(U.season.unique())
    start = U.groupby("season").date.min()
    win_start = {s: start[seasons[max(0, i - VENUE_SEASONS)]] for i, s in enumerate(seasons)}
    hist = {}
    for side in ("home", "away"):
        hist[side] = {t: (g.date.values, np.concatenate([[0.0], np.cumsum(g.e.values)]))
                      for t, g in U.sort_values("date").groupby(side)}
    out = np.full((len(G), 2), np.nan)
    for i, (t, d, s, neu) in enumerate(zip(G.home.values, G.date.values, G.season.values, G.neutral_i.values)):
        if neu:
            continue
        ws = np.datetime64(win_start[s]) if s in win_start else None
        vals = []
        for side in ("home", "away"):
            h = hist[side].get(t)
            if h is None or ws is None:
                vals.append((0.0, 0))
                continue
            a, b = np.searchsorted(h[0], ws, "left"), np.searchsorted(h[0], d, "left")
            vals.append((h[1][b] - h[1][a], b - a))
        (sh, nh), (sr, nr) = vals
        out[i, 0] = sh / (nh + K_VENUE)
        out[i, 1] = sh / (nh + K_VENUE) - sr / (nr + K_VENUE)
    return pd.DataFrame(out, columns=["venue_factor", "venue_split"], index=G.index)


def availability(G: pd.DataFrame) -> pd.DataFrame:
    """Key players out / back for both teams, from ESPN player box scores (2011-21 only)."""
    from data.ncaab_players import load as load_players
    pb = load_players(range(2011, 2022))
    pb = pb[pb.athlete_id.notna()].copy()
    pb["team_id"] = pd.to_numeric(pb.team_id, errors="coerce").astype("Int64")
    pb["m"] = np.where(pb.did_not_play.fillna(False).astype(bool), 0.0, pb.minutes.fillna(0.0))
    pb = pb.drop_duplicates(["game_id", "team_id", "athlete_id"])
    rows = []
    for (team, season), g in pb.groupby(["team_id", "season"]):
        order = g.groupby("game_id").agg(date=("game_date", "first"), tot=("m", "sum"))
        order = order[order.tot > 0].sort_values("date")             # team-games that have a box score
        gids = order.index.values
        W = g.pivot(index="game_id", columns="athlete_id", values="m").reindex(gids).fillna(0.0).values
        for j in range(len(gids)):
            out_m, back_m = np.nan, np.nan
            if j >= 3:
                prev = W[max(0, j - PREV_GAMES):j].mean(axis=0)
                out_m = float(prev[(prev >= KEY_MIN) & (W[j] == 0)].sum() / 200)
            if j >= 2:
                avg = W[:j].mean(axis=0)
                back = (avg >= KEY_MIN) & (W[j - 1] == 0) & (W[j] > 0)
                back_m = float(avg[back].sum() / 200)
            rows.append((gids[j], int(team), out_m, back_m))
    A = pd.DataFrame(rows, columns=["game_id", "team_id", "out_share", "back_share"])
    A = A.set_index(["game_id", "team_id"])
    res = {}
    for side in ("home", "away"):
        idx = pd.MultiIndex.from_arrays([G.espn_game_id.fillna(-1).astype("int64"),
                                         pd.to_numeric(G[side].str[1:], errors="coerce").fillna(-1).astype("int64")])
        res[side] = A.reindex(idx)
    X = pd.DataFrame(index=G.index)
    X["out_share"] = res["home"].out_share.values + res["away"].out_share.values
    X["key_out"] = (X.out_share > 0).astype(float).where(X.out_share.notna())
    X["back_share"] = res["home"].back_share.values + res["away"].back_share.values
    X["key_back"] = (X.back_share > 0).astype(float).where(X.back_share.notna())
    return X


def schedule_features(G: pd.DataFrame) -> pd.DataFrame:
    from data.ncaab_stages import load_schedules
    s = load_schedules(range(2011, 2022))
    s["season"] = season_of(s.date)
    long = pd.concat([s[["date", "season", "home"]].rename(columns={"home": "team"}),
                      s[["date", "season", "away"]].rename(columns={"away": "team"})]).drop_duplicates()
    long = long.sort_values(["team", "date"])
    long["rest"] = long.groupby(["team", "season"]).date.diff().dt.days
    rest = long.drop_duplicates(["team", "date"]).set_index(["team", "date"]).rest
    X = pd.DataFrame(index=G.index)
    d = G.date.dt.normalize()
    rh = rest.reindex(pd.MultiIndex.from_arrays([G.home, d])).values
    ra = rest.reindex(pd.MultiIndex.from_arrays([G.away, d])).values
    both = np.isfinite(rh) & np.isfinite(ra)
    X["long_layoff"] = np.where(both, ((rh >= 7) & (ra >= 7)).astype(float), np.nan)
    X["played_yesterday"] = np.where(both, ((rh == 1) | (ra == 1)).astype(float), np.nan)
    sch = s.set_index("game_id")
    gid = G.espn_game_id
    cap = gid.map(sch.venue_capacity)
    X["football_stadium"] = (cap >= 30000).astype(float).where(cap.notna() & (cap > 0))
    reg = s[s.stage.isin(["conf_regular", "nonconf_home"]) & ~s.neutral_site.astype(bool)]
    last_home = reg.sort_values("date").groupby(["home", "season"]).game_id.last()
    X["senior_night"] = gid.isin(set(last_home.values)).astype(float).where(gid.notna())
    return X


def main():
    P, cals, _ = load()
    P = P[P.season.isin(LA.ERA)]
    M = main_line_probs(P, cals)
    M = M[M.eligible].copy()
    M["era"] = M.season.map(LA.ERA)
    s = LA.schedules()
    G = LA.pregame_features(M, s).reset_index(drop=True)
    G["r"] = G.outcome - G.line - G.mu
    G["bet"] = (G.p_best >= LA.P_MIN) & ~G.best_push
    G["won"] = G.best_win.astype(int)
    G["margin"] = G.best_side * (G.outcome - G.line)
    G = pd.concat([G, venue_features(G), availability(G), schedule_features(G)], axis=1)
    eras = list(dict.fromkeys(LA.ERA.values()))

    ideas = {"venue factor (home floor ran over its closes)": ("venue_factor", "+"),
             "venue split (home floor minus the team's road games)": ("venue_split", "+"),
             "key player out (25+ min, either team)": ("key_out", "-"),
             "key minutes out (share of 200)": ("out_share", "-"),
             "key player back after missing the last game": ("key_back", "+"),
             "long layoff (both teams 7+ days off)": ("long_layoff", "-"),
             "played yesterday (either team)": ("played_yesterday", "-"),
             "football-stadium venue (30,000+ seats)": ("football_stadium", "-"),
             "senior night (home team's last home game)": ("senior_night", "none")}
    rows = []
    for label, (col, expect) in ideas.items():
        rec = {"idea": label, "expected": expect}
        for era in eras:
            E = G[G.era == era]
            short = "disc" if era.startswith("disc") else "val"
            x = E[col].values.astype(float)
            t_all, n_all = LA.t_stat(x, E.r.values.astype(float))
            Bt = E[E.bet]
            t_bet, _ = LA.t_stat(Bt[col].values.astype(float), Bt.margin.values.astype(float))
            rec[f"t all games ({short})"] = t_all
            rec[f"t our bets ({short})"] = t_bet
            rec[f"games with a value ({short})"] = n_all
            if set(np.unique(x[np.isfinite(x)])) <= {0.0, 1.0}:
                rec[f"flagged games ({short})"] = int(np.nansum(x))
                rec[f"miss when flagged ({short})"] = float(E.r[E[col] == 1].mean())
        d, v = rec["t all games (disc)"], rec["t all games (val)"]
        rec["lead?"] = bool(np.isfinite(d) and np.isfinite(v) and abs(d) >= 2 and abs(v) >= 1.5 and np.sign(d) == np.sign(v))
        rec["direction as expected?"] = (None if expect == "none" or not rec["lead?"]
                                         else bool((np.sign(d) > 0) == (expect == "+")))
        rows.append(rec)
    S = pd.DataFrame(rows)

    # bets: win rate with and without each flag, by side
    bet_rows = []
    for label, (col, _) in ideas.items():
        if col in ("venue_factor", "venue_split", "out_share"):
            continue
        for era in eras:
            Bt = G[G.bet & (G.era == era) & G[col].notna()]
            for side, sname in ((1, "Over"), (-1, "Under")):
                for flag in (1.0, 0.0):
                    x = Bt[(Bt.best_side == side) & (Bt[col] == flag)]
                    if len(x):
                        bet_rows.append({"idea": label, "era": era, "side": sname, "flagged": bool(flag), "bets": len(x),
                                         "won": x.won.mean(), "ROI @-110": (x.won * 100 / 110 - (1 - x.won)).mean()})
    BR = pd.DataFrame(bet_rows)

    # execution check: does the close overshoot after big moves?
    G["move"] = G.line_close - G.line_open
    G["after_close"] = G.outcome - G.line_close
    ov = []
    for era in eras:
        E = G[(G.era == era) & G.ok_close.astype(bool) & G.line_close.notna()]
        t, n = LA.t_stat(E.move.values.astype(float), E.after_close.values.astype(float))
        rec = {"era": era, "games": n, "t slope": t}
        m = E.move
        for lab, sel in (("close fell 3+", m <= -3), ("fell 1-3", (m > -3) & (m <= -1)), ("within 1", (m > -1) & (m < 1)),
                         ("rose 1-3", (m >= 1) & (m < 3)), ("rose 3+", m >= 3)):
            rec[f"total - close: {lab}"] = E.after_close[sel].mean()
            rec[f"n: {lab}"] = int(sel.sum())
        ov.append(rec)
    OV = pd.DataFrame(ov)
    d0, v0 = OV["t slope"].iloc[0], OV["t slope"].iloc[1]
    overshoot_lead = bool(d0 <= -2 and v0 <= -1.5)

    # altitude checks
    sch = LA.schedules()
    home_city = sch[~sch.neutral_site.astype(bool)].groupby("home_id").city.agg(lambda x: x.mode().iloc[0] if len(x.mode()) else "")
    alt_team = {f"e{k}" for k, v in home_city.items() if v in LA.HIGH_ALT}
    nb = ~G.neutral_i.astype(bool)
    alt_rows = []
    for era in eras:
        E = G[(G.era == era) & nb]
        base = E[(E.high_altitude == 0) & ~E.home.isin(alt_team) & ~E.away.isin(alt_team)].r
        groups = {"all other games (low venue, no altitude team)": base,
                  "at altitude, visitor from low altitude": E[(E.high_altitude == 1) & ~E.away.isin(alt_team)].r,
                  "at altitude, visitor also based at altitude": E[(E.high_altitude == 1) & E.away.isin(alt_team)].r,
                  "altitude-based team on the road at low altitude": E[(E.high_altitude == 0) & E.away.isin(alt_team)].r}
        for lab, x in groups.items():
            alt_rows.append({"era": era, "games": lab, "n": len(x), "miss vs forecast": x.mean(),
                             "standard error": x.std() / np.sqrt(len(x))})
    AL = pd.DataFrame(alt_rows)
    H = G[nb & G.home_1h.notna() & G.home_2h_reg.notna() & G.high_altitude.notna()].copy()
    H["h1"], H["h2"] = H.home_1h + H.away_1h, H.home_2h_reg + H.away_2h_reg
    low = H[H.high_altitude == 0]
    fh = float(low.h1.sum() / (low.h1 + low.h2).sum())
    H["first half"] = H.h1 - fh * (H.line + H.mu)
    H["second half (regulation)"] = H.h2 - (1 - fh) * (H.line + H.mu)
    HH = H.groupby(["era", "high_altitude"])[["first half", "second half (regulation)"]].mean().reset_index()
    HH["high_altitude"] = HH.high_altitude.map({0.0: "low venue", 1.0: "high-altitude venue"})
    venues = G[(G.high_altitude == 1) & nb].groupby("city").r.agg(["size", "mean"]).reset_index()
    venues.columns = ["city", "games", "miss vs forecast"]
    pos = int((venues["miss vs forecast"] > 0).sum())

    lines = ["# Loss autopsy, round 2 (NCAAB straight bets, 2011-21; 2021-26 not read)\n",
             "Ideas and their expected direction were written down in the script before it was first run. "
             "Same rule as round 1: |t| >= 2 in discovery and the same sign with |t| >= 1.5 in validation. "
             "t all games = predicts the miss against the engine's forecast; t our bets = predicts the bets' own margin.\n",
             "## Ideas\n", df_to_md(S, "{:.2f}"), "",
             "Bets with and without each flag (win rate, ROI at -110):\n", df_to_md(BR, "{:.3f}"), "",
             "## Does the closing total overshoot after big moves? (for middling)\n",
             "If it did, the total would land on the far side of the close after big moves (t slope = slope of (total - close) on (close - open); negative = overshoot).\n",
             df_to_md(OV, "{:.2f}"), "", f"Overshoot lead: **{overshoot_lead}**.\n",
             "## High-altitude venues: does the round-1 lead look physical?\n",
             df_to_md(AL, "{:.2f}"), "",
             f"By half (first-half share of regulation points at low venues {fh:.3f}; miss vs the forecast split by that share):\n",
             df_to_md(HH, "{:.2f}"), "",
             f"Venues: {pos} of {len(venues)} high-altitude floors ran above the forecast (2011-21, non-neutral games).\n",
             df_to_md(venues.sort_values("miss vs forecast", ascending=False), "{:.2f}"), ""]
    out = ROOT / "reports" / "loss_autopsy_round2.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    keep = ["game_key", "season", "era", "r", "bet", "won", "best_side", "margin", "venue_factor", "venue_split", "out_share",
            "key_out", "back_share", "key_back", "long_layoff", "played_yesterday", "football_stadium", "senior_night",
            "high_altitude", "move", "after_close"]
    G[keep].to_parquet(ROOT / "data" / "processed" / "loss_autopsy_round2.parquet", index=False)
    log_experiment("loss_autopsy_round2", {"rule": "|t|>=2 disc and |t|>=1.5 same sign val", "k_venue": K_VENUE,
                                           "venue_seasons": VENUE_SEASONS, "key_min": KEY_MIN, "prev_games": PREV_GAMES},
                   {"ideas": S.to_dict("records"), "overshoot": OV.to_dict("records"), "overshoot_lead": overshoot_lead})


if __name__ == "__main__":
    main()
