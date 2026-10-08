"""Stage 3 — ONE-TIME WNBA test (2023, 2024, 2025, 2026) of the locked WNBA opener engine and the
locked odds-card products, exactly as the NBA test (scripts/stage3_nba_test.py). Refuses to run
twice.
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
from backtest.wf2 import main_line_probs, walk_forward_market
from calibration.calibrate import log_loss, wilson
from config_loader import ROOT, log_experiment
from stage3_common import evaluate, locked
from stage3_wnba_dev import wnba_market

REPORT = ROOT / "reports" / "stage3_wnba_test.md"


def main():
    if REPORT.exists():
        sys.exit(f"REFUSING: {REPORT} exists — the WNBA test is evaluated once only.")
    s3 = yaml.safe_load((ROOT / "config" / "stage3.yaml").read_text())["wnba"]
    lock_w = yaml.safe_load((ROOT / "config" / "stage3_wnba_locked.yaml").read_text())
    TEST = s3["test"]
    d, rep = wnba_market()
    spec = lock_w["model"]
    P, cals, calm = walk_forward_market(d, spec["mean_feats"], spec["var_feats"], spec["kind"], spec["shape"],
                                        spec["alpha"], seasons=sorted(d.season.unique()), min_games=spec["min_games"],
                                        train_decay=spec["train_decay"], calib_decay=spec["calib_decay"])
    books = d.set_index("game_key").books_json
    R, cards = evaluate(P, cals, calm, books, TEST)
    out = ["# Stage 3 — WNBA one-time test (2023-2026), opening lines, real prices\n",
           f"Engine: `{lock_w['variant']}` (locked in `config/stage3_wnba_locked.yaml`, revision "
           f"`{lock_w['locked_at_revision']}`); products: `config/stage3_locked.yaml` (revision "
           f"`{locked()['locked_at_revision']}`), the same as NCAAB and NBA. Data: {rep['games']} games.\n",
           "## Odds-targeted two-pick cards\n", df_to_md(R), ""]

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
        Cn.to_csv(ROOT / "reports" / f"stage3_wnba_cards_{tag}.csv", index=False)
    print("\n".join(out))
    log_experiment("stage3_wnba_test", {"lock_wnba": lock_w, "lock": locked()},
                   {"pooled": R[R.season == "POOLED"].astype(str).to_dict("records")})


if __name__ == "__main__":
    main()
