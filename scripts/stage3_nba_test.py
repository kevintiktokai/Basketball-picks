"""Stage 3 — ONE-TIME NBA test (2023-24, 2024-25, 2025-26) of the locked NBA opener engine
and the locked odds-card products. Refuses to run twice.
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
import yaml

from backtest.analysis import df_to_md
from backtest.odds_cards import best_main
from backtest.wf2 import main_line_probs
from calibration.calibrate import log_loss, wilson
from config_loader import ROOT, log_experiment
from features.store import cached_walk_forward, fingerprint
from stage3_common import evaluate, locked
from stage3_nba_dev import RO, nba_market

REPORT = ROOT / "reports" / "stage3_nba_test.md"


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT} exists — the NBA test is evaluated once only.")
    s3 = yaml.safe_load((ROOT / "config" / "stage3.yaml").read_text())["nba"]
    lock_nba = yaml.safe_load((ROOT / "config" / "stage3_nba_locked.yaml").read_text())
    TEST = s3["test"]
    d = nba_market()
    seasons = sorted(d.season.unique())
    spec = lock_nba["model"]
    P, cals, calm = cached_walk_forward(d, spec, seasons, f"nba-{len(d)}-{d.total.sum():.0f}")
    books = d.set_index("game_key").books_json
    R, cards = evaluate(P, cals, calm, books, TEST)
    out = ["# Stage 3 — NBA one-time test (2023-24..2025-26), opening lines, real prices\n",
           f"Engine: `{lock_nba['variant']}` (locked in `config/stage3_nba_locked.yaml`); products: "
           f"`config/stage3_locked.yaml` (revision `{locked()['locked_at_revision']}`).\n",
           "## Odds-targeted two-pick cards\n", df_to_md(R), ""]

    # main-line singles at REAL best-book opening prices
    M = main_line_probs(P, cals)
    Mm = main_line_probs(P.assign(mu=P.mu_mkt, sd=P.sd_mkt), calm)
    e = M[M.season.isin(TEST) & M.eligible & ~M.push].copy()
    em = Mm.set_index("game_key").loc[e.game_key]
    out.append(f"Main-line log loss model {log_loss(e.p_over / (e.p_over + e.p_under), e.over):.5f} vs "
               f"market-only {log_loss(em.p_over / (em.p_over + em.p_under), e.over):.5f} over {len(e)} games.\n")
    rows = []
    bj = books.reindex(e.game_key).values
    for lo, hi in ((0.5, 0.53), (0.53, 0.55), (0.55, 0.58), (0.58, 1.01)):
        m = (e.p_best >= lo).values & (e.p_best < hi).values
        prof, wins, n = [], 0, 0
        for i in np.where(m)[0]:
            r = e.iloc[i]
            line, price, _ = best_main(bj[i], int(r.best_side))
            if np.isnan(line):
                line, price = r.line, 1.909
            win = r.outcome > line if r.best_side == 1 else r.outcome < line
            push = r.outcome == line
            prof.append(0.0 if push else (price - 1 if win else -1.0))
            wins += int(win)
            n += int(not push)
        rows.append({"two-sided P": f"{lo:.0%}-{min(hi, 1):.0%}", "bets": int(m.sum()),
                     "win_rate_best_book": wins / n if n else np.nan, "ci95": wilson(wins, n),
                     "roi_best_book_real_price": float(np.mean(prof)) if prof else np.nan})
    out += ["## Single bets at the best book's opening number and real price\n", df_to_md(pd.DataFrame(rows)), ""]

    # closing-line value of the target-card legs
    C = cards[list(cards)[0]]
    Fi = P.set_index("game_key")
    if len(C):
        mv = np.concatenate([C[f"side_{l}"].values * (Fi.loc[C[f"game_{l}"]].line_close.values
                                                        - Fi.loc[C[f"game_{l}"]].line_open.values) for l in ("a", "b")])
        out.append(f"Target-card legs: open→close move in our direction {np.nanmean(mv):+.2f} pts; "
                   f"moved our way {np.nanmean(mv > 0):.1%}, against {np.nanmean(mv < 0):.1%}.\n")
    REPORT.write_text("\n".join(out) + "\n")
    for name, Cn in cards.items():
        tag = name.strip().split(" ")[0].lower().replace(":", "")
        Cn.to_csv(ROOT / "reports" / f"stage3_nba_cards_{tag}.csv", index=False)
    print("\n".join(out))
    log_experiment("stage3_nba_test", {"lock_nba": lock_nba, "lock": locked()},
                   {"pooled": R[R.season == "POOLED"].to_dict("records")})


if __name__ == "__main__":
    main()
