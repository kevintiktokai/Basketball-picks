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


TRACK = {
    "target": ["NCAAB development 2018-21: 46.3% of cards won at avg 2.55 (ROI +17%)",
               "NCAAB 2021-26 re-analysis: 47.0% won at avg 2.58 (ROI +21%; +10% if alternates priced off the close)"],
    "main": ["NCAAB 2021-26 re-analysis: 38.3% won at avg 3.64, real prices (ROI +39%)"],
}


def print_odds_card(R, a):
    from backtest.odds_cards import best_main
    C = R["target_card"] if a.product == "target" else R["main_double"]
    F = R["legs"].frame.set_index("game_key")
    title = ("TARGET CARD — combined odds >= 2.5, highest chance both win" if a.product == "target"
             else "MAIN-LINE DOUBLE — opening numbers at real prices")
    print(BAR + f"\n{title}\nNCAA men's basketball — {a.date} — engine {a.engine}\n" + BAR)
    print(f"\nGames screened: {R['n_screened']}   eligible: {R['n_eligible']}")
    if C.empty:
        print("\nNO CARD\n\nReason: no pair reaches combined odds >= 2.5 with a positive conservative "
              "expected value.\n" + BAR)
        return
    c = C.iloc[0]
    for i, leg in enumerate(("a", "b"), 1):
        g = F.loc[c[f"game_{leg}"]]
        side = int(c[f"side_{leg}"])
        line = c[f"thr_{leg}"]
        name = f"{g.get('away_name', g.away)} @ {g.get('home_name', g.home)}"
        moved = side * (g.line - line)
        print(f"\nPick {i}: {name}")
        print(f"  BET:   {side_txt(side)} {line:.1f}   (market opener {g.line:.1f}; "
              f"{moved:+.1f} pts in our favour)")
        if c[f"main_{leg}"]:
            bl, bp, book = best_main(g.get("books_json"), side)
            src = f"real price at {book}" if book else "assumed -110"
            print(f"  Price: {c[f'odds_{leg}']:.2f}   ({src})")
        else:
            print(f"  Price: ~{c[f'odds_{leg}']:.2f}   (alternate line: estimated book price — check yours)")
        p, pc = c[f"p_{leg}"], c[f"pc_{leg}"]
        other = c["odds_b"] if leg == "a" else c["odds_a"]
        p_other = c["p_b"] if leg == "a" else c["p_a"]
        print(f"  Model probability: {p:.1%}  (conservative {pc:.1%})   fair odds {1 / p:.2f}")
        print(f"  Minimum price for this leg (card stays +EV with the other leg at {other:.2f}): "
              f"{1 / (p * p_other * other):.2f}")
    print("\n" + SUB)
    print(f"Combined odds:            {c.combined_odds:.2f}")
    print(f"Chance both win (model):  {c.joint_model:.1%}   (conservative {c.joint_cons:.1%})")
    print(f"Break-even at these odds: {1 / c.combined_odds:.1%}")
    print(f"Expected return per unit: {c.ev_model:+.1%}   (conservative {c.ev_cons:+.1%})")
    print("\nTrack record of this locked product:")
    for t in TRACK[a.product]:
        print("  " + t)
    print("\nExpect to LOSE more cards than you win: at ~2.5 the edge is winning ~47% when 40% breaks even.")
    print(f"\nFINAL: TAKE BOTH — only at or above the minimum prices, and as close to the opening line as possible.\n{BAR}")
    if a.record:
        rec = {"date": a.date, "engine": a.engine, "product": a.product,
               "recorded_at": pd.Timestamp.utcnow().isoformat()}
        for leg in ("a", "b"):
            g = F.loc[c[f"game_{leg}"]]
            rec.update({f"{leg}_away": g.get("away_name", g.away), f"{leg}_home": g.get("home_name", g.home),
                        f"{leg}_side": side_txt(int(c[f"side_{leg}"])), f"{leg}_line": c[f"thr_{leg}"],
                        f"{leg}_odds": c[f"odds_{leg}"], f"{leg}_p": c[f"p_{leg}"], f"{leg}_p_cons": c[f"pc_{leg}"]})
        rec.update({"combined_odds": c.combined_odds, "joint_model": c.joint_model})
        ledger = Path(__file__).resolve().parents[1] / "reports" / "live_ledger.csv"
        pd.DataFrame([rec]).to_csv(ledger, mode="a", header=not ledger.exists(), index=False)
        print(f"recorded to {ledger}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True)
    ap.add_argument("--slate")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--record", action="store_true",
                    help="append the released card to reports/live_ledger.csv for forward testing")
    ap.add_argument("--product", choices=["target", "main", "sixty"], default="target",
                    help="target: combined >=2.5, legs ~1.6, highest win chance (default); "
                         "main: main-line double at real prices; sixty: stage-2 60%% buffered card")
    ap.add_argument("--engine", choices=["v3", "v2"], default="v3",
                    help="v3 (default, recency-adapted, J=0.65) or v2 (stage-2 locked, J=0.625)")
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
    R = run_card(a.date, slate, engine=a.engine)
    if "error" in R:
        print(BAR + f"\nOVER/UNDER CARD ENGINE — NCAAB — {a.date}\n" + BAR)
        print(f"\nNO BET\n\nReason: {R['error']}\n")
        return
    lock, T, C, M, F = R["lock"], R["T"], R["card"], R["main"], R["frame"]
    if a.product in ("target", "main"):
        print_odds_card(R, a)
        return
    cp = lock["card_policy"]
    unresolved = R["slate"][(R["slate"].match_home != "exact") | (R["slate"].match_away != "exact")]

    print(BAR)
    print(f"TWO-PICK CARD ENGINE ({a.engine}) — NCAA men's basketball — {a.date}")
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
        print("\nTrack record (locked engines, never-seen seasons; see reports/STAGE2_SUMMARY.md):")
        if a.engine == "v2":
            print("  holdout 2018-21:          221/363 cards 2/2 (60.9%, 95% CI 55.8-65.8%)")
            print("  independent test 2021-26: 424/664 cards 2/2 (63.9%, 95% CI 60.1-67.4%)")
        else:
            print("  independent test 2021-26: 428/664 cards 2/2 (64.5%, 95% CI 60.7-68.0%)")
            print("  (v3 was developed on 2007-21, so 2021-26 is its only out-of-sample record)")
        print(f"\nFINAL:\nTAKE BOTH — ONLY IF your book offers these alternate lines at or above the break-even odds\n{BAR}")
        if a.record:
            rec = {"date": a.date, "engine": a.engine, "recorded_at": pd.Timestamp.utcnow().isoformat()}
            for leg in ("a", "b"):
                g = F[F.game_key == c[f"game_{leg}"]].iloc[0]
                rec.update({f"{leg}_away": g.get("away_name", g.away), f"{leg}_home": g.get("home_name", g.home),
                            f"{leg}_side": side_txt(c[f"side_{leg}"]), f"{leg}_line": c[f"thr_{leg}"],
                            f"{leg}_market_open": g.line, f"{leg}_p": c[f"p_{leg}"], f"{leg}_p_cons": c[f"pc_{leg}"]})
            rec["joint_model"] = c.joint_model
            ledger = Path(__file__).resolve().parents[1] / "reports" / "live_ledger.csv"
            pd.DataFrame([rec]).to_csv(ledger, mode="a", header=not ledger.exists(), index=False)
            print(f"recorded to {ledger}")
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
