"""Prediction CLI — the live OVER ENGINE.

Usage:
  python scripts/predict.py --slate slate.csv [--date 2026-01-08] [--time 19:00]
        [--bookmaker fanduel] [--history recent_results.csv]

slate.csv columns: home, away, line, over_odds (decimal; default 1.909),
                   optional date, home_spread (+ = home favoured), league
recent_results.csv (optional, to bring team states up to date):
                   date, home, away, line, home_pts, away_pts[, home_spread]

Only NBA is supported: it is the only league with historical totals data in
this project. Rows with another `league` value are rejected.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np

from backtest.dependence import joint_probability
from models.live import load_slate, max_playable_line, predict_slate

BAR = "=" * 50
SUB = "-" * 50
REASON_TEXT = {
    "x_rating": "opponent-adjusted scoring ratings (offence vs defence matchup)",
    "x_naive": "recent raw scoring form",
    "rest_sum": "rest days",
    "b2b_any": "back-to-back fatigue",
    "abs_spread": "expected competitiveness (spread size)",
    "line_tend_sum": "market's season-long view of these teams",
    "lg_total_minus_line": "league-wide scoring drift vs lines",
    "line_rel": "line level vs league",
    "early_season": "early-season uncertainty",
    "postseason": "postseason environment",
    "log_games": "sample size this season",
    "ou_trend_sum": "recent Over/Under results of both teams",
}


def label(r):
    return f"{r.away} @ {r.home}"


def pick_detail(r, sp, cal, cons, fm, partner=None):
    lo, hi = r.proj_total - 1.2816 * r.sd, r.proj_total + 1.2816 * r.sd
    conf = "HIGH" if r.p_cons >= 0.55 else "MEDIUM" if r.p_cal >= 0.55 else "LOW"
    mpl_single = max_playable_line(r, sp, cal, cons, fm)
    print(f"Candidate:\n{label(r)}\n")
    print(f"Bookmaker line:\n{r.line:.1f}\n\nOver odds:\n{r.odds:.2f}\n")
    print(f"Projected total:\n{r.proj_total:.1f}\n\nModel range (80%):\n{lo:.1f} – {hi:.1f}\n")
    print(f"P(Over) raw:\n{r.p_raw:.1%}\n\nCalibrated probability:\n{r.p_cal:.1%}\n")
    print(f"Conservative probability:\n{r.p_cons:.1%}\n")
    print(f"Model edge:\n{r.proj_total - r.line:+.1f} points\n")
    print(f"Individual expected value:\n{(r.p_cal * r.odds - 1):+.1%}\n\nConfidence:\n{conf}\n")
    if partner is not None:
        mpl = max_playable_line(r, sp, cal, cons, fm, partner)
        print(f"Maximum playable line (card, with partner):\n{mpl if mpl is not None else 'none'}\n")
    print(f"Maximum playable line (standalone single):\n{mpl_single if mpl_single is not None else 'none'}\n")
    contrib = sorted(((k[2:], v) for k, v in r.items() if k.startswith("c_")), key=lambda t: -abs(t[1]))
    print("Reason (largest model contributions, points vs a typical game):")
    for f, v in contrib[:4]:
        print(f"- {REASON_TEXT.get(f, f)}: {v:+.1f}")
    print("\nRisks:")
    if abs(r.home_spread) >= 10 if not np.isnan(r.home_spread) else False:
        print(f"- blowout risk: spread {r.home_spread:+.1f}")
    if r.min_games_season < 10:
        print("- early season: fewer than 10 games of data for one team")
    from scipy.stats import norm
    p_low = norm.cdf((r.line - 15 - r.proj_total) / r.sd)
    print(f"- finishing 15+ points under the line (<= {r.line - 15:.0f}): {p_low:.0%} "
          f"(model SD {r.sd:.1f} pts)")
    print("- roster/injury information is NOT modelled (no data feed)")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slate", required=True)
    ap.add_argument("--date")
    ap.add_argument("--time", default="")
    ap.add_argument("--bookmaker", default="unspecified")
    ap.add_argument("--leagues", default="NBA")
    ap.add_argument("--history")
    a = ap.parse_args()
    if a.leagues.upper() != "NBA":
        sys.exit("Only NBA is supported: no historical totals data exists here for other leagues.")
    slate = load_slate(a.slate, a.date)
    if "league" in slate and (slate.league.str.upper() != "NBA").any():
        sys.exit("Non-NBA rows in slate: unsupported (no validated model).")
    cur, dec, sp, cal, cons, fm = predict_slate(slate, a.history)
    date = slate.date.min().date()

    print(BAR)
    print(f"OVER ENGINE — {date} {a.time}  (bookmaker: {a.bookmaker})")
    print(BAR)
    print(f"\nGames screened:\n{dec.n_games}\n\nEligible individual candidates:\n{dec.n_candidates}\n")
    print(f"Pairs evaluated:\n{dec.n_pairs}\n\nPairs with conservative joint probability >= 60%:\n"
          f"{dec.n_qualifying_pairs}\n\nOutcome:\n{dec.outcome}\n")

    by_id = cur.set_index("game_id")
    if dec.outcome == "TWO-PICK CARD":
        a_, b_ = [by_id.loc[p.game_id] for p in dec.picks]
        for r, partner in ((a_, b_), (b_, a_)):
            print(SUB)
            pick_detail(r, sp, cal, cons, fm, partner)
        print(BAR + "\nTWO-PICK OVER CARD\n" + BAR)
        for i, r in enumerate((a_, b_), 1):
            print(f"\nPick {i}:\n{label(r)}\n\nOver:\n{r.line:.1f}\n\nOdds:\n{r.odds:.2f}\n")
            print(f"Individual calibrated probability:\n{r.p_cal:.0%}\n\nProjected total:\n{r.proj_total:.1f}\n")
            print(SUB)
        print("\nJOINT ANALYSIS\n")
        print(f"Estimated P(Pick 1 wins):\n{a_.p_cal:.0%}\n\nEstimated P(Pick 2 wins):\n{b_.p_cal:.0%}\n")
        print(f"Naive independent probability:\n{dec.joint_indep:.1%}\n")
        print(f"Model-estimated joint probability:\n{dec.joint_cal:.1%}\n")
        print(f"Conservative joint probability:\n{dec.joint_cons:.1%}\n")
        print(f"Estimated dependence (rho):\n{sp.rho_hat:+.3f} (lower bound {sp.rho_lo:+.3f}); "
              f"joint − independent product = {dec.joint_cal - dec.joint_indep:+.2%}\n")
        print("Historical 2/2 rate for comparable cards:\n"
              "NONE — the engine has never released a card in 2,896 historical slates\n")
        print(f"Combined odds (as a double):\n{a_.odds * b_.odds:.2f}\n")
        ev_s = 0.5 * ((a_.p_cal * a_.odds - 1) + (b_.p_cal * b_.odds - 1))
        print(f"Card EV as two singles:\n{ev_s:+.1%}\n\nCard EV as a double:\n"
              f"{dec.joint_cons * a_.odds * b_.odds - 1:+.1%} (conservative joint)\n")
        print("Confidence:\nQUALIFIES\n\nFINAL:\nTAKE BOTH OVERS\n" + BAR)
    elif dec.outcome == "ONE QUALIFYING PICK":
        print(BAR + "\nONE QUALIFYING PICK\n" + BAR)
        pick_detail(by_id.loc[dec.picks[0].game_id], sp, cal, cons, fm)
        print("Note:\nNo statistically defensible second selection.\n")
        _closest(dec, by_id)
        print(BAR)
    else:
        print(BAR + "\nNO BET\n" + BAR)
        print("\nReason:\nNo pair reaches a conservative joint probability of 60%, and no single\n"
              "candidate meets the validated single-pick standard.\n")
        _closest(dec, by_id)
        print(BAR)

    print("\nAll games screened:")
    for _, r in cur.sort_values("p_cal", ascending=False).iterrows():
        print(f"  {label(r):12s} line {r.line:6.1f}  proj {r.proj_total:6.1f}  "
              f"P(cal) {r.p_cal:5.1%}  P(cons) {r.p_cons:5.1%}  EV {r.p_cal * r.odds - 1:+.1%}")


def _closest(dec, by_id):
    br = dec.best_rejected
    if br:
        a, b = by_id.loc[br["a"]], by_id.loc[br["b"]]
        print(f"Closest candidate pair:\n{label(a)} + {label(b)} — conservative joint "
              f"{br['joint_cons']:.1%} (calibrated joint {br['joint_cal']:.1%})\n")


if __name__ == "__main__":
    main()
