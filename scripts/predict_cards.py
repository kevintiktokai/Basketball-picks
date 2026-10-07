"""Live two-pick card — NCAA men's basketball, opening totals, buffered lines.

usage:
  python scripts/predict_cards.py --date 2026-11-20                 # auto: fetch slate from sportsbookreview.com
  python scripts/predict_cards.py --date 2026-11-20 --slate my.csv  # manual slate
        my.csv columns: home, away, line (opening total)[, home_spread, neutral]
  python scripts/predict_cards.py --date 2026-11-20 --update        # first refresh history (scrape + ESPN box)

What it prints:
  * the TWO-PICK CARD (or ONE QUALIFYING PICK / NO BET) chosen by the locked engine
  * for each leg: side, ALTERNATE line to bet, model probability, conservative
    probability, fair odds, and the minimum odds that keep the card +EV
  * the unbuffered main-line view for every screened game
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

BAR = "=" * 62
SUB = "-" * 62


def side_txt(s):
    return "OVER" if s == 1 else "UNDER"


def update_history(date: str):
    """Refresh current-season data: sportsbookreview.com odds (cached, polite) + ESPN box."""
    from data import sbr_live
    from models.live_ncaab import season_of
    D = pd.Timestamp(date)
    season = season_of(D)
    days = [d for d in sbr_live.season_dates(season) if pd.Timestamp(d) <= D]
    bid = sbr_live.build_id()
    import time
    for d in days:
        for market, tmpl in sbr_live.PATHS.items():
            out = sbr_live.RAW / market / f"{d.isoformat()}.json"
            if out.exists() and pd.Timestamp(d) < D - pd.Timedelta(days=1):
                continue                                      # finished days never change
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                out.write_bytes(sbr_live._get(f"https://www.sportsbookreview.com/_next/data/{bid}/"
                                              + tmpl.format(d=d.isoformat())))
            except Exception as e:                            # noqa: BLE001
                print(f"  fetch failed {market} {d}: {e}")
            time.sleep(1.0)
    sbr_live.parse()
    # current-season ESPN box scores + schedule (live, unpinned)
    import urllib.request
    from data.ncaab_ingest import RAW
    year = int(season[:4]) + 1
    for kind, path in (("team_box", f"mbb/team_box/parquet/team_box_{year}.parquet"),
                       ("mbb_schedule", f"mbb/schedules/parquet/mbb_schedule_{year}.parquet")):
        url = f"https://raw.githubusercontent.com/sportsdataverse/hoopR-mbb-data/main/{path}"
        try:
            urllib.request.urlretrieve(url, RAW / f"{kind}_{year}.parquet")
        except Exception as e:                                # noqa: BLE001
            print(f"  could not refresh {kind} {year}: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True)
    ap.add_argument("--slate")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if a.update:
        update_history(a.date)
    from models.live_ncaab import pending_from_sbr, run_card
    slate = None
    if a.slate:
        slate = pd.read_csv(a.slate)
        slate.columns = [c.strip().lower() for c in slate.columns]
        slate = slate.rename(columns={"home_spread": "home_spread_open"})
    elif a.date:
        from data import sbr_live
        if not (sbr_live.RAW / "totals" / f"{a.date}.json").exists():
            sys.exit("No cached slate for this date: run with --update (or pass --slate).")
    R = run_card(a.date, slate)
    if "error" in R:
        print(BAR + f"\nOVER/UNDER CARD ENGINE — NCAAB — {a.date}\n" + BAR)
        print(f"\nNO BET\n\nReason: {R['error']}\n")
        return
    lock, T, C, M, F = R["lock"], R["T"], R["card"], R["main"], R["frame"]
    cp = lock["card_policy"]
    unresolved = R["slate"][(R["slate"].match_home != "exact") | (R["slate"].match_away != "exact")]

    print(BAR)
    print(f"TWO-PICK CARD ENGINE — NCAA men's basketball — {a.date}")
    print(BAR)
    print(f"\nGames screened:\n{R['n_screened']}\n\nEligible (both teams >= 3 games this season):\n{R['n_eligible']}\n")
    print(f"Market:\nopening full-game totals (median across books)\n")
    print(f"Card rule:\nconservative joint probability >= {cp['joint_target']:.1%}, "
          f"alternate lines at most {cp['max_buffer_points']:.0f} pts from the market line\n")
    if len(unresolved):
        print("Team-name matches that were not exact (check these):")
        for _, r in unresolved.iterrows():
            print(f"  {r.away_name} -> {r.match_away} | {r.home_name} -> {r.match_home}")
        print()

    card = C[C.released == True] if len(C) else C  # noqa: E712
    if len(card):
        c = card.iloc[0]
        print(BAR + "\nTWO-PICK CARD (alternate lines)\n" + BAR)
        for leg in ("a", "b"):
            g = F[F.game_key == c[f"game_{leg}"]].iloc[0]
            p, pc, pm = c[f"p_{leg}"], c[f"pc_{leg}"], c[f"pm_{leg}"]
            print(f"\nPick {'1' if leg == 'a' else '2'}:\n{g.away_name} @ {g.home_name}"
                  if "away_name" in g else f"\nPick:\n{c[f'game_{leg}']}")
            print(f"\nMarket opening total:\n{g.line:.1f}")
            print(f"\nBET:\n{side_txt(c[f'side_{leg}'])} {c[f'thr_{leg}']:.1f}   "
                  f"(line moved {c[f'buf_{leg}']:.1f} pts in our favour)")
            print(f"\nProjected total:\n{g.line + g.mu:.1f}  (model SD {g.sd:.1f})")
            print(f"\nModel probability:\n{p:.1%}\n\nConservative probability:\n{pc:.1%}")
            print(f"\nFair odds (model):\n{1 / p:.3f}\n\nMarket-only fair odds at this line:\n{1 / pm:.3f}")
            print(SUB)
        jm, jc = c.joint_model, c.joint_cons
        print("\nJOINT ANALYSIS\n")
        print(f"Model joint probability (both win):\n{jm:.1%}\n\nConservative joint probability:\n{jc:.1%}")
        print(f"\nDependence:\nsame-day games measured independent (|corr| < 0.01); product used")
        print(f"\nBreak-even DOUBLE odds:\n{1 / jm:.3f}  -> only bet the double at {1 / jm:.2f} or better")
        print(f"Break-even per leg (as singles):\nleg 1 {1 / c.p_a:.3f}, leg 2 {1 / c.p_b:.3f}")
        print("\nTrack record of this exact engine (locked, out-of-sample):")
        print("  development 2011-18: 572/870 cards 2/2 (65.7%)")
        print("  holdout 2018-21:     221/363 cards 2/2 (60.9%, 95% CI 55.8-65.8%)")
        print(f"\nFINAL:\nTAKE BOTH — ONLY IF your book offers these alternate lines at or above the break-even odds\n{BAR}")
    else:
        print(BAR + "\nNO TWO-PICK CARD\n" + BAR)
        print("\nNo pair of legs reaches the conservative joint target within the 15-point alternate-line cap.\n")

    print("\nMain-line view (no buffer), all screened games:")
    show = M.sort_values("p_best", ascending=False)
    for _, r in show.iterrows():
        name = f"{r.get('away_name', r.away)} @ {r.get('home_name', r.home)}"
        print(f"  {name[:48]:48s} open {r.line:6.1f}  proj {r.line + r.mu:6.1f}  "
              f"{side_txt(r.best_side):5s} {r.p_best:5.1%}  (cons {r.p_best_cons:5.1%})")


if __name__ == "__main__":
    main()
