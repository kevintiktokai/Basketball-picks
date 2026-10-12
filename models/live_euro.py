"""Live pieces of the European engine: the upcoming official schedule, the ratings model's
expected total for games not yet played, its bias against Pinnacle, and matching live odds
events to official games. Used by scripts/predict_euro.py and scripts/grade_euro.py.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from data import oddspapi as op
from data.euroleague import RAW as EURO_RAW
from data.euroleague import fetch_season, parse
from features.ratings import DailyRatings

ROOT = Path(__file__).resolve().parents[1]
TZ = "Europe/Madrid"
SEASON_YEAR = 2026                                          # 2026-27
PAST_CODES = [f"{c}{y}" for c in ("E", "U") for y in range(2016, SEASON_YEAR)]
CUR_CODES = [f"E{SEASON_YEAR}", f"U{SEASON_YEAR}"]
BIAS_CACHE = ROOT / "data" / "processed" / "euro_model_bias.json"
ALIASES = {"red star": "crvena zvezda", "olimpia milano": "olimpia milan", "olympiakos": "olympiacos",
           "efes": "anadolu efes", "maccabi": "maccabi tel aviv", "hapoel": "hapoel tel aviv"}


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def upcoming(days: float = 3.0) -> pd.DataFrame:
    """Official games not yet played that start within `days` (EuroLeague and EuroCup)."""
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for code in CUR_CODES:
        comp = code[0]
        data = _get_json(f"https://api-live.euroleague.net/v2/competitions/{comp}/seasons/{code}/games")["data"]
        for g in data:
            if g.get("played"):
                continue
            start = pd.Timestamp(g["utcDate"]).tz_convert("UTC") if g.get("utcDate") else pd.NaT
            if pd.isna(start) or start < now - pd.Timedelta(hours=3) or start > now + pd.Timedelta(days=days):
                continue
            L, R = g["local"]["club"], g["road"]["club"]
            refs = [(g.get(f"referee{i}") or {}).get("name") for i in (1, 2, 3)]
            rows.append({"game_key": f"{code}_{g['gameCode']}", "competition": "euroleague" if comp == "E" else "eurocup",
                         "season": f"{SEASON_YEAR}-{str(SEASON_YEAR + 1)[2:]}", "start": start, "round": g.get("round"),
                         "home": L["code"], "away": R["code"],
                         "home_name": L["name"], "away_name": R["name"],
                         "home_alt": " / ".join(filter(None, {L.get("abbreviatedName"), L.get("editorialName")})),
                         "away_alt": " / ".join(filter(None, {R.get("abbreviatedName"), R.get("editorialName")})),
                         "venue": (g.get("venue") or {}).get("name"), "refs": ", ".join(filter(None, refs))})
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True) if rows else pd.DataFrame()


def played_games() -> tuple[pd.DataFrame, pd.DataFrame]:
    for code in CUR_CODES:                                       # refresh the current season (cached files kept)
        try:
            fetch_season(code)
        except Exception as e:                                   # noqa: BLE001
            print(f"  could not refresh {code}: {e}")
    return parse(PAST_CODES + CUR_CODES)


def model_totals(up: pd.DataFrame, G: pd.DataFrame | None = None, B: pd.DataFrame | None = None) -> pd.Series:
    """Expected total for each upcoming game: the European ratings model (scripts/euro_info_study.py
    settings) fitted on every game played before today, per competition."""
    if G is None:
        G, B = played_games()
    G = G.sort_values("date").copy()
    poss = B.groupby("game_key").poss.first()
    G["poss"] = G.game_key.map(poss)
    G["neutral"] = G["round"].eq("FF")
    today = pd.Timestamp.now(tz=TZ).tz_localize(None).normalize()
    G = G[pd.to_datetime(G.date) < today]
    U = up.assign(date=today, neutral=False, home_pts=np.nan, away_pts=np.nan, poss=np.nan)
    out = {}
    cols = ["date", "season", "home", "away", "neutral", "home_pts", "away_pts", "poss", "game_key"]
    for comp in U.competition.unique():
        frame = pd.concat([G[G.competition == comp][cols], U[U.competition == comp][cols]], ignore_index=True)
        frame["date"] = pd.to_datetime(frame.date)
        r = DailyRatings(half_life_days=60, prev_season_weight=0.25, ridge=3.0, venue_tempo=True).run(frame)
        r = r.set_index("game_key")
        exp = r.rt_eff_total.fillna(r.rt_pts_home + r.rt_pts_away)
        out.update(exp.reindex(U[U.competition == comp].game_key).to_dict())
    return pd.Series(out, dtype=float)


def model_bias() -> dict:
    """Mean of (model expected total - Pinnacle's no-vig line when Pinnacle opened) over the cached
    2025-26 games with odds: the centring the locked strategy applies before asking whether the
    model agrees (backtest/euro_cards.legs). Cached in data/processed/euro_model_bias.json."""
    if BIAS_CACHE.exists():
        return json.loads(BIAS_CACHE.read_text())
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from backtest.euro_cards import decision_times
    from euro_dev_study import results
    from euro_info_study import build
    from features.euro_market import board_at, fair_curve, timelines
    T = timelines()
    C = fair_curve(board_at(T, decision_times(T, "pinnacle_open")))
    _, F = results(T)
    G = build()
    exp = F.set_index("fixture_id").game_key.map(G.set_index("game_key").exp_total)
    dev = (C.set_index("fixture_id").fair_mu.reindex(exp.index) * -1 + exp).dropna()
    out = {"mean": float(dev.mean()), "sd": float(dev.std()), "games": int(len(dev)),
           "source": "OddsPapi cache (2025-26), Pinnacle at its opening, euro_info_study ratings"}
    BIAS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    BIAS_CACHE.write_text(json.dumps(out, indent=1))
    return out


def _canon(s: str) -> str:
    s = str(s or "").lower()
    for k, v in ALIASES.items():
        if k in s and v not in s:
            s = s.replace(k, v)
    return s


def match(events: pd.DataFrame, up: pd.DataFrame, max_hours: float = 6.0) -> pd.DataFrame:
    """events: fixture_id, start, home_name, away_name (odds feed). Adds game_key and match_score:
    an official game starting within `max_hours`, best min(home, away) name similarity >= 0.5,
    home/away in either orientation (flagged)."""
    keys, scores, swapped = [], [], []
    for e in events.itertuples(index=False):
        cand = up[(up.start - e.start).abs() <= pd.Timedelta(hours=max_hours)]
        best, bs, sw = None, 0.0, False
        for g in cand.itertuples(index=False):
            hn = [g.home_name] + str(g.home_alt).split(" / ")
            an = [g.away_name] + str(g.away_alt).split(" / ")
            sim = lambda a, names: max(op.name_sim(_canon(a), _canon(n)) for n in names)   # noqa: E731
            s1 = min(sim(e.home_name, hn), sim(e.away_name, an))
            s2 = min(sim(e.home_name, an), sim(e.away_name, hn))
            if max(s1, s2) > bs:
                best, bs, sw = g.game_key, max(s1, s2), s2 > s1
        ok = bs >= 0.5
        keys.append(best if ok else None)
        scores.append(bs)
        swapped.append(sw and ok)
    return events.assign(game_key=keys, match_score=scores, swapped=swapped)
