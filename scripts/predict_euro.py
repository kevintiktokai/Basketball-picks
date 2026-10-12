"""Live European picks: EuroLeague totals priced against Pinnacle.

From one live odds snapshot (The Odds API: Pinnacle + 1xBet, Betway, Unibet), every soft-book
price is valued against Pinnacle's no-vig price, and the European ratings model is asked whether
it agrees. Two products:

  2.5+ CARD   the LOCKED European strategy (config/europe_locked.yaml), unchanged: legs at odds
              1.70-2.10, at least 1% above Pinnacle's fair price, model agrees, the best leg per
              game, the pair with the highest joint value and combined odds >= 2.5, one card a day.
  SINGLES     every game's best soft-book price at least 2% above Pinnacle's fair price
              (test phase: in development such prices beat Pinnacle's close, +2-5% CLV).

The European edge has development evidence only (2025-26: 144 games, 9 locked cards); its
holdout has not run. Stakes default to 0.5% of the bankroll per bet until the forward record
says more. Value fades fast: about half of it is gone 30-60 minutes after Pinnacle moves, so
place the bets right after running this.

usage: python scripts/predict_euro.py --update [--bankroll 10000] [--record]
       python scripts/predict_euro.py --snapshot PATH        (re-run on a saved snapshot)
Needs THE_ODDS_API_KEY in the environment for --update (2 credits of 500 a month per run).
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml

from backtest.euro_cards import SOFT, TZ, cards, legs
from data import oddsapi
from features.euro_market import fair_curve, fair_p

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "reports" / "live_ledger_euro.csv"
GAMES_LOG = ROOT / "reports" / "euro_live_games.csv"
SINGLE_EV_MIN = 0.02
STAKE = 0.005


def locked_cfg() -> dict:
    s = yaml.safe_load((ROOT / "config" / "europe_locked.yaml").read_text())["strategy"]
    return {"leg_ev_min": s["leg_ev_min"], "leg_odds_band": tuple(s["leg_odds_band"]), "books": s["books"],
            "model_agrees": s["model_agrees"], "cards_per_date": str(s["cards_per_date"])}


def picks(B: pd.DataFrame, model: pd.Series, cfg: dict, single_ev_min: float = SINGLE_EV_MIN):
    """B: board rows (data.oddsapi.board); model: fixture_id -> expected total, already centred on the
    model's long-run bias. Returns (legs, card, singles, curve). Each Madrid date is valued on its own,
    so the locked code's centring on earlier dates adds nothing to the long-run centring."""
    snap = B.t.max()
    curve = fair_curve(B, whole_lines=True)
    parts = []
    for _, Bd in B.groupby(B.start.dt.tz_convert(TZ).dt.date):
        when = pd.Series(snap + pd.Timedelta(milliseconds=1), index=Bd.fixture_id.unique())
        CC = fair_curve(Bd, whole_lines=True)
        if CC.empty:
            continue
        parts.append(legs(Bd, when, CC, None, model, whole_lines=True))
    L = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if L.empty:
        return L, pd.DataFrame(), pd.DataFrame(), curve
    L["clv"] = np.nan                                            # no close yet
    C = cards(L, cfg)
    S = L[L.book.isin(SOFT) & (L.ev_now >= single_ev_min)]
    S = S.sort_values("ev_now").groupby("fixture_id").tail(1).sort_values("ev_now", ascending=False)
    return L, C, S, curve


