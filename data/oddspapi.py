"""OddsPapi adapter (free key): historical EuroLeague / EuroCup totals within a monthly budget.

Historical odds are the one input the European engine still lacks (data/euroleague.py gives
games, box scores and referees, but no prices). OddsPapi's free tier serves the v4 API: the key
is the `apiKey` query parameter, about 200 requests a month are allowed, and one
/historical-odds call returns up to three bookmakers' full price timelines for every market of
one game. That single call holds the opening line, the closing line and the alternate ladder,
so the budget goes one game per request.

Every network request is counted in data/raw/oddspapi/usage.json and refused once the month's
budget is spent (ODDSPAPI_MONTHLY_BUDGET, default 200). Every response is cached, so nothing is
ever requested twice. The key is read from the environment and never written anywhere.

usage: python -m data.oddspapi probe       # ~8 requests: key, market catalogue, how far back odds go
       python -m data.oddspapi plan        # requests the backfill needs, months at this budget
       python -m data.oddspapi update      # spend this month's budget, oldest games first
       python -m data.oddspapi parse       # -> data/processed/odds_euro.parquet (+ _ladder)
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from config_loader import ROOT

BASE = "https://api.oddspapi.io/v4"
RAW = ROOT / "data" / "raw" / "oddspapi"
PROC = ROOT / "data" / "processed"
BASKETBALL = 11
TOURNAMENTS = {"euroleague": 138}          # documented id; EuroCup is looked up by slug
FIRST_SEASON_START = "2025-09-20"
HISTORY_START = "2026-01-20"               # measured 2026-10-08: none on 15 Jan 2026, present from 20 Jan
MAX_MISSES = 5                             # consecutive games without history -> stop that season
BOOKS = "pinnacle,1xbet,betway"            # sharp reference + the two soft books with the fullest
                                           # 2025-26 archive (bet365 has almost none before 2026-27)
MIN_INTERVAL = 5.5                         # free tier: ~5 s cooldown between history requests (measured)
_last_call = [0.0]


class BudgetExhausted(RuntimeError):
    pass


def budget() -> int:
    return int(os.environ.get("ODDSPAPI_MONTHLY_BUDGET", "200"))


def _month() -> str:
    return pd.Timestamp.now(tz="UTC").strftime("%Y-%m")


def used(month: str | None = None) -> int:
    p = RAW / "usage.json"
    return json.loads(p.read_text()).get(month or _month(), 0) if p.exists() else 0


def _spend(kind: str = "") -> None:
    """Count one request (kind='' -> the monthly budget; 'throttled' -> a separate tally of
    rate-limited requests, which the API rejects before serving)."""
    p = RAW / "usage.json"
    u = json.loads(p.read_text()) if p.exists() else {}
    m = _month() + (f"-{kind}" if kind else "")
    if not kind and u.get(m, 0) >= budget():
        raise BudgetExhausted(f"monthly budget of {budget()} requests spent for {m}")
    u[m] = u.get(m, 0) + 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(u, indent=1))


def _unspend() -> None:
    """Move the request just counted from the budget to the 'throttled' tally."""
    p = RAW / "usage.json"
    u = json.loads(p.read_text())
    u[_month()] -= 1
    p.write_text(json.dumps(u, indent=1))
    _spend("throttled")


def _get_json(path: str, params: dict):
    """One counted GET. The key goes in the query string (the free API requires it there), so
    errors never echo the URL. Returns parsed JSON, or None on 404."""
    key = os.environ.get("ODDSPAPI_KEY", "").strip()
    if not key:
        raise SystemExit("Set ODDSPAPI_KEY (free key from oddspapi.io) in the environment, then start a new session.")
    url = f"{BASE}{path}?{urllib.parse.urlencode({**params, 'apiKey': key})}"
    for attempt in range(4):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _spend()
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "basketball-totals-research"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            _last_call[0] = time.time()                  # pace from the END of the download
            return json.loads(body)
        except urllib.error.HTTPError as e:
            _last_call[0] = time.time()
            if e.code == 404:
                return None
            if e.code == 429:
                _unspend()
                try:
                    hint = float(e.headers.get("Retry-After") or json.loads(e.read()).get("retryAfterSec") or 0)
                except Exception:  # noqa: BLE001
                    hint = 0.0
                time.sleep(max(hint, 2.0 * (attempt + 1)) + 0.5)
                continue
            if e.code in (401, 403):
                raise SystemExit(f"OddsPapi refused the key on {path} (HTTP {e.code}).") from None
            if e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OddsPapi {path}: HTTP {e.code}") from None
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OddsPapi {path}: gave up after retries")


def _cached(path, fetch):
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    if data is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    return data


# ---------------------------------------------------------------- catalogue
_NUM = re.compile(r"(\d+(?:\.\d+)?)")
_PART = ("half", "quarter", "period", "1st", "2nd", "3rd", "4th", "team", "player", "race", "odd", "even")


def markets() -> pd.DataFrame:
    """outcomeId -> (market id, kind, full game?, line, side) for basketball. Cached.
    Uses explicit fields when the catalogue has them, the market name otherwise."""
    data = _cached(RAW / f"markets_{BASKETBALL}.json", lambda: _get_json("/markets", {"sportId": BASKETBALL})) or []
    rows = []
    for m in data:
        name = str(m.get("marketName", "")).lower()
        mtype = str(m.get("marketType") or "").lower()
        period = str(m.get("period") or "").lower()
        line = m.get("handicap")
        if line is None:
            nums = _NUM.findall(name)
            line = float(nums[-1]) if nums else None
        if mtype:
            kind = "totals" if mtype == "totals" else "spreads" if mtype.startswith("spreads") else mtype
        else:
            kind = "totals" if ("over" in name and "under" in name) or "total" in name else \
                "spreads" if "handicap" in name or "spread" in name else "other"
        partial = any(k in name for k in _PART) or (period not in ("", "result", "fulltime"))
        for o in m.get("outcomes", []):
            rows.append({"outcome_id": int(o["outcomeId"]), "market_id": int(m["marketId"]), "kind": kind,
                         "full_game": not partial and not m.get("playerProp", False),
                         "incl_ot": period == "result" or "overtime" in name,
                         "line": None if line is None else float(line),
                         "side": str(o.get("outcomeName", "")).strip().lower()})
    return pd.DataFrame(rows, columns=["outcome_id", "market_id", "kind", "full_game", "incl_ot", "line", "side"])


def tournament_id(name: str) -> int:
    if name in TOURNAMENTS:
        return TOURNAMENTS[name]
    data = _cached(RAW / f"tournaments_{BASKETBALL}.json",
                   lambda: _get_json("/tournaments", {"sportId": BASKETBALL})) or []
    hits = sorted((t for t in data if name in str(t.get("tournamentSlug", "")).replace("-", "")),
                  key=lambda t: len(str(t["tournamentSlug"])))       # 'eurocup' before 'eurocup-women'
    if not hits:
        raise SystemExit(f"no basketball tournament matching {name!r}")
    return int(hits[0]["tournamentId"])


# ---------------------------------------------------------------- fetching
def _start(f: dict) -> pd.Timestamp:
    return pd.Timestamp(f["startTime"]).tz_convert("UTC") if pd.Timestamp(f["startTime"]).tzinfo \
        else pd.Timestamp(f["startTime"], tz="UTC")


def _blocks(start: pd.Timestamp, end: pd.Timestamp, days: int = 30):
    """Fixed 30-day blocks anchored on 20 September of each season, so any date range maps to
    the same cache files (a probe's lists are reused by the backfill)."""
    y = start.year if start.month >= 7 else start.year - 1
    b0 = pd.Timestamp(f"{y}-09-20")
    if start < b0:                                       # July-September: previous season's tail
        b0 = pd.Timestamp(f"{y - 1}-09-20")
    b0 += pd.Timedelta(days=days * ((start - b0).days // days))
    while b0 <= end:
        yield b0, b0 + pd.Timedelta(days=days - 1)
        b0 += pd.Timedelta(days=days)


def fixtures(tid: int, start: str, end: str) -> list[dict]:
    """A tournament's fixtures between two dates (tournamentId lifts the 10-day range cap).
    Blocks that ended more than two days ago are cached; the current one is re-read."""
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    out = []
    for b0, b1 in _blocks(t0, t1):
        params = {"tournamentId": tid, "from": f"{b0:%Y-%m-%d}", "to": f"{b1:%Y-%m-%d}"}
        path = RAW / str(tid) / "fixtures" / f"{b0:%Y%m%d}_{b1:%Y%m%d}.json"
        if b1 < today - pd.Timedelta(days=2):
            out += _cached(path, lambda p=params: _get_json("/fixtures", p)) or []
        elif b0 <= today:
            out += _get_json("/fixtures", params) or []
    seen, uniq = set(), []
    for f in out:
        d = _start(f).tz_convert(None).normalize() if f.get("startTime") else None
        if f.get("fixtureId") and f["fixtureId"] not in seen and d is not None and t0 <= d <= t1:
            seen.add(f["fixtureId"])
            uniq.append(f)
    return uniq


def _finished(f: dict, now: pd.Timestamp) -> bool:
    """Started more than 4 hours ago and not cancelled (statusId 3)."""
    return _start(f) < now - pd.Timedelta(hours=4) and f.get("statusId") != 3


def _cutoff(f: dict) -> pd.Timestamp:
    """End of the pre-game market: one minute before the scheduled start. (Books begin in-game
    pricing on the same market ids from the scheduled time, before the recorded actual start.)"""
    return _start(f) - pd.Timedelta(minutes=1)


def _slim(data: dict, keep: set, cutoff: pd.Timestamp | None = None) -> dict:
    """Keep full-game totals/spread/moneyline markets and pre-game snapshots only: in-game
    prices are ~95% of the feed and the engine never uses them."""
    books = {}
    for slug, bd in (data.get("bookmakers") or {}).items():
        mk = {}
        for mid, md in (bd.get("markets") or {}).items():
            if keep and int(mid) not in keep:
                continue
            outs = {}
            for oid, od in (md.get("outcomes") or {}).items():
                snaps = (od.get("players") or {}).get("0") or []
                if cutoff is not None:
                    snaps = [x for x in snaps if pd.Timestamp(x["createdAt"]) < cutoff]
                if snaps:
                    outs[oid] = {"players": {"0": snaps}}
            if outs:
                mk[mid] = {"outcomes": outs}
        if mk:
            books[slug] = {"markets": mk}
    return {"fixtureId": data.get("fixtureId"), "bookmakers": books}


def hist_path(tid: int, fid: str, books: str = BOOKS):
    """The first book set fetched for a game is `<id>.json`; any extra set is `<id>__<books>.json`."""
    base = RAW / str(tid) / "hist" / f"{fid}.json"
    if not base.exists() or json.loads(base.read_text()).get("_books", BOOKS) == books:
        return base
    return RAW / str(tid) / "hist" / f"{fid}__{books.replace(',', '_')}.json"


def history(f: dict, tid: int, keep: set, books: str = BOOKS):
    """Full price timelines for one finished fixture (one request), cached with its fixture meta."""
    path = hist_path(tid, f["fixtureId"], books)
    if path.exists():
        return json.loads(path.read_text())
    data = _get_json("/historical-odds", {"fixtureId": f["fixtureId"], "bookmakers": books})
    slim = {**_slim(data or {}, keep, _cutoff(f)), "_fixture": {k: f.get(k) for k in (
        "fixtureId", "startTime", "trueStartTime", "participant1Name", "participant2Name", "statusId")},
        "_tid": tid, "_books": books}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(slim))
    return slim


def _keep_ids(M: pd.DataFrame) -> set:
    return set(M[M.full_game & M.kind.isin(["totals", "spreads", "moneyline"])].market_id)


def seasons_to_cover(first: str = FIRST_SEASON_START):
    """(start, end) of each season (20 Sep - 5 Jun: 9 fixture-list windows), newest first."""
    now = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    y = now.year if now.month >= 7 else now.year - 1
    out = []
    while pd.Timestamp(f"{y}-09-20") >= pd.Timestamp(first):
        end = min(pd.Timestamp(f"{y + 1}-06-05"), now)
        if end > pd.Timestamp(f"{y}-09-20"):
            out.append((f"{y}-09-20", end.strftime("%Y-%m-%d")))
        y -= 1
    return out


def update(names=("euroleague", "eurocup"), first: str = HISTORY_START, books: str = BOOKS) -> dict:
    """Spend the remaining monthly budget on finished games, OLDEST first across all competitions:
    the free archive may be a rolling window, so the oldest games are the ones about to
    disappear. A competition-season stops after MAX_MISSES consecutive games without history.
    Resumable; stops cleanly at the budget."""
    M = markets()
    keep = _keep_ids(M)
    now = pd.Timestamp.now(tz="UTC")
    got = {n: 0 for n in names}
    try:
        queue = []
        for start, end in reversed(seasons_to_cover(FIRST_SEASON_START)):
            start = max(start, first)
            if start > end:
                continue
            for n in names:
                tid = tournament_id(n)
                queue += [(_start(f), n, tid, start, f) for f in fixtures(tid, start, end) if _finished(f, now)]
        misses = {}
        for _, n, tid, season, f in sorted(queue, key=lambda q: q[0]):
            if misses.get((n, season), 0) >= MAX_MISSES:
                continue
            path = RAW / str(tid) / "hist" / f"{f['fixtureId']}.json"
            h = json.loads(path.read_text()) if path.exists() else None
            if h is None:
                h = history(f, tid, keep, books)
                got[n] += 1
            misses[(n, season)] = 0 if h["bookmakers"] else misses.get((n, season), 0) + 1
    except BudgetExhausted as e:
        print(f"stopped: {e}")
    return got


# ---------------------------------------------------------------- parsing
def _ms(ts) -> float:
    return pd.Timestamp(ts).value / 1e6


def ladder() -> pd.DataFrame:
    """Long table: fixture x book x line x side with opening and closing price (full-game totals)."""
    M = markets()
    tot = M[(M.kind == "totals") & M.full_game & M.side.isin(["over", "under"])]
    tot = tot.drop_duplicates("outcome_id").set_index("outcome_id")
    rows = []
    for p in sorted(RAW.glob("*/hist/*.json")):
        d = json.loads(p.read_text())
        f = d.get("_fixture") or {}
        start = _cutoff(f)
        meta = {"fixture_id": f.get("fixtureId"), "tid": d.get("_tid"), "start": start,
                "home_name": f.get("participant1Name"), "away_name": f.get("participant2Name")}
        for book, bd in (d.get("bookmakers") or {}).items():
            for md in (bd.get("markets") or {}).values():
                for oid, od in (md.get("outcomes") or {}).items():
                    if int(oid) not in tot.index:
                        continue
                    snaps = sorted((s for s in ((od.get("players") or {}).get("0") or []) if s.get("price")),
                                   key=lambda s: s["createdAt"])
                    pre = [s for s in snaps if pd.Timestamp(s["createdAt"]) < start]
                    live = [s for s in pre if s.get("active", True) is not False]
                    if not live:
                        continue
                    o, c = live[0], live[-1]
                    m = tot.loc[int(oid)]
                    rows.append({**meta, "book": book, "incl_ot": bool(m.incl_ot), "line": m.line, "side": m.side,
                                 "open_price": o["price"], "open_ms": _ms(o["createdAt"]),
                                 "close_price": c["price"], "close_ms": _ms(c["createdAt"]),
                                 "last_ms": _ms(pre[-1]["createdAt"]),
                                 "last_active": pre[-1].get("active", True) is not False})
    L = pd.DataFrame(rows)
    if L.empty:
        return L
    # the feed records changes only, so a line's last active price is its price at the close;
    # a line that went inactive within 30 minutes of the book's last pre-game update was still
    # offered (books suspend everything just before tip-off); earlier means it was withdrawn
    end = L.groupby(["fixture_id", "book"]).last_ms.transform("max")
    L["close_active"] = L.last_active | (end - L.last_ms <= 30 * 60 * 1000)
    L = L.drop(columns=["last_ms", "last_active"])
    # totals including overtime where the book prices them; regulation-only lines otherwise
    has_ot = L[L.incl_ot].groupby(["fixture_id", "book"]).size()
    key = pd.MultiIndex.from_frame(L[["fixture_id", "book"]])
    return L[L.incl_ot | ~key.isin(has_ot.index)].drop(columns="incl_ot").reset_index(drop=True)


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
    closing main line = the most balanced line still offered at the close."""
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


_STOP = {"basketball", "basket", "club", "the", "bc", "kk", "bk", "sad", "team", "fc", "as", "cb"}


def _tokens(s) -> list[str]:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return [t for t in re.findall(r"[a-z0-9]{3,}", s) if t not in _STOP]


def name_sim(a, b) -> float:
    """Share of the shorter name's tokens found (fuzzily) in the other: 'Olimpia Milano' vs
    'EA7 EMPORIO ARMANI MILAN' -> 0.5, 'Baskonia' vs 'KOSNER BASKONIA VITORIA-GASTEIZ' -> 1."""
    A, B = _tokens(a), _tokens(b)
    if not A or not B:
        return 0.0
    small, big = (A, B) if len(A) <= len(B) else (B, A)
    hit = sum(any(difflib.SequenceMatcher(None, t, u).ratio() >= 0.8 for u in big) for t in small)
    return hit / len(small)


def match_official(F: pd.DataFrame, G: pd.DataFrame) -> pd.DataFrame:
    """Attach the official game_key: same date (+-1 day) and the best home+away name match."""
    G = G.assign(d0=pd.to_datetime(G.date).dt.normalize())
    keys, scores = [], []
    for f in F.itertuples(index=False):
        d = f.start.tz_convert(None).normalize()
        cand = G[(G.d0 >= d - pd.Timedelta(days=1)) & (G.d0 <= d + pd.Timedelta(days=1))]
        best, bs = None, 0.0
        for g in cand.itertuples(index=False):
            s = min(name_sim(f.home_name, g.home_name), name_sim(f.away_name, g.away_name))
            if s > bs:
                best, bs = g.game_key, s
        keys.append(best if bs >= 0.5 else None)
        scores.append(bs)
    return F.assign(game_key=keys, match_score=scores)


def parse(games: pd.DataFrame | None = None):
    L = ladder()
    if L.empty:
        raise SystemExit("no cached odds yet; run `python -m data.oddspapi update` first")
    ML = main_lines(L)
    fx = L.groupby("fixture_id")[["tid", "start", "home_name", "away_name"]].first().reset_index()
    if games is not None:
        fx = match_official(fx, games)
    PROC.mkdir(parents=True, exist_ok=True)
    F = ML.merge(fx, on="fixture_id")
    L.to_parquet(PROC / "odds_euro_ladder.parquet", index=False)
    F.to_parquet(PROC / "odds_euro.parquet", index=False)
    return L, F


# ---------------------------------------------------------------- probe / plan
def probe() -> None:
    """Key check, the basketball totals catalogue, and whether finished EuroLeague games carry
    totals timelines in Nov 2024, Nov 2025 and the last ten days (at most 8 requests)."""
    M = markets()
    tot = M[(M.kind == "totals") & M.full_game]
    print(f"key OK; {M.market_id.nunique()} basketball markets, {tot.market_id.nunique()} full-game totals lines "
          f"(e.g. {sorted(tot.line.dropna().unique())[:3]} ...)")
    print("EuroCup tournament id:", tournament_id("eurocup"))
    keep = _keep_ids(M)
    now = pd.Timestamp.now(tz="UTC")
    recent = (now - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    for start in ("2024-11-01", "2025-11-01", recent):
        end = (pd.Timestamp(start) + pd.Timedelta(days=9)).strftime("%Y-%m-%d")
        fx = [f for f in fixtures(138, start, end) if _finished(f, now)]
        if not fx:
            print(f"  EuroLeague {start}: no finished fixtures listed")
            continue
        h = history(fx[0], 138, keep)
        n = {b: sum(len(o.get("players", {}).get("0") or []) for md in bd["markets"].values()
                    for oid, o in md["outcomes"].items() if int(oid) in set(tot.outcome_id))
             for b, bd in h["bookmakers"].items()}
        print(f"  EuroLeague {start}: {len(fx)} finished fixtures; totals price points per book on one game: {n}")
    print(f"requests used this month: {used()} of {budget()}")


def plan(first: str = FIRST_SEASON_START) -> None:
    """Requests still needed for the backfill, using official game counts (no API calls)."""
    from data.euroleague import parse as euro_parse
    codes = [f"{c}{y}" for c in ("E", "U") for y in range(int(first[:4]), pd.Timestamp.now().year + 1)]
    G, _ = euro_parse(codes)
    have = len(list(RAW.glob("*/hist/*.json")))
    lists = 2 * 9 * len(seasons_to_cover(first)) - len(list(RAW.glob("*/fixtures/*.json")))
    need = max(len(G) - have, 0) + max(lists, 0)
    print(f"games since {first}: {len(G)} (EuroLeague {int((G.competition == 'euroleague').sum())}, "
          f"EuroCup {int((G.competition == 'eurocup').sum())}); already cached: {have}")
    print(f"requests needed: ~{need} (incl. ~{max(lists, 0)} fixture lists); left this month: "
          f"{budget() - used()}; about {need / budget():.1f} months at {budget()}/month")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        probe()
    elif cmd == "plan":
        plan()
    elif cmd == "update":
        got = update()
        print(f"fetched {got}; requests used this month: {used()} of {budget()}")
    elif cmd == "parse":
        from data.euroleague import parse as euro_parse
        G, _ = euro_parse([f"{c}{y}" for c in ("E", "U") for y in range(2024, pd.Timestamp.now().year + 1)])
        L, F = parse(G)
        m = F.groupby("fixture_id").game_key.first().notna().mean()
        print(f"{F.fixture_id.nunique()} games, {F.book.nunique()} books, {m:.0%} matched to official games")
    else:
        raise SystemExit(__doc__)
