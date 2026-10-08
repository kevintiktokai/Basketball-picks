"""OddsPapi adapter: historical opening/closing totals for EuroLeague and EuroCup.

Historical odds are the one input the European engine still lacks (the official
EuroLeague API in data/euroleague.py gives games, box scores and referees, but no
prices). OddsPapi's free tier serves, for each finished fixture, the first and last
price it recorded for every outcome at every bookmaker (GET /fixtures/odds/clv),
including Pinnacle and whole alternate-total ladders. This module fetches those
politely, caches them, and builds the market frame the engine uses elsewhere:
opening and closing main line + prices per book, plus every alternate line.

The key comes from the environment variable ODDSPAPI_KEY (or is injected by the network
proxy) and is sent as a header, so it never appears in URLs, cache files or logs.

usage: python -m data.oddspapi probe                      # key works? how far back do odds go?
       python -m data.oddspapi fetch euroleague 2021-09-01 2026-06-30
       python -m data.oddspapi parse euroleague           # -> data/processed/odds_euroleague*.parquet
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from config_loader import ROOT

BASE = "https://v5.oddspapi.io/en"
RAW = ROOT / "data" / "raw" / "oddspapi"
PROC = ROOT / "data" / "processed"
BASKETBALL = 11
TOURNAMENTS = {"euroleague": 138}        # documented id; others are looked up by slug
BOOKS = ["pinnacle", "bet365", "unibet", "williamhill", "betway", "bwin", "1xbet", "marathonbet"]
MIN_INTERVAL = 0.7                       # history/fixture endpoints allow 100 requests/minute
FINISHED = 2
_last_call = [0.0]


def _headers() -> dict:
    """The key comes from ODDSPAPI_KEY; when it is absent the request goes out without it, so a
    key injected by a network proxy (environment 'network secret') also works."""
    h = {"Accept": "application/json", "User-Agent": "basketball-totals-research"}
    k = os.environ.get("ODDSPAPI_KEY", "").strip()
    if k:
        h["X-API-Key"] = k
    return h


def _get_json(path: str, params: dict):
    """One polite GET; retries on 429 / transient errors. Returns parsed JSON."""
    url = f"{BASE}{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    for attempt in range(5):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            body = e.read()[:300].decode("utf-8", "ignore")
            if e.code == 401:
                raise SystemExit("OddsPapi rejected the request (no or invalid key). Add a free key from "
                                 "oddspapi.io to the environment as ODDSPAPI_KEY, then start a new session.")
            raise RuntimeError(f"OddsPapi {path} -> HTTP {e.code}: {body}") from None
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OddsPapi {path}: gave up after retries")


def _cached(path, fetch):
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


# ---------------------------------------------------------------- metadata
def markets() -> pd.DataFrame:
    """outcomeId -> market (type, period, line, side) for basketball. Cached."""
    data = _cached(RAW / f"markets_{BASKETBALL}.json", lambda: _get_json("/markets", {"sportId": BASKETBALL}))
    rows = [{"outcome_id": o["outcomeId"], "market_id": m["marketId"], "market_type": m.get("marketType"),
             "period": m.get("period"), "line": m.get("handicap"), "side": str(o.get("outcomeName", "")).lower(),
             "player_prop": bool(m.get("playerProp"))}
            for m in data for o in m.get("outcomes", [])]
    return pd.DataFrame(rows)


def tournament_id(name: str) -> int:
    if name in TOURNAMENTS:
        return TOURNAMENTS[name]
    data = _cached(RAW / f"tournaments_{BASKETBALL}.json", lambda: _get_json("/tournaments", {"sportId": BASKETBALL}))
    hits = [t for t in data if name.replace("-", "") in str(t.get("tournamentSlug", "")).replace("-", "")]
    if not hits:
        raise SystemExit(f"no basketball tournament matching {name!r}; run `probe` to list them")
    return int(sorted(hits, key=lambda t: len(t["tournamentSlug"]))[0]["tournamentId"])


# ---------------------------------------------------------------- fetching
def fixtures(tid: int, start: str, end: str, window_days: int = 14) -> list[dict]:
    """All fixtures of a tournament between two dates. Windows that are fully in the past are
    cached (their schedule can no longer change); the current window is always refreshed."""
    out, t0, t1 = [], pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    now = pd.Timestamp.now(tz="UTC")
    while t0 < t1:
        w1 = min(t0 + pd.Timedelta(days=window_days), t1)
        params = {"tournamentId": tid, "startTimeFrom": int(t0.timestamp()), "startTimeTo": int(w1.timestamp())}
        path = RAW / str(tid) / "fixtures" / f"{t0:%Y%m%d}_{w1:%Y%m%d}.json"
        if w1 < now - pd.Timedelta(days=2):
            out += _cached(path, lambda p=params: _get_json("/fixtures", p))
        else:
            out += _get_json("/fixtures", params)
        t0 = w1
    seen, uniq = set(), []
    for f in out:
        if f["fixtureId"] not in seen:
            seen.add(f["fixtureId"])
            uniq.append(f)
    return uniq


def _slim_clv(data: dict, totals_ids: set) -> dict:
    """Keep fixture meta + full-game totals/spread outcomes only (the full feed is ~100x larger)."""
    keep = {}
    for book, odds in (data.get("odds") or {}).items():
        sel = {k: v for k, v in odds.items() if int(k.split(":")[2]) in totals_ids}
        if sel:
            keep[book] = sel
    return {**{k: v for k, v in data.items() if k != "odds"}, "odds": keep}


def fetch(name: str, start: str, end: str, books=None) -> int:
    """Opening/closing prices (OLV/CLV) for every finished fixture in [start, end]. Resumable."""
    tid = tournament_id(name)
    M = markets()
    keep_ids = set(M[M.market_type.isin(["totals", "spreads"]) & ~M.player_prop
                     & M.period.isin(["result", "fulltime"])].outcome_id)
    books = ",".join(books or BOOKS)
    n = 0
    for f in fixtures(tid, start, end):
        if (f.get("status") or {}).get("statusId") != FINISHED:
            continue
        path = RAW / str(tid) / "clv" / f"{f['fixtureId']}.json"
        if path.exists():
            continue
        data = _get_json("/fixtures/odds/clv", {"fixtureId": f["fixtureId"], "bookmakers": books})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_slim_clv(data, keep_ids)))
        n += 1
    return n


# ---------------------------------------------------------------- parsing
def ladder(name: str) -> pd.DataFrame:
    """Long table: fixture x book x line x side with opening and closing price."""
    tid = tournament_id(name)
    M = markets().set_index("outcome_id")
    rows = []
    for p in sorted((RAW / str(tid) / "clv").glob("*.json")):
        d = json.loads(p.read_text())
        part, sc = d.get("participants") or {}, ((d.get("scores") or {}).get("result") or {})
        meta = {"fixture_id": d["fixtureId"], "start": pd.Timestamp(d["startTime"], unit="s", tz="UTC"),
                "home_name": part.get("participant1Name"), "away_name": part.get("participant2Name"),
                "home_pts": sc.get("participant1Score"), "away_pts": sc.get("participant2Score")}
        for book, odds in (d.get("odds") or {}).items():
            for odds_id, v in odds.items():
                oid = int(odds_id.split(":")[2])
                if oid not in M.index or M.at[oid, "market_type"] != "totals":
                    continue
                o, c = v.get("olv") or {}, v.get("clv") or {}
                rows.append({**meta, "book": book, "period": M.at[oid, "period"], "line": float(M.at[oid, "line"]),
                             "side": M.at[oid, "side"], "open_price": o.get("price"), "open_ms": o.get("changedAt"),
                             "close_price": c.get("price"), "close_ms": c.get("changedAt"),
                             "close_active": c.get("active", True)})
    L = pd.DataFrame(rows)
    if L.empty:
        return L
    # full-game totals including overtime ('result'); 'fulltime' only where a fixture has no 'result' market
    has_result = L[L.period == "result"].fixture_id.unique()
    L = L[(L.period == "result") | ~L.fixture_id.isin(has_result)]
    return L.drop(columns="period")


def _two_way(L: pd.DataFrame, which: str) -> pd.DataFrame:
    w = L.pivot_table(index=["fixture_id", "book", "line"], columns="side",
                      values=[f"{which}_price", f"{which}_ms"], aggfunc="first")
    w.columns = [f"{a.split('_')[1]}_{b}" for a, b in w.columns]
    w = w.dropna(subset=["price_over", "price_under"]).reset_index()
    w["imb"] = (1 / w.price_over - 1 / w.price_under).abs()          # 0 = balanced (main line)
    w["first_ms"] = w[["ms_over", "ms_under"]].min(axis=1)
    return w


def main_lines(L: pd.DataFrame) -> pd.DataFrame:
    """Per fixture x book: opening main line = the earliest-posted near-balanced line;
    closing main line = the most balanced line still active at the close."""
    o = _two_way(L, "open")
    o = o[o.imb < 0.08]
    first = o.groupby(["fixture_id", "book"]).first_ms.transform("min")
    o = o[o.first_ms <= first + 10 * 60 * 1000]                  # lines posted in the first 10 minutes
    o = o.sort_values(["fixture_id", "book", "imb"]).groupby(["fixture_id", "book"]).head(1)
    act = L[L.close_active.fillna(True).astype(bool)]
    c = _two_way(act, "close").sort_values(["fixture_id", "book", "imb"]).groupby(["fixture_id", "book"]).head(1)
    o = o.rename(columns={"line": "open_line", "price_over": "open_over", "price_under": "open_under",
                          "first_ms": "open_ms"})[["fixture_id", "book", "open_line", "open_over", "open_under", "open_ms"]]
    c = c.rename(columns={"line": "close_line", "price_over": "close_over", "price_under": "close_under"})[
        ["fixture_id", "book", "close_line", "close_over", "close_under"]]
    return o.merge(c, on=["fixture_id", "book"], how="outer")


def match_official(F: pd.DataFrame, G: pd.DataFrame) -> pd.DataFrame:
    """Attach official game_key by date (UTC start vs local date, +-1 day) and exact final score."""
    G = G.assign(d0=pd.to_datetime(G.date).dt.normalize())
    out = []
    for f in F.itertuples(index=False):
        d = f.start.tz_convert(None).normalize()
        cand = G[(G.d0 >= d - pd.Timedelta(days=1)) & (G.d0 <= d + pd.Timedelta(days=1))
                 & (G.home_pts == f.home_pts) & (G.away_pts == f.away_pts)]
        out.append(cand.game_key.iloc[0] if len(cand) == 1 else None)
    return F.assign(game_key=out)


def parse(name: str, games: pd.DataFrame | None = None):
    L = ladder(name)
    if L.empty:
        raise SystemExit("no cached odds yet; run fetch first")
    ML = main_lines(L)
    fx = L.groupby("fixture_id")[["start", "home_name", "away_name", "home_pts", "away_pts"]].first().reset_index()
    if games is not None:
        fx = match_official(fx, games)
    PROC.mkdir(parents=True, exist_ok=True)
    L.to_parquet(PROC / f"odds_{name}_ladder.parquet", index=False)
    ML.merge(fx, on="fixture_id").to_parquet(PROC / f"odds_{name}.parquet", index=False)
    return L, ML.merge(fx, on="fixture_id")


# ---------------------------------------------------------------- probe
def probe() -> None:
    """Checks the key and reports, per season, whether finished EuroLeague/EuroCup fixtures carry
    totals odds (one fixture list + one CLV call per competition and season: ~40 requests)."""
    books = _get_json("/bookmakers", {})
    slugs = {b["slug"] for b in books}
    print(f"key OK: {len(books)} bookmakers visible; default set present: {[b for b in BOOKS if b in slugs]}")
    T = _get_json("/tournaments", {"sportId": BASKETBALL})
    hits = [t for t in T if any(s in str(t.get("tournamentSlug", "")) for s in ("euroleague", "eurocup"))]
    print("matching tournaments:", [(t["tournamentId"], t["tournamentSlug"]) for t in hits])
    euro = []
    for name in ("euroleague", "eurocup"):                  # the men's competition: shortest matching slug
        cand = sorted((t for t in hits if name in str(t["tournamentSlug"])), key=lambda t: len(t["tournamentSlug"]))
        euro += cand[:1]
    M = markets()
    tot = set(M[(M.market_type == "totals") & ~M.player_prop].outcome_id)
    for t in euro:
        for y in range(2018, pd.Timestamp.now().year + 1):
            fx = _get_json("/fixtures", {"tournamentId": t["tournamentId"],
                                         "startTimeFrom": int(pd.Timestamp(f"{y}-11-01", tz="UTC").timestamp()),
                                         "startTimeTo": int(pd.Timestamp(f"{y}-11-30", tz="UTC").timestamp())})
            fin = [f for f in fx if (f.get("status") or {}).get("statusId") == FINISHED]
            if not fin:
                print(f"  {t['tournamentSlug']} Nov {y}: no finished fixtures listed")
                continue
            d = _get_json("/fixtures/odds/clv", {"fixtureId": fin[0]["fixtureId"], "bookmakers": ",".join(BOOKS)})
            n = {b: sum(int(k.split(":")[2]) in tot for k in o) for b, o in (d.get("odds") or {}).items()}
            print(f"  {t['tournamentSlug']} Nov {y}: {len(fin)} finished fixtures; totals prices per book on one: {n}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        probe()
    elif cmd == "fetch":
        name, start, end = sys.argv[2], sys.argv[3], sys.argv[4]
        print(f"{name}: fetched {fetch(name, start, end)} new fixtures")
    elif cmd == "parse":
        from data.euroleague import parse as euro_parse
        name = sys.argv[2]
        pre = "E" if name == "euroleague" else "U"
        G, _ = euro_parse([f"{pre}{y}" for y in range(2016, pd.Timestamp.now().year + 1)])
        L, F = parse(name, G)
        print(f"{F.fixture_id.nunique()} fixtures, {F.book.nunique()} books, "
              f"{F.game_key.notna().groupby(F.fixture_id).first().mean():.0%} matched to official games")
    else:
        raise SystemExit(__doc__)