def leg_row(L: pd.DataFrame, fixture_id, leg: str) -> pd.Series:
    """The leg row behind a card's leg text ('book side line @price', as backtest.euro_cards.cards writes it)."""
    x = L[L.fixture_id == fixture_id]
    txt = x.book + " " + x.side + " " + x.line.astype(str) + " @" + x.price.map(lambda v: f"{v:.2f}")
    return x[txt == leg].iloc[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true", help="take a new odds snapshot (2 credits)")
    ap.add_argument("--snapshot", help="use this saved snapshot instead of the latest one")
    ap.add_argument("--hours", type=float, default=40, help="games starting within this many hours")
    ap.add_argument("--bankroll", type=float, help="print stakes for this bankroll")
    ap.add_argument("--stake", type=float, default=STAKE, help="share of the bankroll per bet (default 0.5%%)")
    ap.add_argument("--record", action="store_true", help="append the picks to reports/live_ledger_euro.csv")
    a = ap.parse_args()

    from models import live_euro as LE
    path = Path(a.snapshot) if a.snapshot else None
    if a.update:
        try:
            path = oddsapi.fetch()
        except oddsapi.NoKey:
            sys.exit("No odds key in this session. Add THE_ODDS_API_KEY to the environment's settings "
                     "(free key at the-odds-api.com) and start a new session.")
        print(f"snapshot {path.name}; credits left this month: {oddsapi.usage().get('remaining')}")
    path = path or oddsapi.latest_snapshot()
    if path is None:
        sys.exit("No odds snapshot yet: run with --update (needs THE_ODDS_API_KEY).")

    now = pd.Timestamp.now(tz="UTC")
    B = oddsapi.board(path)
    B = B[(B.start > now) & (B.start <= now + pd.Timedelta(hours=a.hours))]
    if B.empty:
        sys.exit(f"No EuroLeague totals in {path.name} for games in the next {a.hours:.0f} hours.")
    up = LE.upcoming(days=a.hours / 24 + 1)
    ev = B.groupby("fixture_id")[["start", "home_name", "away_name"]].first().reset_index()
    ev = LE.match(ev, up)
    mt = LE.model_totals(up)
    bias = LE.model_bias()["mean"]
    model = ev.set_index("fixture_id").game_key.map(mt) - bias
    L, C, S, curve = picks(B, model, locked_cfg())

    age = (now - B.t.max()).total_seconds() / 60
    print(f"\nEuroLeague totals, snapshot {B.t.max():%Y-%m-%d %H:%M} UTC ({age:.0f} min old). "
          f"Model centred by {bias:+.1f} pts (its average gap to Pinnacle).\n")
    cv = curve.set_index("fixture_id")
    games = []
    for e in ev.sort_values("start").itertuples(index=False):
        tip = e.start.tz_convert(TZ)
        pin = cv.loc[e.fixture_id] if e.fixture_id in cv.index else None
        line = f"{pin.pin_main:g}" if pin is not None else "—"
        fair = f"{pin.fair_mu:.1f}" if pin is not None else "—"
        m = model.get(e.fixture_id, np.nan)
        flag = "" if e.game_key else "  (no official match: model skipped)"
        print(f"{tip:%a %d %b %H:%M} Madrid  {e.home_name} v {e.away_name}{flag}")
        print(f"    Pinnacle line {line}, fair total {fair}; model {m:.1f}" if np.isfinite(m) else
              f"    Pinnacle line {line}, fair total {fair}; model —")
        g = B[(B.fixture_id == e.fixture_id) & B.book.isin(SOFT)]
        for side in ("over", "under"):
            x = g[g.side == side]
            if len(x) and pin is not None:
                x = x.assign(evx=fair_p(curve, x.fixture_id, x.line, x.side) * x.price - 1).sort_values("evx")
                b = x.iloc[-1]
                print(f"    best {side:5s}: {b.book} {b.line:g} @ {b.price:.2f} (value {b.evx:+.1%})")
        games.append({"snapshot": path.name, "fixture_id": e.fixture_id, "game_key": e.game_key, "start": e.start,
                      "home": e.home_name, "away": e.away_name, "pin_main": pin.pin_main if pin is not None else np.nan,
                      "fair_mu": pin.fair_mu if pin is not None else np.nan, "model": mt.get(e.game_key, np.nan)})

    stake = f" stake ${a.bankroll * a.stake:,.0f}" if a.bankroll else f" stake {a.stake:.1%} of bankroll"
    name = ev.set_index("fixture_id")
    leg_txt = lambda r: (f"{name.at[r.fixture_id, 'home_name']} v {name.at[r.fixture_id, 'away_name']}: "   # noqa: E731
                         f"{r.side.upper()} {r.line:g} at {r.book} @ {r.price:.2f}")
    print("\n2.5+ CARD (locked European strategy)")
    if C.empty:
        print("    no card: fewer than two legs meet the locked rules right now")
    for c in C.itertuples(index=False):
        A, Bl = leg_row(L, c.game_a, c.leg_a), leg_row(L, c.game_b, c.leg_b)
        print(f"    leg 1: {leg_txt(A)}  (value {A.ev_now:+.1%})")
        print(f"    leg 2: {leg_txt(Bl)}  (value {Bl.ev_now:+.1%})")
        print(f"    combined odds {c.odds:.2f}, value {c.ev:+.1%};{stake}")
    print(f"\nSINGLES (best price at least {SINGLE_EV_MIN:.0%} above Pinnacle's fair price; test phase)")
    if S.empty:
        print("    none right now")
    for r in S.itertuples(index=False):
        agree = "model agrees" if r.model_agrees else "model does not agree"
        print(f"    {leg_txt(r)}  value {r.ev_now:+.1%}, {agree};{stake}")

    live = path.resolve().parent == oddsapi.SNAP.resolve()          # only real snapshots are logged
    if not live:
        if a.record:
            print("\nnot recorded: --record only logs snapshots taken with --update")
        return
    GAMES_LOG.parent.mkdir(parents=True, exist_ok=True)
    gl = pd.DataFrame(games)
    if GAMES_LOG.exists():
        old = pd.read_csv(GAMES_LOG)
        gl = gl[~gl.set_index(["snapshot", "fixture_id"]).index.isin(old.set_index(["snapshot", "fixture_id"]).index)]
    if len(gl):
        gl.to_csv(GAMES_LOG, mode="a", header=not GAMES_LOG.exists(), index=False)
    if a.record:
        recs = []
        run = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M")
        for kind, frame in (("single", S), ("card", None)):
            if kind == "single":
                for r in frame.itertuples(index=False):
                    recs.append({"run_utc": run, "snapshot": path.name, "kind": "single", "card": "",
                                 "fixture_id": r.fixture_id, "game_key": name.at[r.fixture_id, "game_key"], "start": r.start, "book": r.book,
                                 "side": r.side, "line": r.line, "price": r.price, "fair_p": r.p_now, "ev": r.ev_now,
                                 "model_agrees": bool(r.model_agrees), "stake_frac": a.stake})
            else:
                for i, c in enumerate(C.itertuples(index=False)):
                    for leg, gid in ((c.leg_a, c.game_a), (c.leg_b, c.game_b)):
                        r = leg_row(L, gid, leg)
                        recs.append({"run_utc": run, "snapshot": path.name, "kind": "card",
                                     "card": f"{c.date}-{i + 1} @{c.odds:.2f}", "fixture_id": gid,
                                     "game_key": name.at[gid, "game_key"],
                                     "start": r.start, "book": r.book, "side": r.side, "line": r.line, "price": r.price,
                                     "fair_p": r.p_now, "ev": r.ev_now, "model_agrees": bool(r.model_agrees),
                                     "stake_frac": a.stake})
        if recs:
            pd.DataFrame(recs).to_csv(LEDGER, mode="a", header=not LEDGER.exists(), index=False)
            print(f"\nrecorded {len(recs)} picks to {LEDGER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
