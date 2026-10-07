"""STAGE 2b — one-time independent test of the locked engines on NCAAB 2021-22..2025-26
(odds from sportsbookreview.com: several US books, opening + closing totals, real prices).

Primary:   v2  (config/stage2_locked.yaml)
Secondary: v3  (config/stage3_v3_locked.yaml)
Refuses to run if the report exists.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml

from backtest.analysis import df_to_md
from backtest.wf2 import buffered_cards, card_summary, leg_table, main_line_probs, walk_forward_market
from calibration.calibrate import log_loss, wilson
from config_loader import ROOT, log_experiment
from features.ncaab_features import build_ncaab_features, market_frame

REPORT = ROOT / "reports" / "stage2b_independent_test.md"
OUT = []


def h(s=""):
    OUT.append(s)
    print(s, flush=True)


def american_to_decimal(a):
    a = pd.to_numeric(a, errors="coerce")
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def best_open_for_side(books_json: str, side: int):
    """Best opening number and its price for a side across books: lowest total for an
    Over, highest total for an Under. Returns (line, decimal_odds, book)."""
    try:
        books = json.loads(books_json)
    except Exception:  # noqa: BLE001
        return np.nan, np.nan, None
    best = None
    for name, b in books.items():
        line = b.get("open")
        price = b.get("open_over") if side == 1 else b.get("open_under")
        if line is None or price is None:
            continue
        dec = float(american_to_decimal(price))
        key = (-line if side == 1 else line, dec)          # better line first, then better price
        if best is None or key > best[0]:
            best = (key, line, dec, name)
    if best is None:
        return np.nan, np.nan, None
    return best[1], best[2], best[3]


def median_open_price(books_json: str, side: int, line: float):
    """Median decimal price for the side among books whose opener equals the median line."""
    try:
        books = json.loads(books_json)
    except Exception:  # noqa: BLE001
        return np.nan
    ps = [b.get("open_over") if side == 1 else b.get("open_under") for b in books.values()
          if b.get("open") == line]
    ps = [p for p in ps if p is not None]
    return float(np.median(american_to_decimal(ps))) if ps else np.nan


def evaluate_engine(name, d, seasons, test_seasons, lock_model, policy, decays, F_extra):
    m = lock_model
    P, cals, calm = walk_forward_market(d, m["mean_feats"], m["var_feats"], m["kind"], m["shape"],
                                        m["alpha"], seasons=seasons, min_games=m["min_games"],
                                        train_decay=decays[0], calib_decay=decays[1])
    T = leg_table(P, cals, calm)
    C = buffered_cards(T, joint_target=policy["joint_target"], max_buffer=policy["max_buffer_points"],
                       top_legs=policy["top_legs"], rho_lo=policy["rho_lo"])
    C.to_csv(ROOT / "reports" / f"stage2b_cards_{name}.csv", index=False)
    TC = C[C.season.isin(test_seasons) & (C.released == True)]  # noqa: E712
    h(f"## Engine {name} — two-pick buffered cards\n")
    rows = []
    for season in test_seasons + ["POOLED"]:
        c = TC if season == "POOLED" else TC[TC.season == season]
        n = len(c)
        k = int(c.card_2of2.sum())
        lo, hi = wilson(k, n)
        rows.append({"season": season, "cards": n, "2of2": k,
                     "1of2": int(((c.win_a + c.win_b) == 1).sum()), "0of2": int(((c.win_a + c.win_b) == 0).sum()),
                     "rate_2of2": k / n if n else np.nan, "ci95": (lo, hi),
                     "leg_win": float((c.win_a.sum() + c.win_b.sum()) / (2 * n)) if n else np.nan,
                     "leg_pred": float((c.p_a + c.p_b).mean() / 2) if n else np.nan,
                     "model_joint": float(c.joint_model.mean()) if n else np.nan,
                     "avg_buffer": float((c.buf_a + c.buf_b).mean() / 2) if n else np.nan,
                     "roi_open_px_4.5%": float(c.profit_double.mean()) if n else np.nan,
                     "roi_close_px_4.5%": float(c.profit_double_close.mean()) if n else np.nan})
    h(df_to_md(pd.DataFrame(rows)))
    h()
    wa, wb = TC.win_a.astype(float), TC.win_b.astype(float)
    h(f"Leg independence: corr {np.corrcoef(wa, wb)[0, 1]:+.3f}; product of leg rates "
      f"{wa.mean() * wb.mean():.1%} vs actual {(wa * wb).mean():.1%}.")
    for nm, msk in (("both Over", (TC.side_a == 1) & (TC.side_b == 1)),
                    ("both Under", (TC.side_a == -1) & (TC.side_b == -1)), ("mixed", TC.side_a != TC.side_b)):
        h(f"* {nm}: {int(msk.sum())} cards, 2/2 {TC[msk].card_2of2.mean():.1%}")
    # CLV of legs
    Fi = P.set_index("game_key")
    mv = np.concatenate([TC[f"side_{l}"].values * (Fi.loc[TC[f"game_{l}"]].line_close.values
                                                     - Fi.loc[TC[f"game_{l}"]].line_open.values)
                         for l in ("a", "b")])
    h(f"\nOpen→close move in our direction: {np.nanmean(mv):+.2f} pts; moved our way "
      f"{np.nanmean(mv > 0):.1%}, against {np.nanmean(mv < 0):.1%}.\n")

    # line-shopping variant: same legs, threshold improved by (best book opener - median opener)
    shop_w = []
    for l in ("a", "b"):
        g = Fi.loc[TC[f"game_{l}"]]
        side = TC[f"side_{l}"].values
        best = np.array([best_open_for_side(bj, s)[0] if isinstance(bj, str) else np.nan
                         for bj, s in zip(F_extra.reindex(g.index).books_json.values, side)])
        gain = np.where(np.isnan(best), 0.0, np.where(side == 1, g.line_open.values - best,
                                                      best - g.line_open.values))
        thr = TC[f"thr_{l}"].values - side * np.maximum(gain, 0)
        out = g.outcome.values
        shop_w.append(np.where(side == 1, out > thr, out < thr))
    shop = shop_w[0] & shop_w[1]
    k, n = int(shop.sum()), len(shop)
    lo, hi = wilson(k, n)
    h(f"Line-shopping variant (same legs; each leg's alternate line moved by the best book's "
      f"opener advantage): 2/2 {k}/{n} = {k / n:.1%} (CI {lo:.1%}–{hi:.1%}).\n")

    # main line two-sided at REAL opening prices
    M = main_line_probs(P, cals)
    Mm = main_line_probs(P.assign(mu=P.mu_mkt, sd=P.sd_mkt), calm)
    e = M[M.season.isin(test_seasons) & M.eligible & ~M.push]
    em = Mm.set_index("game_key").loc[e.game_key]
    h(f"Main-line log loss model {log_loss(e.p_over / (e.p_over + e.p_under), e.over):.5f} vs market-only "
      f"{log_loss(em.p_over / (em.p_over + em.p_under), e.over):.5f} over {len(e)} games.\n")
    e = e.merge(F_extra[["books_json"]], left_on="game_key", right_index=True, how="left")
    rows = []
    for lo_, hi_ in ((0.5, 0.55), (0.55, 0.6), (0.6, 1.01)):
        mm = e[(e.p_best >= lo_) & (e.p_best < hi_)]
        res_med, res_best = [], []
        for _, r in mm.iterrows():
            s = r.best_side
            px = median_open_price(r.books_json, s, r.line) if isinstance(r.books_json, str) else np.nan
            px = 1.909 if np.isnan(px) else px
            win = r.outcome > r.line if s == 1 else r.outcome < r.line
            push = r.outcome == r.line
            res_med.append(0.0 if push else (px - 1 if win else -1.0))
            bl, bp, _ = best_open_for_side(r.books_json, s) if isinstance(r.books_json, str) else (np.nan, np.nan, None)
            if np.isnan(bl):
                bl, bp = r.line, 1.909
            winb = r.outcome > bl if s == 1 else r.outcome < bl
            pushb = r.outcome == bl
            res_best.append(0.0 if pushb else (bp - 1 if winb else -1.0))
        n = len(mm)
        k = int(mm.best_win.sum())
        rows.append({"two-sided P": f"{lo_:.0%}-{min(hi_, 1):.0%}", "bets": n,
                     "win_at_median_open": k / n if n else np.nan, "ci95": wilson(k, n),
                     "roi_median_open_real_price": float(np.mean(res_med)) if n else np.nan,
                     "roi_best_book_open_real_price": float(np.mean(res_best)) if n else np.nan})
    h(df_to_md(pd.DataFrame(rows)))
    h()
    return C, TC


def main(dry_run_seasons=None):
    if REPORT.exists() and dry_run_seasons is None:
        sys.exit(f"REFUSING: {REPORT} exists — stage 2b is evaluated once only.")
    from data.ncaab_unify import unify
    cfg2b = yaml.safe_load((ROOT / "config" / "stage2b.yaml").read_text())
    provenance = {}
    if dry_run_seasons is None:
        import hashlib
        from data import sbr_live
        man = sbr_live.RAW / "MANIFEST.json"
        if not man.exists():
            sys.exit("scrape not complete (no MANIFEST.json)")
        sbr_live.parse()                       # always rebuild from the complete raw scrape
        provenance = {"raw_files": len(json.loads(man.read_text())),
                      "manifest_sha256": hashlib.sha256(man.read_bytes()).hexdigest()}
    test_seasons = dry_run_seasons or cfg2b["test_seasons"]
    v2 = yaml.safe_load((ROOT / "config" / "stage2_locked.yaml").read_text())
    v3 = yaml.safe_load((ROOT / "config" / "stage3_v3_locked.yaml").read_text())

    u, box, rep = unify(write=False, include_live=dry_run_seasons is None)
    f = build_ncaab_features(write=False, games=u, box=box)
    d = market_frame(f, "open")
    seasons = sorted(d.season.unique())
    F_extra = u.set_index("game_key")[["books_json"]] if "books_json" in u else pd.DataFrame(
        {"books_json": pd.Series(dtype=object)})

    h("# Stage 2b — independent test on NCAAB 2021-22..2025-26 (run once)\n" if dry_run_seasons is None
      else f"# DRY RUN on {test_seasons}\n")
    h(f"Data: {json.dumps({k: v for k, v in rep.items() if k != 'live_by_season'}, default=str)}\n")
    if provenance:
        h(f"Raw scrape provenance: {provenance['raw_files']} JSON files, manifest sha256 "
          f"`{provenance['manifest_sha256'][:16]}…`\n")
    if "live_by_season" in rep:
        h(df_to_md(pd.DataFrame(rep["live_by_season"])))
        h()
    C2, T2 = evaluate_engine("v2_primary", d, seasons, test_seasons, v2["model"], v2["card_policy"],
                             (None, None), F_extra)
    pol3 = dict(v2["card_policy"])
    pol3["joint_target"] = v3["changes_vs_v2"]["joint_target"]
    C3, T3 = evaluate_engine("v3_secondary", d, seasons, test_seasons, v2["model"], pol3,
                             (v3["changes_vs_v2"]["train_decay"], v3["changes_vs_v2"]["calib_decay"]), F_extra)
    if dry_run_seasons is None:
        REPORT.write_text("\n".join(OUT) + "\n")
        log_experiment("stage2b_test", {"v2": v2, "v3": v3},
                       {"v2": card_summary(T2.assign(released=True)), "v3": card_summary(T3.assign(released=True))})


if __name__ == "__main__":
    main()
